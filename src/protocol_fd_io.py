from typing import Callable

import log
from fd_io import MUXFDIO, FDIO
import protocol
from protocol_message import ProtocolMessage

ProtocolCallbackFunc=Callable[[ProtocolMessage], None]
class ProtocolMUXFDIO:
    multiplexIO: MUXFDIO
    channel_id: int = 1
    on_protocol_callback: ProtocolCallbackFunc

    def __init__(self,
                 fdio: FDIO,
                 on_protocol_callback: ProtocolCallbackFunc) -> None:
        self.on_protocol_callback = on_protocol_callback
        self.multiplexIO = MUXFDIO(fdio)
        self.multiplexIO.setChannelCallbackFunction(self.channel_id, self.__on_raw_protocol_in__)

    def write(self, message: ProtocolMessage) -> None:
        raw: bytes = protocol.encode(message)
        self.multiplexIO.write_channel(self.channel_id, raw)

    def __on_raw_protocol_in__(self, message: bytes) -> None:
        unsafe_message: ProtocolMessage | None = protocol.decode(message)
        if not unsafe_message:
            log.error(f"FDProtocolIO.__on_raw_protocol_in__: Message could not be decoded!")
            return
        self.on_protocol_callback(unsafe_message)