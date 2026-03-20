#!/bin/bash

apt update

apt install -y \
    python3 \
    python3-websockets \
    python3-cbor2 \
    python3-pytest

python3 -m pip install --user pyinstaller --break-system-packages