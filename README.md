Serve vector tiles with cities names

## Build
```bash
docker build -t cesium-labels .
```

## Run
```bash
docker run -p 48088:48088 --rm cesium-labels
```

## Test with demo
```bash
cd demo
python -m SimpleHTTPServer 8000
```

Then go to http://localhost:8000/
