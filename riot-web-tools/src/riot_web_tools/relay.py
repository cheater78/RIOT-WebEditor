#!/usr/bin/env python3
import asyncio
from typing import cast

from riot_web_tools.utils import log
from riot_web_tools.protocol import *

class Relay:
    socket_server: ProtocolAsyncRemoteSocketServer
    requested_shells: dict[IDAddress, MessageRequest]

    def __init__(self) -> None:
        self.event_loop = asyncio.new_event_loop()
        self.socket_server = ProtocolAsyncRemoteSocketServer(
            self.__on_protocol_link_message__,
            self.__on_protocol_connection_established__,
            event_loop=self.event_loop
        )
        self.requested_shells = {}
    
    def run(self) -> None:
        log.info(">Starting event loop...")
        self.event_loop.run_forever()
        log.warn(">Event loop stopped!")

    def __on_protocol_connection_established__(self, peer_id: IDAddress) -> None:
        if isinstance(peer_id, ClientAddress):
            for established in self.socket_server.get_established():
                if isinstance(established, ShellAddress):
                    self.socket_server.write_link(MessageReset(peer_id, established, TerminationType.ERROR, "Client reconnected!"))
            self.requested_shells.clear()
            return
        if not peer_id in self.requested_shells.keys():
            return
        log.info(f"Relaying RequestMessage after Shell connection has been established!")
        self.socket_server.write_link(self.requested_shells[peer_id])
        del self.requested_shells[peer_id]

    def __on_protocol_link_message__(self, link_message: LinkMessage) -> None:
        # Drop illegal sender-receiver paired message (device|client to device|client or shell to shell)
        sender_group_is_client: bool = link_message.sender.is_client_side()
        reciever_group_is_client: bool = link_message.receiver.is_client_side()
        if sender_group_is_client == reciever_group_is_client:
            log.warn(f"ProtocolLinkMessage with illegal sender-receiver pairing dropped! Message:{link_message}")
            return

        # get the underlying next hop id (0 if client, shell_id else)
        reciever_addr: IDAddress = ClientAddress() if reciever_group_is_client else cast(ShellAddress, link_message.receiver)
        
        if not self.socket_server.is_established(reciever_addr): # the receiver is unknown to the relay
            match(link_message):
                case MessageReset() as rst:
                    log.warn(f"MessageReset to an unknown socket was dropped! Message:{rst}")
                    return
                case MessageRequest() as req:
                    if reciever_group_is_client:
                        log.warn(f"{link_message.sender} tried to send a MessageRequest to the Client! Dropping! Message:{req}")
                        return
                    if req in self.requested_shells.values():
                        log.warn(f"MessageRequest duplicate recieved! Dropping Message:{link_message}")
                        return
                    if not req.spawned:
                        log.info(f"MessageRequest received from {req.sender} but Shell is dead. Message:{req}")
                        self.socket_server.write_link(
                            MessageReset(
                                sender=link_message.receiver,
                                receiver=link_message.sender,
                                termination_type=TerminationType.ERROR,
                                termination_message=f"Shell with {reciever_addr} is dead!"
                            ))
                        return
                    log.info(f"MessageRequest staged. {req.receiver} is required to register now. Message:{req}")
                    self.requested_shells[reciever_addr] = req
                    # NOTE: crude timeout impl! - clean up if needed
                    async def timeout_worker():
                        await asyncio.sleep(3)
                        if reciever_addr in self.requested_shells.keys():
                            log.warn(f"MessageRequest was not send! Shell did not register! {req}")
                            del self.requested_shells[reciever_addr]
                    self.event_loop.create_task(timeout_worker())

                    return
                case _:
                    # Message to unknown receipient - send LTM
                    log.warn(f"ProtocolLinkMessage with unknown receipient: {reciever_addr}! Sending LTM! Message:{link_message}")
                    self.socket_server.write_link(
                        MessageReset(
                            sender=link_message.receiver,
                            receiver=link_message.sender,
                            termination_type=TerminationType.ERROR,
                            termination_message=f"Reciever {reciever_addr} has no established connection to relay!"
                        ))
                    return
        # ProtocolLinkMessage can be forwarded
        log.info(f"Relaying {link_message}")
        self.socket_server.write_link(link_message)

relay = Relay()
relay.run()