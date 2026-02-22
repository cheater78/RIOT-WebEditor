import asyncio

from remote_socket_client import AsyncRemoteSocketClient, AsyncWebsocketClient, RemoteSocketConnectionFailedCallbackFunc
import protocol
from protocol import ProtocolCallbackFunc
from protocol_message import *
from protocol_field_types import *

AsyncRemoteSocketClientImplementation: type[AsyncRemoteSocketClient] = AsyncWebsocketClient
class ProtocolAsyncRemoteSocketClient(AsyncRemoteSocketClientImplementation):
    _connection_established: bool = False
    _remote_socket_me: Address
    _protocol_message_cb: ProtocolCallbackFunc

    def __init__(self,
                 shell_id: int,
                 protocol_message_cb: ProtocolCallbackFunc,
                 failed_cb: RemoteSocketConnectionFailedCallbackFunc,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        
        self._protocol_message_cb = protocol_message_cb
        self._remote_socket_me = Address(AddressType.SHELL, shell_id)
        super().__init__(
            self.__on_open__,
            self.__on_close__,
            failed_cb,
            self.__on_message__,
            reconnect_delay_s=1,
            reconnect_trys=3,
            event_loop=event_loop)

    def disconnect(self) -> None:
        self.write_protocol(MessageDisconnect())
        super().disconnect()

    def is_established(self) -> bool:
        return self.is_connected() and self._connection_established

    def write_protocol(self, message: ProtocolMessage) -> None:
        encoded_message: bytes = protocol.encode(message)
        super().write(encoded_message)

    def __on_open__(self) -> None:
        self.write_protocol(MessageConnect(self._remote_socket_me))

    def __on_close__(self) -> None:
        self._connection_established = False

    def __on_message__(self, message: bytes) -> None:
        decoded: ProtocolMessage | None = protocol.decode(message)
        if decoded is None:
            log.error("Failed to decode message from WS!")
            return
        match decoded.type:
            case MessageType.CONNECT_ACK:
                self._connection_established = True
            case MessageType.DISCONNECT:
                self.disconnect()
            case _:
                self._protocol_message_cb(decoded)