import asyncio
from abc import abstractmethod
from typing import Callable

from riot_web_tools.utils import log
from riot_web_tools.utils.types.bytes import to_bytes

ClientConnectionCallbackFunc = Callable[[], None]
ClientMessageCallbackFunc = Callable[[bytes], None]
class AsyncRemoteSocketClient:
    _event_loop: asyncio.AbstractEventLoop
    _is_connecting: bool
    _is_disconnecting: bool
    _reconnect_delay_s: float

    _opened_cb: ClientConnectionCallbackFunc
    _closed_cb: ClientConnectionCallbackFunc
    _message_cb: ClientMessageCallbackFunc

    _write_queue: asyncio.Queue[bytes]

    def __init__(self,
                 opened_callback: ClientConnectionCallbackFunc,
                 closed_callback: ClientConnectionCallbackFunc,
                 message_callback: ClientMessageCallbackFunc,
                 reconnect_delay_s: float = 1,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        self._event_loop=event_loop
        self._is_connecting = False
        self._is_disconnecting = False
        self._reconnect_delay_s = reconnect_delay_s

        self._opened_cb = opened_callback
        self._closed_cb = closed_callback
        self._message_cb = message_callback
        self._write_queue = asyncio.Queue[bytes]()

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    def connect(self) -> None:
        if self.is_connected():
            log.warn("Already connected! Skipping...")
            return
        if self._is_connecting:
            log.warn("Already connecting! Skipping...")
            return
        self._is_connecting = True
        self._event_loop.create_task(self.__connect_and_run__())
    
    def disconnect(self) -> None:
        if not self.is_connected():
            log.warn("Already disconntected! Skipping...")
            return
        if self._is_disconnecting:
            log.warn("Already connecting! Skipping...")
            return
        self._is_disconnecting = True
        self._event_loop.create_task(self.__stop_and_disconnect__())
    
    def write(self, msg: bytes) -> None:
        try:
            self._write_queue.put_nowait(msg)
        except asyncio.QueueFull:
            log.warn("Remote Socket write queue was full! scheduling submission..")
            self._event_loop.create_task(self._write_queue.put(msg))

    async def __connect_and_run__(self) -> None:
        while True:
            await self.__connect__()
            if not self.is_connected():
                await asyncio.sleep(self._reconnect_delay_s)
            else:
                break
        self._is_connecting = False
        if self.is_connected():
            self._event_loop.create_task(self.__reader__())
            self._event_loop.create_task(self.__writer__())
            self._opened_cb()
            

    async def __stop_and_disconnect__(self) -> None:
        await self.__disconnect__()
        self._is_disconnecting = False

    @abstractmethod
    async def __connect__(self) -> None:
        pass

    @abstractmethod
    async def __disconnect__(self) -> None:
        pass
    
    @abstractmethod
    async def __read__(self) -> bytes | None:
        pass
    
    @abstractmethod
    async def __write__(self, message: bytes) -> None:
        pass

    async def __reader__(self) -> None:
        while self.is_connected():
            try:
                raw_read: bytes | None = await self.__read__()
            except:
                break
            if not raw_read:
                await asyncio.sleep(0)
                continue
            socket_msg: bytes = to_bytes(raw_read)
            if not socket_msg:
                await asyncio.sleep(0)
                continue
            self._message_cb(socket_msg)
        self._closed_cb()
    
    async def __writer__(self) -> None:
        while self.is_connected():
            try:
                message: bytes = self._write_queue.get_nowait()
                if not message:
                    await asyncio.sleep(0)
                    continue
                await self.__write__(message)    
            except asyncio.QueueEmpty:
                await asyncio.sleep(0)
                continue
            except:
                break
        self._closed_cb()

# Websocket
import websockets.client as wsc
# from websockets import exceptions as wse # TODO: kept for debugging, remove!
class AsyncWebsocketClient(AsyncRemoteSocketClient):
    _location: str
    _websocket: wsc.WebSocketClientProtocol | None = None # type: ignore

    def __init__(self,
                 opened_callback: ClientConnectionCallbackFunc,
                 closed_callback: ClientConnectionCallbackFunc,
                 message_callback: ClientMessageCallbackFunc,
                 address: str = "127.0.0.1",
                 port: int = 7777,
                 use_ssl: bool = False,
                 reconnect_delay_s: float = 1,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self._location: str = "ws" + ("s" if use_ssl else "") + "://" + str(address) + ":" + str(port)

        super().__init__(opened_callback,
                         closed_callback,
                         message_callback,
                         reconnect_delay_s,
                         event_loop)
        
    def is_connected(self) -> bool:
        return self._websocket is not None and not self._websocket.closed

    async def __connect__(self) -> None:
        try:
            self._websocket = await wsc.connect(self._location) # type: ignore
        except:
            self._websocket = None
    
    async def __disconnect__(self) -> None:
        if not self._websocket:
            return
        await self._websocket.close()

    async def __read__(self) -> bytes | None:
        if not self._websocket:
            return
        return to_bytes(await self._websocket.recv()) # type: ignore

    async def __write__(self, message: bytes) -> None:
        if not self._websocket:
            return
        await self._websocket.send(message) # type: ignore

# WebsocketStream or WebTransport implementations could be made here.
# We currently don't see any benefit of using those.

__all__ = [
    "ClientConnectionCallbackFunc",
    "ClientMessageCallbackFunc",
    "AsyncRemoteSocketClient",
    "AsyncWebsocketClient",
]