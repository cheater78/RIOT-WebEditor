#!/usr/bin/env python3
import asyncio

import log
from remote_socket_server import SocketMessageType, AsyncWebSocketServer
import protocol
from protocol_message import *
from protocol_field_types import AddressType, Address

class AsyncProtocolRemoteSocketServer:
    RemoteSocketServer = AsyncWebSocketServer
    ServerConnectionHandle = RemoteSocketServer.ConnectionHandle

    socket_server: RemoteSocketServer
    sockets_by_id: dict[int, ServerConnectionHandle] = {}

    requested_shells: list[MessageShellRequest]

    def __init__(self) -> None:
        self.event_loop = asyncio.new_event_loop()
        self.socket_server = AsyncProtocolRemoteSocketServer.RemoteSocketServer(self.__on_connection_opened__,
                                                                             self.__on_connection_closed__,
                                                                             self.__on_message__,
                                                                             event_loop=self.event_loop)
        self.sockets_by_id = {}
        self.requested_shells = []
    
    def write(self, message: ProtocolLinkMessage) -> None:
        self.write_to(message.receiver, message)
    
    def write_to_client(self, message: ProtocolMessage) -> None:
        self.write_to(Address(AddressType.CLIENT, 0), message)

    def write_to(self, to:Address, message: ProtocolMessage) -> None:
        encoded: SocketMessageType = protocol.encode(message)
        match to.type:
            case AddressType.CLIENT | AddressType.DEVICE:
                reciever_id: int = 0
            case AddressType.SHELL:
                reciever_id: int = to.value
        if not reciever_id in self.sockets_by_id.keys():
            log.error(f"AsyncProtocolRemoteSocketRelay.write_to: ID {reciever_id} has no associated socket!")
            return
        self.socket_server.write(self.sockets_by_id[reciever_id], encoded)

    def run(self) -> None:
        log.info(">Starting event loop...")
        self.event_loop.run_forever()

    def __get_registered_by_id__(self, peer_id: int) -> ServerConnectionHandle | None:
        return self.sockets_by_id.get(peer_id, None)
    
    def __get_registered_by_handle__(self, socket_handle: ServerConnectionHandle) -> int | None:
        for peer_id, handle in self.sockets_by_id.items():
            if handle.id == socket_handle.id:
                return peer_id
        return None

    def __register_socket__(self, socket_handle: ServerConnectionHandle, peer_id: int) -> None:
        if peer_id in self.sockets_by_id.keys():
            log.warn(f"AsyncProtocolRemoteSocketRelay.__register_socket__: ID is already registered {peer_id}! Overriding...")
            del self.sockets_by_id[peer_id]

        # Check if already connected -> replace the old connection
        if ambiguous_id:= self.__get_registered_by_handle__(socket_handle):
            log.warn(f"AsyncProtocolRemoteSocketRelay.__register_socket__: SocketHandle is already registered under ID {ambiguous_id}! Overriding...")
            del self.sockets_by_id[ambiguous_id]
        
        # register new connection
        self.sockets_by_id[peer_id] = socket_handle

    def __unregister_socket__(self, id: int) -> None:
        if id in self.sockets_by_id:
            del self.sockets_by_id[id]
            log.info(f"AsyncProtocolRemoteSocketRelay.__unregister_socket__: Unregistered ID {id}")
        else:
            log.warn(f"AsyncProtocolRemoteSocketRelay.__unregister_socket__: ID {id} was not registered!")

    def __on_connection_opened__(self, socket_handle: ServerConnectionHandle) -> None:
        log.info(f"AsyncProtocolRemoteSocketRelay: New connection opened")

    def __on_connection_closed__(self, socket_handle: ServerConnectionHandle) -> None:
        log.info(f"AsyncProtocolRemoteSocketRelay: Connection closed")
        if registered_id:= self.__get_registered_by_handle__(socket_handle):
            log.info(f"AsyncProtocolRemoteSocketRelay.__on_connection_closed__: Unregistering SocketHandle from ID {registered_id}")
            self.__unregister_socket__(registered_id)
        else:
            log.warn(f"AsyncProtocolRemoteSocketRelay.__on_connection_closed__: SocketHandle was not registered!")
    
    def __on_message__(self, socket_handle: ServerConnectionHandle, message: SocketMessageType) -> None:
        
        decoded_message = protocol.decode(message)
        if decoded_message is None:
            log.error(f"AsyncProtocolRemoteSocketRelay: Failed to decode message from : {message}")
            return
        
        match decoded_message:
            case ProtocolLinkMessage() as link_message:
                self.__on_protocol_link_message__(socket_handle, link_message)
            case MessageConnect() as connect_message:
                self.__on_message_connect__(socket_handle, connect_message)
            case MessageDisconnect() as disconnect_message:
                self.__on_message_disconnect__(socket_handle, disconnect_message)
            case MessageDNRRequest() as dnr_request_message:
                log.info(f"Relaying DNR: {dnr_request_message}")
                self.write_to_client(dnr_request_message)
            case _ as drop_message:
                log.error(f"Dropping unknown message: {drop_message}")
    
    def __on_protocol_link_message__(self, socket_handle: ServerConnectionHandle, link_message: ProtocolLinkMessage) -> None:
        # Drop illegal sender-receiver paired message (device|client to device|client or shell to shell)
        sender_group_is_client: bool = link_message.sender.type == AddressType.DEVICE or link_message.sender.type == AddressType.CLIENT
        reciever_group_is_client: bool = link_message.receiver.type == AddressType.DEVICE or link_message.receiver.type == AddressType.CLIENT
        if sender_group_is_client == reciever_group_is_client:
            log.warn(f"ProtocolLinkMessage with illegal sender-receiver pairing dropped! Message:{link_message}")
            return

        # get the underlying next hop id (0 if client, shell_id else)
        reciever_id: int = 0 if reciever_group_is_client else link_message.receiver.value
        
        message_type: MessageType = link_message.type
        if not reciever_id in self.sockets_by_id.keys(): # the receiver is unknown to the relay
            # Drop LTMswith unknown destination (should not happend, investigate warnings!)
            if message_type == MessageType.LTM:
                log.warn(f"LinkTerminationMessage to an unknown socket was dropped! Message:{link_message}")
                return
            # ShellRequestMessages might appear on the relay before the Shell registered itself
            # stage the SRM and handle on registration
            elif message_type == MessageType.SRM:
                if not isinstance(link_message, MessageShellRequest):
                    log.error(f"Message of type SRM was not MessageShellRequest!")
                    return
                if reciever_group_is_client:
                    log.warn(f"Shell({link_message.sender.value}) tried to send a ShellRequestMessage to the Client! Dropping! Message:{link_message}")
                    return

                if not link_message in self.requested_shells:
                    log.info(f"ShellRequestMessage staged. Shell({link_message.receiver.value}) is required to register now. Message:{link_message}")
                    self.requested_shells.append(link_message)
                else:
                    log.warn(f"ShellRequestMessage duplicate recieved! Message:{link_message}")
                return

            # Message to unknown receipient - send LTM
            log.warn(f"ProtocolLinkMessage with unknown receipient! Sending LTM! Message:{link_message}")
            self.write_to(link_message.sender,
                            MessageLinkTermination(
                            sender=link_message.receiver,
                            reciever=link_message.sender,
                            termination_type=TerminationType.ERROR,
                            termination_message=f"Reciever ID {reciever_id} of type {link_message.receiver.type} has no established connection!"
            ))
            return
        # ProtocolLinkMessage can be forwarded
        log.info(f"Relaying {link_message}")
        self.write(link_message)

    def __on_message_connect__(self, socket_handle: ServerConnectionHandle, connect_message: MessageConnect) -> None:
        peer_address: Address = connect_message.peer_id
        if peer_address.type == AddressType.DEVICE: # Only Shells and one Client allowed to connect
            log.error(f"Recieved MessageConnect from Device! - Devices should not open connections!")
            return
        
        self.__register_socket__(socket_handle, connect_message.peer_id.value)
        # send ack
        self.write_to(peer_address, MessageConnectAck())
        log.info(f"Registered {connect_message.peer_id.type} as ID {connect_message.peer_id.value}")

        for srm in self.requested_shells:
            if srm.receiver.value == connect_message.peer_id.value:
                self.write(srm)
                self.requested_shells.remove(srm)
                log.info(f"Sent staged SRM to {connect_message.peer_id}. Message:{srm}")
                break
    
    def __on_message_disconnect__(self, socket_handle: ServerConnectionHandle, disconnect_message: MessageDisconnect) -> None:
        if registered_id:= self.__get_registered_by_handle__(socket_handle):
            log.info(f"Unregistering SocketHandle from ID {registered_id}")
            self.__unregister_socket__(registered_id)
        else:
            log.warn(f"SocketHandle was not registered!")