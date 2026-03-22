from abc import ABC
from enum import Enum

from riot_web_tools.protocol.model.pkgable_struct import *
from riot_web_tools.protocol.model.address import Address

class MessageType(StructTag):
    CONNECT =       "connect"
    CONNECT_ACK =   "connect ACK"
    DISCONNECT =    "disconnect"
    REQUEST =       "REQ"
    COMMAND =       "CMD"
    ACK =           "ACK"
    RESET =         "RST"
    LOG =           "LOG"
    IO =            "IO"

class LogType(Enum):
    ERROR = "error"
    LOG =   "log"

class TerminationType(Enum):
    SUCCESS =   "success"
    ERROR =     "error"

@smartdataclass
class Message(PkgableTaggedStruct[MessageType], ABC):
    pass

@smartdataclass
class LinkMessage(Message, ABC):
    sender: Address
    receiver: Address

# Final Classes
## Connection
@smartdataclass
class MessageConnect(Message, tag=MessageType.CONNECT):
    peer_id: Address

@smartdataclass
class MessageConnectAck(Message, tag=MessageType.CONNECT_ACK):
    pass

@smartdataclass
class MessageDisconnect(Message, tag=MessageType.DISCONNECT):
    pass

## Commands
class CommandType(StructTag):
    FLASH = "flash"
    TERM = "term"

### Request
@smartdataclass
class Request(PkgableTaggedStruct[CommandType], ABC):
    pass

@smartdataclass
class RequestBoardProject(Request):
    board: str
    project_path: str

@smartdataclass
class RequestFlash(RequestBoardProject, tag=CommandType.FLASH):
    pass

@smartdataclass
class RequestTerm(RequestBoardProject, tag=CommandType.TERM):
    pass

@smartdataclass
class MessageRequest(LinkMessage, tag=MessageType.REQUEST):
    spawned: bool
    request: Request

### Command
@smartdataclass
class Command(PkgableTaggedStruct[CommandType], ABC):
    pass

@smartdataclass
class CommandBoard(Command):
    board: str

@smartdataclass
class CommandFlash(CommandBoard, tag=CommandType.FLASH):
    binaries: dict[int, bytes]
    args: str

@smartdataclass
class CommandTerm(CommandBoard, tag=CommandType.TERM):
    baud_rate: int

@smartdataclass
class MessageCommand(LinkMessage, tag=MessageType.COMMAND):
    command: Command

### Response
@smartdataclass
class MessageACK(LinkMessage, tag=MessageType.ACK):
    pass

@smartdataclass
class MessageReset(LinkMessage, tag=MessageType.RESET):
    termination_type: TerminationType
    termination_message: str

@smartdataclass
class MessageLog(LinkMessage, tag=MessageType.LOG):
    log_type: LogType
    log_msg: str

@smartdataclass
class MessageIO(LinkMessage, tag=MessageType.IO):
    msg: bytes

__all__ = [
    "MessageType",
    "LogType",
    "TerminationType",

    "Message",
    "LinkMessage",

    "MessageConnect",
    "MessageConnectAck",
    "MessageDisconnect",

    "CommandType",
    "RequestFlash",
    "RequestTerm",
    "MessageRequest",
    "CommandFlash",
    "CommandTerm",
    "MessageCommand",

    "MessageACK",
    "MessageReset",

    "MessageLog",
    "MessageIO",
]