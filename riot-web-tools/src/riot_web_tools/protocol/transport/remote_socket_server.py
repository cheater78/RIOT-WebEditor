import asyncio
from typing import Callable

from riot_web_tools.utils import log
from riot_web_tools.rsocket.remote_socket_server import *
from riot_web_tools.protocol.model import *
import riot_web_tools.protocol.codec as codec

AsyncRemoteSocketServerImplementation: type[AsyncWebSocketServer] = AsyncWebSocketServer

ProtocolServerCallbackFunc = Callable[[LinkMessage], None]
ProtocolServerConnectionCallbackFunc = Callable[[IDAddress], None]
class ProtocolAsyncRemoteSocketServer(AsyncRemoteSocketServerImplementation):
    _connections: dict[IDAddress, SocketHandle] = {}
    _on_protocol_link_message_cb: ProtocolServerCallbackFunc
    _on_protocol_connection_established_cb: ProtocolServerConnectionCallbackFunc

    def __init__(self,
                on_protocol_link_message_cb: ProtocolServerCallbackFunc,
                on_protocol_connection_established_cb: ProtocolServerConnectionCallbackFunc,
                event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()) -> None:
        super().__init__(
            self.__on_connection_opened__,
            self.__on_connection_closed__,
            self.__on_message__,
            event_loop=event_loop)
        self._connections = {}
        self._on_protocol_link_message_cb = on_protocol_link_message_cb
        self._on_protocol_connection_established_cb = on_protocol_connection_established_cb
    
    def write_to(self, receiver: Address, message: Message) -> None:
        encoded: bytes = codec.encode(message)
        if not isinstance(receiver, IDAddress): # DeviceAdress -> ClientAddress
            receiver = ClientAddress()
        if not self.is_established(receiver):
            log.error(f"write_to: {receiver} has no established connection!")
            return
        socket_handle: SocketHandle = self.__get_connection_handle__(receiver)
        self.write(socket_handle, encoded)

    def write_to_client(self, message: Message) -> None:
        self.write_to(ClientAddress(), message)
    
    def write_link(self, message: LinkMessage) -> None:
        self.write_to(message.receiver, message)

    def __on_connection_opened__(self, socket_handle: SocketHandle) -> None:
        pass

    def __on_connection_closed__(self, socket_handle: SocketHandle) -> None:
        self.__close_connection__(socket_handle)
    
    def __on_message__(self, socket_handle: SocketHandle, message: bytes) -> None:
        match codec.decode(message):
            case LinkMessage() as link_message:
                self._on_protocol_link_message_cb(link_message)
            case MessageConnect() as connect_message:
                # Connection established
                if not isinstance(connect_message.peer_id, IDAddress):
                    log.warn("ConnectMessage from non IDAddress!")
                    return
                self.__establish_connection__(socket_handle, connect_message.peer_id)
                self.write_to(connect_message.peer_id, MessageConnectAck())
                log.info(f"AsyncWebSocketServer.__handler__: New Protocol connection from {connect_message.peer_id}")
                self._on_protocol_connection_established_cb(connect_message.peer_id)
            case MessageDisconnect():
                # Connection closed
                self.__close_connection__(socket_handle)
                log.info(f"AsyncWebSocketServer.__handler__: Protocol connection closed!")
            case _ as drop_message:
                log.error(f"Dropping unknown message: {drop_message}")
    
    def is_established(self, address: IDAddress) -> bool:
        return self._connections.get(address, None) != None

    def __establish_connection__(self, handle: SocketHandle, address: IDAddress) -> None:
        self.__wipe_connection__(handle) # remove if ws obj alr exists
        self._connections[address] = handle

    def __close_connection__(self, identifier: SocketHandle | IDAddress) -> None:
        if isinstance(identifier, SocketHandle):
            self.__wipe_connection__(identifier)
        else:
            del self._connections[identifier]

    def __get_connection_handle__(self, address: IDAddress) -> SocketHandle:
        unsafe_handle: SocketHandle | None = self._connections.get(address, None)
        if not unsafe_handle:
            raise 
        return unsafe_handle

    def __wipe_connection__(self, handle: SocketHandle) -> None:
        existing_websockets: list[IDAddress] = [
            k
            for k, v in self._connections.items() 
            if v == handle
        ]
        if existing_websockets:
            for address in existing_websockets:
                self.__close_connection__(address)