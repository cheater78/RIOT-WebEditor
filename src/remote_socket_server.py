import asyncio
import websockets.server as wss
from abc import abstractmethod
from typing import TypeVar, Generic, Callable

import log
from safe_types import to_bytes

# Websocket
import websockets.server as wss
from websockets import exceptions as wse

SocketMessageType = bytes
to_SocketMessageType = to_bytes
RemoteSocketConnectionHandle = TypeVar("RemoteSocketConnectionHandle")
RemoteSocketConnectionCallbackFunc = Callable[[RemoteSocketConnectionHandle], None]
RemoteSocketMessageCallbackFunc = Callable[[RemoteSocketConnectionHandle, SocketMessageType], None]

class AsyncRemoteSocketServer(Generic[RemoteSocketConnectionHandle]):
    on_connection_opened_callback: RemoteSocketConnectionCallbackFunc[RemoteSocketConnectionHandle]
    on_connection_closed_callback: RemoteSocketConnectionCallbackFunc[RemoteSocketConnectionHandle]
    on_message_callback: RemoteSocketMessageCallbackFunc[RemoteSocketConnectionHandle]

    scheduled_writes: dict[RemoteSocketConnectionHandle, asyncio.Queue[SocketMessageType]]

    def __init__(self,
                 on_connection_opened_callback: RemoteSocketConnectionCallbackFunc[RemoteSocketConnectionHandle],
                 on_connection_closed_callback: RemoteSocketConnectionCallbackFunc[RemoteSocketConnectionHandle],
                 on_message_callback: RemoteSocketMessageCallbackFunc[RemoteSocketConnectionHandle],
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        self.on_connection_opened_callback = on_connection_opened_callback
        self.on_connection_closed_callback = on_connection_closed_callback
        self.on_message_callback = on_message_callback
        self.scheduled_writes = {}

        event_loop.create_task(self.__writer__())

    def write(self,
        socket_handle: RemoteSocketConnectionHandle,
        msg: SocketMessageType) -> None:
        queue: asyncio.Queue[SocketMessageType] | None = self.scheduled_writes.get(socket_handle)
        if queue is None:
            queue = asyncio.Queue[SocketMessageType]()
            self.scheduled_writes[socket_handle] = queue
        queue.put_nowait(msg)

    async def __writer__(self) -> None:
        while True:
            for socket_handle, queue in list(self.scheduled_writes.items()): # snapshot to avoid mutation issues
                try:
                    while not queue.empty():
                        message = queue.get_nowait()
                        await self.__write__(socket_handle, message)

                    # cleanup empty queues
                    if queue.empty():
                        del self.scheduled_writes[socket_handle]

                except wse.ConnectionClosed:
                    log.warn("AsyncWebSocketServer.__writer__: Connection closed while writing!")
                    self.on_connection_closed_callback(socket_handle)

            await asyncio.sleep(0)
    
    @abstractmethod
    async def __write__(self, socket_handle: RemoteSocketConnectionHandle, message: SocketMessageType) -> None:
        pass


class AsyncWebSocketServer(AsyncRemoteSocketServer[wss.WebSocketServerProtocol]):
    ConnectionHandle = wss.WebSocketServerProtocol
    WebSocketConnectionCallbackFunc = Callable[[ConnectionHandle], None]
    WebSocketMessageCallbackFunc = Callable[[ConnectionHandle, SocketMessageType], None]

    host: str
    port: int
    server: wss.WebSocketServer | None = None

    def __init__(self,
                 on_connection_opened_callback: WebSocketConnectionCallbackFunc,
                 on_connection_closed_callback: WebSocketConnectionCallbackFunc,
                 on_message_callback: WebSocketMessageCallbackFunc,
                 host: str = "0.0.0.0",
                 port: int = 7777,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        self.host = host
        self.port = port
        self.server = None

        super().__init__(on_connection_opened_callback,
                         on_connection_closed_callback,
                         on_message_callback,
                         event_loop)
        
        event_loop.create_task(self.__run__())

    async def __run__(self) -> None:
        if self.server and self.server.is_serving():
            log.warn("WebSocketServer already started!")
            return
        self.server = await wss.serve(self.__handler__, self.host, self.port)
        log.info("WebSocketServer started!")

    async def __handler__(self, websocket: ConnectionHandle) -> None:
        log.info(f"AsyncWebSocketServer.__handler__: New WebSocket connection from {websocket.remote_address}")
        self.on_connection_opened_callback(websocket)
        try:
            async for message in websocket:
                if type(message) is bytes:
                    self.on_message_callback(websocket, message)
                else:
                    log.error("AsyncWebSocketServer.__handler__: Message recieved was not bytes!")
        except wse.ConnectionClosed:
            log.info(f"AsyncWebSocketServer.__handler__: Connection closed! {websocket.remote_address}")
        self.on_connection_closed_callback(websocket)
    
    async def __write__(self, socket_handle: ConnectionHandle, message: SocketMessageType) -> None:
        await socket_handle.send(message) # type: ignore

# WebsocketStream or WebTransport implementations could be made here.
# We currently dont see any benefit of using those.