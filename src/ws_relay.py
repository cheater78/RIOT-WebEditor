import asyncio
import sys
import os
import socket
import websockets

from typing import Callable

class WebCommandServer:
    port: int
    websocket: websockets.serve
    connected_client: websockets.WebSocketServerProtocol | None = None
    on_message: Callable[[str], None] | None = None

    def __init__(self, port: int):
        self.port = port

    async def start(self):
        print("Starting WebCommandServer...")
        self.server = await websockets.serve(self.__on_connect__, "0.0.0.0", self.port)
        print("WebCommandServer started")

        asyncio.create_task(self.__worker__())
        print("WebCommandServer worker launched")

    def set_message_callback(self, callback: Callable[[str], None]):
        self.on_message = callback
        print("WebCommandServer Message callback set")

    async def write(self, msg: str):
        if self.connected_client:
            try:
                print(f"WebCommandServer sending: {msg}")
                await self.connected_client.send(msg)
            except websockets.ConnectionClosed:
                print("WebCommandServer client disconnected during send")
                self.connected_client = None

    async def __on_connect__(self, websocket):
        print("WebCommandServer client connected")
        self.connected_client = websocket

    async def __worker__(self):
        while True:
            if not self.connected_client or not self.on_message:
                await asyncio.sleep(0.1)
                continue

            try:
                async for data in self.connected_client:
                    msg = data.decode() if isinstance(data, bytes) else data
                    print(f"WebSocket received: {msg}")
                    self.on_message(msg)
            except websockets.ConnectionClosed:
                print("WebSocket disconnected")
                self.connected_client = None


class UnixReaderSocket:
    path: str
    server: socket.socket
    on_message: Callable[[str], None] | None = None

    def __init__(self, path: str):
        self.path = path
        if os.path.exists(path):
            os.remove(path)

        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(path)
        self.server.listen(1)

        print("Starting UnixReaderSocket worker task")
        asyncio.create_task(self.__worker__())
        print("UnixReaderSocket Worker task started")

    def set_message_callback(self, callback: Callable[[str], None]):
        self.on_message = callback

    async def __worker__(self):
        loop = asyncio.get_running_loop()

        while True:
            # run blocking accept() in executor thread
            conn, _ = await loop.run_in_executor(None, self.server.accept)
            print("UnixReaderSocket accepted connection")

            def read_all():
                chunks = []
                while True:
                    buf = conn.recv(4096)
                    if not buf:
                        break
                    chunks.append(buf)
                return b"".join(chunks)

            # blocking read_all() in a thread
            print("UnixReaderSocket reading..")
            data = await loop.run_in_executor(None, read_all)
            msg = data.decode()
            print("UnixReaderSocket decoded message ", msg)

            if self.on_message:
                print("UnixReaderSocket calling on_message")
                self.on_message(msg)

            conn.close()
            print("UnixReaderSocket connection closed")


async def main():
    port = int(sys.argv[1])
    unix_sock = sys.argv[2]

    wss = WebCommandServer(port)
    await wss.start()

    us = UnixReaderSocket(unix_sock)
    us.set_message_callback(lambda msg: asyncio.create_task(wss.write(msg)))

    await asyncio.Future()

asyncio.run(main())