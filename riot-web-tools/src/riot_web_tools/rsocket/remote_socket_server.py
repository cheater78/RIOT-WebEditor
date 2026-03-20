import asyncio
from abc import ABC, abstractmethod
from typing import Callable
from uuid import UUID, uuid4

# Websocket
from websockets.legacy.server import WebSocketServer, WebSocketServerProtocol, serve
from websockets import exceptions as wse

from riot_web_tools.utils import log
from riot_web_tools.utils.types.bytes import to_bytes

SocketHandle = UUID
ServerConnectionCallbackFunc = Callable[[SocketHandle], None]
ServerCallbackFunc = Callable[[SocketHandle, bytes], None]

class AsyncRemoteSocketServer(ABC):
    _host: str
    _port: int
    _on_connection_opened_cb: ServerConnectionCallbackFunc
    _on_connection_closed_cb: ServerConnectionCallbackFunc
    _on_message_cb: ServerCallbackFunc

    _scheduled_writes: dict[SocketHandle, asyncio.Queue[bytes]]

    def __init__(self,
                 on_connection_opened_cb: ServerConnectionCallbackFunc,
                 on_connection_closed_cb: ServerConnectionCallbackFunc,
                 on_message_cb: ServerCallbackFunc,
                 host: str = "0.0.0.0",
                 port: int = 7777,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        self._on_connection_opened_cb = on_connection_opened_cb
        self._on_connection_closed_cb = on_connection_closed_cb
        self._on_message_cb = on_message_cb
        self._host = host
        self._port = port
        self._scheduled_writes = {}

        event_loop.create_task(self.__writer__())

    def write(self, socket_handle: SocketHandle, msg: bytes) -> None:
        queue: asyncio.Queue[bytes] | None = self._scheduled_writes.get(socket_handle)
        if queue is None:
            queue = asyncio.Queue[bytes]()
            self._scheduled_writes[socket_handle] = queue
        queue.put_nowait(msg)

    async def __writer__(self) -> None:
        while True:
            for socket_handle, queue in list(self._scheduled_writes.items()): # snapshot to avoid mutation issues
                try:
                    while not queue.empty():
                        message = queue.get_nowait()
                        await self.__write__(socket_handle, message)

                    # cleanup empty queues
                    if queue.empty():
                        del self._scheduled_writes[socket_handle]

                except wse.ConnectionClosed:
                    log.warn("AsyncWebSocketServer.__writer__: Connection closed while writing!")
                    # disconnect cb should be called in the implementation

            await asyncio.sleep(0)
    
    @abstractmethod
    async def __write__(self, socket_handle: SocketHandle, message: bytes) -> None:
        pass

    @abstractmethod
    def has_socket(self, handle: SocketHandle) -> bool:
        pass

class AsyncWebSocketServer(AsyncRemoteSocketServer):
    _server: WebSocketServer | None = None
    _server_connections: dict[SocketHandle, WebSocketServerProtocol]

    def __init__(self,
                 on_connection_opened_cb: ServerConnectionCallbackFunc,
                 on_connection_closed_cb: ServerConnectionCallbackFunc,
                 on_message_cb: ServerCallbackFunc,
                 host: str = "0.0.0.0",
                 port: int = 7777,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        self._server = None
        self._server_connections = {}
        super().__init__(
            on_connection_opened_cb,
            on_connection_closed_cb,
            on_message_cb,
            host,
            port,
            event_loop)
        event_loop.create_task(self.__run__())

    async def __run__(self) -> None:
        if self._server and self._server.is_serving():
            log.warn("WebSocketServer already started!")
            return
        self._server = await serve(self.__handler__, self._host, self._port)
        log.info("WebSocketServer started!")

    async def __handler__(self, websocket: WebSocketServerProtocol) -> None:
        log.info(f"AsyncWebSocketServer.__handler__: New WebSocket connection from {websocket.remote_address}")
        
        # Connection open
        websocket_handle: SocketHandle = self.__register_websocket__(websocket)
        self._on_connection_opened_cb(websocket_handle)

        try:
            async for message in websocket:
                message_bytes: bytes = to_bytes(message)
                self._on_message_cb(websocket_handle, message_bytes)
        except wse.ConnectionClosed:
            log.info(f"AsyncWebSocketServer.__handler__: Connection closed! {websocket.remote_address}")
        except Exception as e:
            log.error(f"AsyncWebSocketServer.__handler__: Connection failed with Exception {e}!")
        
        # Connection close
        self._on_connection_closed_cb(websocket_handle)
        self.__deregister_websocket__(websocket_handle)
        log.info(f"AsyncWebSocketServer.__handler__: Connection {websocket.remote_address} lost!")
    
    async def __write__(self, socket_handle: SocketHandle, message: bytes) -> None:
        websocket: WebSocketServerProtocol | None = self.__get_websocket__(socket_handle)
        if websocket is None:
            log.error("Provided socket_handle was not known to AsyncWebSocketServer!")
            return
        await websocket.send(message)

    def has_socket(self, handle: SocketHandle) -> bool:
        return self.__get_websocket__(handle) != None

    def __register_websocket__(self, websocket: WebSocketServerProtocol) -> SocketHandle:
        self.__wipe_websocket__(websocket) # remove if ws obj alr exists
        handle: SocketHandle = uuid4() # create new random UUID
        self._server_connections[handle] = websocket
        return handle

    def __deregister_websocket__(self, handle: SocketHandle) -> None:
        del self._server_connections[handle]

    def __get_websocket__(self, handle: SocketHandle) -> WebSocketServerProtocol | None:
        return self._server_connections.get(handle, None)

    def __wipe_websocket__(self, websocket: WebSocketServerProtocol) -> None:
        existing_websockets: list[SocketHandle] = [
            k
            for k, v in self._server_connections.items() 
            if v == websocket
        ]
        if existing_websockets:
            for handle in existing_websockets:
                self.__deregister_websocket__(handle)


# WebsocketStream or WebTransport implementations could be made here.
# We currently dont see any benefit of using those.

__all__ = [
    "SocketHandle",
    "ServerConnectionCallbackFunc",
    "ServerCallbackFunc",
    "AsyncRemoteSocketServer",
    "AsyncWebSocketServer"
]