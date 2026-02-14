import asyncio
from abc import abstractmethod
from typing import Callable

import log
from safe_types import to_bytes

# Websocket
import websockets.client as wsc
from websockets import exceptions as wse

SocketMessageType = bytes
to_SocketMessageType = to_bytes
RemoteSocketConnectionCallbackFunc = Callable[[], None]
RemoteSocketMessageCallbackFunc = Callable[[SocketMessageType], None]

class AsyncRemoteSocketClient:
    on_connection_opened_callback: RemoteSocketConnectionCallbackFunc
    on_connection_closed_callback: RemoteSocketConnectionCallbackFunc
    on_message_callback: RemoteSocketMessageCallbackFunc

    reconnect_delay_ms: float = 1.5
    is_connecting: bool = False
    event_loop: asyncio.AbstractEventLoop
    scheduled_writes: asyncio.Queue[SocketMessageType]

    def __init__(self,
                 on_connection_opened_callback: RemoteSocketConnectionCallbackFunc,
                 on_connection_closed_callback: RemoteSocketConnectionCallbackFunc,
                 on_message_callback: RemoteSocketMessageCallbackFunc,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        self.on_connection_opened_callback = on_connection_opened_callback
        self.on_connection_closed_callback = on_connection_closed_callback
        self.on_message_callback = on_message_callback
        self.event_loop=event_loop
        self.scheduled_writes = asyncio.Queue[SocketMessageType]()

        event_loop.create_task(self.__run__())
    
    def write(self, msg: SocketMessageType) -> None:
        self.scheduled_writes.put_nowait(msg)

    async def __connect__(self, no_timeout: bool = False) -> None:
        if self.__connected__():
            log.warn("AsyncRemoteSocketClient.__connect__: Already connected! Skipping...")
            return
        if self.is_connecting:
            log.warn("AsyncRemoteSocketClient.__connect__: Already connecting! Skipping...")
            if not no_timeout and not self.__connected__():
                await asyncio.sleep(self.reconnect_delay_ms)
            return
        self.is_connecting = True
        await self.__connect_raw__()
        self.is_connecting = False
        if not no_timeout and not self.__connected__():
            await asyncio.sleep(self.reconnect_delay_ms)

    @abstractmethod
    def __connected__(self) -> bool:
        pass

    async def __run__(self) -> None:
        await self.__connect__()
        self.event_loop.create_task(self.__reader__())
        self.event_loop.create_task(self.__writer__())

    @abstractmethod
    async def __connect_raw__(self) -> None:
        pass

    async def __reader__(self) -> None:
        while True:
            await asyncio.sleep(0)
            if not self.__connected__():
                await self.__connect__()
                continue

            raw_read: SocketMessageType | None = await self.__read__()
            
            if not raw_read:
                continue

            socket_msg: SocketMessageType = to_SocketMessageType(raw_read)
            if not socket_msg:
                continue

            self.on_message_callback(socket_msg)
    
    @abstractmethod
    async def __read__(self) -> SocketMessageType | None:
        pass

    async def __writer__(self) -> None:
        while True:
            await asyncio.sleep(0)
            if not self.__connected__():
                await self.__connect__()
                continue

            try:
                while not self.scheduled_writes.empty():
                    message = self.scheduled_writes.get_nowait()
                    await self.__write__(message)

            except wse.ConnectionClosed:
                log.warn("AsyncWebSocketServer.__writer__: Connection closed while writing!")
                self.on_connection_closed_callback()
            
            
    
    @abstractmethod
    async def __write__(self, message: SocketMessageType) -> None:
        pass

class AsyncWebsocketClient(AsyncRemoteSocketClient):
    location: str
    websocket: wsc.WebSocketClientProtocol | None = None

    def __init__(self,
                on_connection_opened_callback: RemoteSocketConnectionCallbackFunc,
                on_connection_closed_callback: RemoteSocketConnectionCallbackFunc,
                on_message_callback: RemoteSocketMessageCallbackFunc,
                address: str = "127.0.0.1",
                port: int = 7777,
                use_ssl: bool = False,
                event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self.location: str = "ws" + ("s" if use_ssl else "") + "://" + str(address) + ":" + str(port)

        super().__init__(on_connection_opened_callback,
                         on_connection_closed_callback,
                         on_message_callback,
                         event_loop)

    async def __connect_raw__(self) -> None:
        if self.__connected__():
            log.info(f"AsyncWebsocketHandler: Already open! not opening again.")
            return
        log.info(f"AsyncWebsocketHandler: Connecting... ({self.location})")
        self.websocket = await wsc.connect(self.location)
        log.info(f"AsyncWebsocketHandler: Connection established!")

        self.on_connection_opened_callback()
    
    def __connected__(self) -> bool:
        return self.websocket is not None and not self.websocket.closed

    async def __read__(self) -> SocketMessageType | None:
        try:
            # query websocket blocking, runs in an async event loop in SocketConnection
            return await self.websocket.recv() # type: ignore
        except wse.ConnectionClosed:
            log.warn("AsyncWebsocketClient: Connecttion lost!")
            self.on_connection_closed_callback()
            return None

    async def __write__(self, message: SocketMessageType) -> None:
        log.info(f"AsyncWebsocketClient: Writing {message}")
        await self.websocket.send(message) # type: ignore


# WebsocketStream or WebTransport implementations could be made here.
# We currently dont see any benefit of using those.