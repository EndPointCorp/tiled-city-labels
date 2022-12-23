import csv
import sys
import math

from simple_http_server import request_map, server, PathValue, Headers

def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)

    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    
    return (lat_deg, lon_deg)

def num2box(x, y, zoom):
    south, west = num2deg(x, y + 1, zoom)
    north, east = num2deg(x + 1, y, zoom)

    return Box(west, south, east, north) 

def distanceDegree(lon1, lat1, lon2, lat2):
    dx = lon1 - lon2
    dy = lat1 - lat2

    return math.sqrt(dx * dx + dy * dy)

def geoNum2Box(x, y, level):
    """
        const xTiles = this.getNumberOfXTilesAtLevel(level);
        const yTiles = this.getNumberOfYTilesAtLevel(level);

        const xTileWidth = rectangle.width / xTiles;
        const west = x * xTileWidth + rectangle.west;
        const east = (x + 1) * xTileWidth + rectangle.west;

        const yTileHeight = rectangle.height / yTiles;
        const north = rectangle.north - y * yTileHeight;
        const south = rectangle.north - (y + 1) * yTileHeight;
    """
    xTiles = 2 << level
    yTiles = 1 << level

    xTileWidth = 360.0 / xTiles
    west = x * xTileWidth - 180.0
    east = (x + 1) * xTileWidth - 180.0

    yTileHeight = 180.0 / yTiles
    north = 90.0 - y * yTileHeight
    south = 90.0 - (y + 1) * yTileHeight

    return Box(west, south, east, north) 


class Box():
    def __init__(self, minx, miny, maxx, maxy):
        self.minx = minx
        self.miny = miny
        self.maxx = maxx
        self.maxy = maxy
    
    def contains(self, x, y):
        xin = x >= self.minx and x <= self.maxx
        yin = y >= self.miny and y <= self.maxy
        return  xin and yin

    def intersects(self, box):
        e = 0.0000001

        outside = \
            self.maxx < box.minx - e or \
            self.maxy < box.miny - e or \
            self.minx - e > box.maxx or \
            self.miny - e > box.maxy

        return not outside
    
    def __str__(self):
        return 'Box({}, {}, {}, {})'.format(
            self.minx, 
            self.miny,
            self.maxx, 
            self.maxy,
            )


class Node():
    def __init__(self, x, y, z, points, threshold = 10):
        self.x = x
        self.y = y
        self.z = z

        self.bbox = num2box(self.x, self.y, self.z)

        self.threshold = threshold

        self.points = points
        self.children = []
    
    def insert(self, point):
        self.addSorted(point)
        while len(self.points) > self.threshold:
            self.insertChild(self.points.pop())
    
    def insertChild(self, point):
        lon, lat = point.get('position')
        x, y = deg2num(lat, lon, self.z + 1)
        chldNode = self.getOrCreateChild(x, y)
        chldNode.insert(point)

    def getOrCreateChild(self, x, y):
        chld = self.getChild(x, y)
        if chld:
            return chld 

        chld = Node(x, y, self.z + 1, [], self.threshold)
        self.children.append(chld)
        return chld

    def getChild(self, x, y):
        for chld in self.children:
            if chld.x == x and chld.y == y:
                return chld
        return None

    def addSorted(self, point):
        for i, pnt in enumerate(self.points):
            if point.get('population') >= pnt.get('population'):
                self.points.insert(i, point)
                return        

        self.points.append(point)


class QTree():
    def __init__(self, pointsPerNode = 10):
        self.threshold = pointsPerNode
        self.root = Node(0, 0, 0, [])

    def insert(self, point):
        self.root.insert(point)
    
    def traverseDFS(self, visitor):
        def itraverse(node):
            for chld in node.children:
                itraverse(chld)
            visitor(node)

        itraverse(self.root)
    
    def findByNameBFS(self, name):
        stack = [self.root]
        def rTraverse(depth):
            nonlocal stack
            nonlocal name

            while len(stack) > 0 and stack[0].z <= depth:
                node = stack.pop(0)
                
                for p in node.points:
                    if p.get('name') == name:
                        return p, node

                for c in node.children:
                    stack.append(c)
            
            if len(stack) > 0:
                return rTraverse(depth + 1)
            
            return None, None
        
        return rTraverse(0)

    
    def traverseByBox(self, box, visitor):
        stack = [self.root]
        def rTraverse():
            nonlocal visitor
            nonlocal box
            nonlocal stack

            node = stack.pop(0)

            for p in node.points:
                lon, lat = p.get('position')
                if box.contains(lon, lat):
                    if visitor(p, node):
                        return

            for c in node.children:
                if c.bbox.intersects(box):
                    stack.append(c)
            
            if len(stack) > 0:
                rTraverse()
        
        rTraverse()
    

    def traverseToTile(self, x, y, z, visitor):
        lat1, lon1 = num2deg(x, y, z)
        lat2, lon2 = num2deg(x + 1, y + 1, z)
        
        lat = (lat1 + lat2) / 2.0
        lon = (lon1 + lon2) / 2.0
        
        tile = self.root
        while tile and tile.z <= z:
            visitor(tile)
            cx, cy = deg2num(lat, lon, tile.z + 1)
            tile = tile.getChild(cx, cy)

    def getTilePoints(self, x, y, z):
        points = []
        def collector(node):
            nonlocal points
            for p in node.points:
                lon, lat = p.get('position')
                cx, cy = deg2num(lat, lon, z)
                if cx == x and cy == y:
                    points.append(p)

        self.traverseToTile(x, y, z, collector)
        return points
    
    def getBoxPoints(self, box, maxPoints = None):
        points = []
        d = (box.maxx - box.minx) * 0.2
        def collector(point, node):
            nonlocal d
            nonlocal points
            nonlocal maxPoints

            cluster = False
            lon1, lat1 = point.get('position')
            for p in points:
                lon2, lat2 = p.get('position')
                if distanceDegree(lon1, lat1, lon2, lat2) < d:
                    cluster = True
                    break
            
            if not cluster:
                points.append(point)

            if maxPoints and len(points) >= maxPoints:
                return True

        self.traverseByBox(box, collector)
        return points


CACHE = QTree()

def readCities(path):
    cities = []
    with open(path, mode='r') as file:
        for row in csv.reader(file, delimiter='\t'):
            cities.append({
                "id": int(row[0]),
                "name": row[1],
                "position": [ float(row[5]), float(row[4]) ],
                "population": int(row[14]),
                "elevation": int(row[16]),
            })
    
    return cities

def tile(cities):
    for city in cities:
        CACHE.insert(city)
    
    z_max = 0
    count = 0
    def max_z_visitor(qnode):
        nonlocal z_max
        nonlocal count
        z_max = max(qnode.z, z_max)
        count = count + len(qnode.points) 

    CACHE.traverseDFS(max_z_visitor)
    print('Maximum depth: {}, total count: {}'.format(z_max, count))

@request_map('/{grid}/{z_raw}/{x_raw}/{y_raw}\.{format}')
def serve_tms(
    grid = PathValue(),
    z_raw = PathValue(), 
    x_raw = PathValue(), 
    y_raw = PathValue(), 
    format = PathValue() ):
    
    x = int(x_raw)
    y = int(y_raw)
    z = int(z_raw)

    box = geoNum2Box(x, y, z)

    cities = CACHE.getBoxPoints(box, maxPoints = 4)

    return 200, Headers({"Access-Control-Allow-Origin": "*"}), {"features": cities}

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'data/cities500.txt'

    cities = readCities(path)
    tile(cities)

    print(cities[0])

    server.start(port = 48088)


if __name__ == '__main__':
    main()