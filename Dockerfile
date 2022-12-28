FROM ubuntu:focal

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install simple_http_server

COPY src/tile.py opt/tile.py
COPY data opt/data

ENV PORT=48088 DATA_PATH=/opt/data/cities500.txt

CMD [ "python3", "/opt/tile.py" ]