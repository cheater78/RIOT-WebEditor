# pyright: reportMissingTypeStubs=false
import cbor2
from typing import Callable

import log
from protocol_message import *

SocketMessageType = bytes
ProtocolCallbackFunc=Callable[[ProtocolMessage], None]

def encode(message: ProtocolMessage) -> SocketMessageType:
        structured_message: list[Any] = message.encode()
        cbor_encoded_message: SocketMessageType = cbor2.dumps(structured_message)
        # write to Socket
        return cbor_encoded_message

def decode(message: SocketMessageType) -> ProtocolMessage | None:
    raw_msg_obj: Any = cbor2.loads(message)
    if not is_list(raw_msg_obj):
        log.error(f"decode: raw_msg_obj was not a list!")
        return None
    raw_msg: list[Any] = raw_msg_obj

    # decode MessageType
    unsafe_message_type = MessageType.decode(raw_msg)
    if unsafe_message_type is None:
        log.error(f"decode: raw_msg did not have a valid MessageType!")
        return None
    
    if unsafe_message_type not in type_to_class.keys():
        log.error(f"decode: No registered ProtocolMessage class for MessageType {unsafe_message_type}!")
        return None
    
    message_cls = type_to_class[unsafe_message_type]
    msg = message_cls.decode(raw_msg)
    return msg