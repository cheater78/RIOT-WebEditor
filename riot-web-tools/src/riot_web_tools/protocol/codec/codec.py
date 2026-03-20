# pyright: reportMissingTypeStubs=false
import cbor2
from typing import Any, cast

from riot_web_tools.protocol.model.pkgable_struct import PakageType, Package
from riot_web_tools.protocol.model.message import Message

CodecType=bytes

def encode(message: Message) -> CodecType:
    packaged_message: Package = message.to_package()
    cbor_encoded_message: CodecType = cbor2.dumps(packaged_message)
    return cbor_encoded_message

def decode(encoded_message: CodecType) -> Message:
    raw_message: Any = cbor2.loads(encoded_message)
    if not isinstance(raw_message, PakageType):
        raise TypeError(f"Raw decoded Message was not of PakageType({PakageType.__name__})!")
    packaged_message: Package = cast(Package, raw_message)
    return Message.from_package(packaged_message)

__all__ = [
    "CodecType",
    "encode",
    "decode",
]