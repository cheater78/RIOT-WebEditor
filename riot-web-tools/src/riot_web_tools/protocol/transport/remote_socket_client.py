import asyncio
from typing import Callable

from riot_web_tools.utils import log
from riot_web_tools.rsocket.remote_socket_client import AsyncRemoteSocketClient, AsyncWebsocketClient
from riot_web_tools.protocol.model.message import *
from riot_web_tools.protocol.model.address import *
from riot_web_tools.protocol import codec

ProtocolClientCallbackFunc = Callable[[LinkMessage], None]

AsyncRemoteSocketClientImplementation: type[AsyncRemoteSocketClient] = AsyncWebsocketClient
class ProtocolAsyncRemoteSocketClient(AsyncRemoteSocketClientImplementation):
    _connection_established: bool = False
    _connection_failed: bool = False
    _remote_socket_me: Address
    _protocol_link_message_cb: ProtocolClientCallbackFunc

    def __init__(self,
                 shell_id: int,
                 protocol_message_cb: ProtocolClientCallbackFunc,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        
        self._protocol_link_message_cb = protocol_message_cb
        self._remote_socket_me = ShellAddress(shell_id)
        super().__init__(
            self.__on_open__,
            self.__on_close__,
            self.__on_message__,
            reconnect_delay_s=1,
            event_loop=event_loop)

    def disconnect(self) -> None:
        self.write_protocol(MessageDisconnect())
        super().disconnect()

    def is_established(self) -> bool:
        return self.is_connected() and self._connection_established

    def write_protocol(self, message: Message) -> None:
        encoded_message: bytes = codec.encode(message)
        super().write(encoded_message)

    def __on_open__(self) -> None:
        self.write_protocol(MessageConnect(self._remote_socket_me))

    def __on_close__(self) -> None:
        self._connection_established = False

    def __on_message__(self, message: bytes) -> None:
        decoded: Message = codec.decode(message)
        match decoded:
            case MessageConnect() as c:
                log.warn(f"Received MessageConnectAck on Shell! Message: {c}")
            case MessageDisconnect():
                self.disconnect()
            case MessageConnectAck():
                self._connection_established = True
            case LinkMessage() as link_message:
                self._protocol_link_message_cb(link_message)
            case _ as illegal_message:
                log.warn(f"Received illegal message! Message: {illegal_message}")
    
    def __on_socket_failed__(self, retry: bool) -> None:
        log.warn("Socket connection failed!" + ("Retrying..." if retry else ""))
        self._connection_failed = retry
        pass