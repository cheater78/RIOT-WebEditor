from __future__ import annotations
import inspect
from protocol_field_types import *
from typing import Any, Dict, cast

import log
from protocol_field_types import MessageType
from safe_types import is_str

# Message Base Classes
class ProtocolMessage:
    type: MessageType
    
    def __init__(self, type: MessageType) -> None:
        self.type = type

    def encode(self) -> list[Any]:
        return [self.type.encode()]

    @classmethod
    def _decode(cls, data: list[Any]) -> MessageType | None: # tuple omitted for simplicity
        return MessageType.decode(data)

    @classmethod
    def decode(cls, data: list[Any]) -> ProtocolMessage | None:
        usafe_type = cls._decode(data)
        if usafe_type is None:
            log.error(f"{cls.__name__}.decode: MessageType at data[0] was not valid!")
            return None
        return ProtocolMessage(usafe_type)
    
    @classmethod
    def field_count(cls):
        seen: set[Any] = set()
        for c in cls.__mro__:
            if c is object:
                continue

            for name, value in c.__dict__.items():
                if name.startswith("__"):
                    continue

                # exclude methods, classmethods, staticmethods, descriptors
                if inspect.isroutine(value):
                    continue
                if hasattr(value, "__get__"):
                    continue

                seen.add(name)

        return len(seen)
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type})"

class ProtocolLinkMessage(ProtocolMessage):
    sender: Address
    receiver: Address

    def __init__(self, type: MessageType, sender: Address, reciever: Address) -> None:
        super().__init__(type)
        self.sender = sender
        self.receiver = reciever

    @classmethod
    def _decode(cls, data: list[Any]) -> tuple[MessageType, Address, Address] | None: # pyright: ignore[reportIncompatibleMethodOverride]
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}._decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        unsafe_type = ProtocolMessage._decode(data)
        if unsafe_type is None:
            log.error(f"{cls.__name__}._decode: MessageType was not valid!")
            return None
        # MessageType is valid

        unsafe_sender = Address.decode(data[1])
        if unsafe_sender is None: 
            log.error(f"{cls.__name__}._decode: Field at data[1](sender) was not a valid Address! (was {str(data[1])})")
            return None
        # sender Address is valid

        unsafe_reciever = Address.decode(data[2])
        if unsafe_reciever is None: 
            log.error(f"{cls.__name__}._decode: Field at data[2](reciever) was not a valid Address! (was {str(data[1])})")
            return None
        # reciever Address is valid

        return (unsafe_type, unsafe_sender, unsafe_reciever)

    @classmethod
    def decode(cls, data: list[Any]) -> ProtocolLinkMessage | None:
        decoded = cls._decode(data)
        if decoded is None: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return ProtocolLinkMessage(*decoded)

    def encode(self) -> list[Any]:
        super_props: list[Any] = super().encode()
        super_props.extend([self.sender.encode(), self.receiver.encode()])
        return super_props
    
    def required_field_count(self) -> int:
        return self.field_count()
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver})"

class ProtocolLinkBoardMessage(ProtocolLinkMessage):
    board: str

    def __init__(self, type: MessageType, sender: Address, reciever: Address, board: str) -> None:
        super().__init__(type, sender, reciever)
        self.board = board

    @classmethod
    def _decode(cls, data: list[Any]) -> tuple[MessageType, Address, Address, str] | None: # pyright: ignore[reportIncompatibleMethodOverride]
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}._decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        decoded_base = ProtocolLinkMessage._decode(data)
        if decoded_base is None: 
            log.error(f"{cls.__name__}._decode: Failed to decode data as ProtocolLinkMessage!")
            return None
        
        if not is_str(data[3]):
            log.error(f"{cls.__name__}._decode: data[3](board) is not a str!")
            return None

        return (*decoded_base, data[3])

    @classmethod
    def decode(cls, data: list[Any]) -> ProtocolLinkBoardMessage | None:
        decoded = cls._decode(data)
        if decoded is None: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as ProtocolLinkBoardMessage!")
            return None
        return ProtocolLinkBoardMessage(*decoded)

    def encode(self) -> list[Any]:
        super_props: list[Any] = super().encode()
        super_props.extend([self.board])
        return super_props
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},board:{self.board})"


class ProtocolLinkBoardProjectMessage(ProtocolLinkBoardMessage):
    project_path: str

    def __init__(self, type: MessageType, sender: Address, reciever: Address, board: str, project_path: str) -> None:
        super().__init__(type, sender, reciever, board)
        self.project_path = project_path

    @classmethod
    def _decode(cls, data: list[Any]) -> tuple[MessageType, Address, Address, str, str] | None: # pyright: ignore[reportIncompatibleMethodOverride]
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}._decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        decoded_base = ProtocolLinkBoardMessage._decode(data)
        if decoded_base is None: 
            log.error(f"{cls.__name__}._decode: Failed to decode data as ProtocolLinkBoardMessage!")
            return None

        if not is_str(data[4]):
            log.error(f"{cls.__name__}._decode: data[4](project_path) is not a str!")
            return None

        return (*decoded_base, data[4])

    @classmethod
    def decode(cls, data: list[Any]) -> ProtocolLinkBoardProjectMessage | None:
        decoded = cls._decode(data)
        if decoded is None: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return ProtocolLinkBoardProjectMessage(*decoded)

    def encode(self) -> list[Any]:
        super_props: list[Any] = super().encode()
        super_props.extend([self.project_path])
        return super_props
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},board:{self.board},project_path:{self.project_path})"

class ProtocolLinkLogLikeMessage(ProtocolLinkMessage):
    log_type: LogType
    log_msg: str

    def __init__(self, type: MessageType, sender: Address, reciever: Address, log_type: LogType, log_msg: str) -> None:
        super().__init__(type, sender, reciever)
        self.log_type = log_type
        self.log_msg = log_msg

    @classmethod
    def _decode(cls, data: list[Any]) -> tuple[MessageType, Address, Address, LogType, str] | None: # pyright: ignore[reportIncompatibleMethodOverride]
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}._decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        decoded_base = ProtocolLinkMessage._decode(data)
        if decoded_base is None: 
            log.error(f"{cls.__name__}._decode: Failed to decode data as {ProtocolLinkMessage.__name__}!")
            return None
        
        log_type = LogType.decode(data[3])
        if log_type is None: 
            log.error(f"{cls.__name__}._decode: Failed to decode data[3] as {LogType.__name__}!")
            return None
        
        if not is_str(data[4]):
            log.error(f"{cls.__name__}._decode: data[4] is not a str!")
            return None

        return (*decoded_base, log_type, data[4])

    @classmethod
    def decode(cls, data: list[Any]) -> ProtocolLinkLogLikeMessage | None:
        decoded = cls._decode(data)
        if decoded is None: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return ProtocolLinkLogLikeMessage(*decoded)

    def encode(self) -> list[Any]:
        super_props: list[Any] = super().encode()
        super_props.extend([self.log_type.encode(), self.log_msg])
        return super_props
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},log_type:{self.log_type},log_msg:{self.log_msg})"

# Message Classes
class MessageConnect(ProtocolMessage):
    peer_id: Address

    def __init__(self, peer_id: Address) -> None:
        super().__init__(MessageType.CONNECT)
        self.peer_id = peer_id

    @classmethod
    def decode(cls, data: list[Any]) -> MessageConnect | None:
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}.decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        unsafe_type = ProtocolMessage._decode(data)
        if unsafe_type is None:
            log.error(f"{cls.__name__}.decode: MessageType was not valid!")
            return None
        if unsafe_type is not MessageType.CONNECT:
            log.error(f"{cls.__name__}.decode: MessageType at data[0] was not MessageType.CONNECT! (was {str(unsafe_type)})")
            return None
        # MessageType is correct -> not needed anymore

        usafe_peer_id = Address.decode(data[1])
        if usafe_peer_id is None: 
            log.error(f"{cls.__name__}.decode: Field at data[1] was not a valid Address! (was {str(data[1])})")
            return None
        # Address is valid
        return MessageConnect(usafe_peer_id)
        
    def encode(self) -> list[Any]:
        super_props: list[Any] = super().encode()
        super_props.extend([self.peer_id.encode()])
        return super_props
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},peer_id:{self.peer_id})"

class MessageConnectAck(ProtocolMessage):
    def __init__(self) -> None:
        super().__init__(MessageType.CONNECT_ACK)
    
    @classmethod
    def decode(cls, data: list[Any]) -> MessageConnectAck | None:
        decoded = cls._decode(data)
        if decoded is None or decoded is not MessageType.CONNECT_ACK: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageConnectAck()
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type})"

class MessageDisconnect(ProtocolMessage):
    def __init__(self) -> None:
        super().__init__(MessageType.DISCONNECT)
    
    @classmethod
    def decode(cls, data: list[Any]) -> MessageDisconnect | None:
        decoded = cls._decode(data)
        if decoded is None or decoded is not MessageType.DISCONNECT: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageDisconnect()
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type})"

class MessageDNRRequest(ProtocolMessage):
    sender: Address
    device_name: str
    
    def __init__(self, sender: Address, device_name: str) -> None:
        super().__init__(MessageType.DNR)
        self.sender = sender
        self.device_name = device_name

    @classmethod
    def decode(cls, data: list[Any]) -> MessageDNRRequest | None:
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}.decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        unsafe_type = ProtocolMessage._decode(data)
        if unsafe_type is None:
            log.error(f"{cls.__name__}.decode: MessageType was not valid!")
            return None
        if unsafe_type is not MessageType.DNR:
            log.error(f"{cls.__name__}.decode: MessageType at data[0] was not MessageType.DNR! (was {str(unsafe_type)})")
            return None
        # MessageType is correct -> not needed anymore

        unsafe_sender = Address.decode(data[1])
        if unsafe_sender is None: 
            log.error(f"{cls.__name__}.decode: Field at data[1](sender) was not a valid Address! (was {str(data[1])})")
            return None
        # sender Address is valid

        if not is_str(data[2]):
            log.error(f"{cls.__name__}.decode: Field at data[2](device_name) was not a str! (was {type(data[1])})")
            return None
        device_name: str = data[2]
        # device_name is str

        return MessageDNRRequest(unsafe_sender, device_name)

    def encode(self) -> list[Any]:
        super_props: list[Any] = super().encode()
        super_props.extend([self.sender.encode(), self.device_name])
        return super_props
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},device_name:{self.device_name})"

class MessageDNRAck(ProtocolLinkMessage):
    def __init__(self, sender: Address, reciever: Address) -> None:
        super().__init__(MessageType.DNR_ACK, sender, reciever)

    @classmethod
    def decode(cls, data: list[Any]) -> MessageDNRAck | None:
        decoded = cls._decode(data)
        if decoded is None or decoded[0] is not MessageType.DNR_ACK: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageDNRAck(*decoded[1:]) # Skip MessageType
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver})"

class MessageShellRequest(ProtocolLinkMessage):
    def __init__(self, sender: Address, reciever: Address) -> None:
        super().__init__(MessageType.SRM, sender, reciever)

    @classmethod
    def decode(cls, data: list[Any]) -> MessageShellRequest | None:
        decoded = cls._decode(data)
        if decoded is None or decoded[0] is not MessageType.SRM: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageShellRequest(*decoded[1:]) # Skip MessageType
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver})"

class MessageShellRequestAck(ProtocolLinkMessage):
    def __init__(self, sender: Address, reciever: Address) -> None:
        super().__init__(MessageType.SRM_ACK, sender, reciever)
    
    @classmethod
    def decode(cls, data: list[Any]) -> MessageShellRequestAck | None:
        decoded = cls._decode(data)
        if decoded is None or decoded[0] is not MessageType.SRM_ACK: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageShellRequestAck(*decoded[1:]) # Skip MessageType
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver})"

class MessageLinkTermination(ProtocolLinkMessage):
    termination_type: TerminationType
    termination_message: str

    def __init__(self, sender: Address, reciever: Address, termination_type: TerminationType, termination_message: str) -> None:
        super().__init__(MessageType.LTM, sender, reciever)
        self.termination_type = termination_type
        self.termination_message = termination_message

    @classmethod
    def _decode(cls, data: list[Any]) -> tuple[MessageType, Address, Address, TerminationType, str] | None: # pyright: ignore[reportIncompatibleMethodOverride]
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}._decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        decoded_base = ProtocolLinkMessage._decode(data)
        if decoded_base is None: 
            log.error(f"{cls.__name__}._decode: Failed to decode data as {ProtocolLinkMessage.__name__}!")
            return None
        
        termination_type = TerminationType.decode(data[3])
        if termination_type is None: 
            log.error(f"{cls.__name__}._decode: Failed to decode data[3] as {TerminationType.__name__}!")
            return None
        
        if not is_str(data[4]):
            log.error(f"{cls.__name__}._decode: data[4] is not a str!")
            return None

        return (*decoded_base, termination_type, data[4])

    @classmethod
    def decode(cls, data: list[Any]) -> MessageLinkTermination | None:
        decoded = cls._decode(data)
        if decoded is None or decoded[0] is not MessageType.LTM: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return cls(*decoded[1:]) # Skip MessageType
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},termination_type:{self.termination_type},termination_message:{self.termination_message})"

class MessageFlash(ProtocolLinkBoardMessage):
    binaries: dict[int, bytes]
    args: str

    def __init__(self, sender: Address, reciever: Address, board: str, binaries: dict[int, bytes], args: str) -> None:
        super().__init__(MessageType.FLASH, sender, reciever, board)
        self.binaries = binaries
        self.args = args

    @classmethod
    def _decode(cls, data: list[Any]) -> tuple[MessageType, Address, Address, str, dict[int, bytes], str] | None: # pyright: ignore[reportIncompatibleMethodOverride]
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}._decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        decoded_base = ProtocolLinkBoardMessage._decode(data)
        if decoded_base is None: 
            log.error(f"{cls.__name__}._decode: Failed to decode data as ProtocolLinkBoardMessage!")
            return None
        
        if not isinstance(data[4], dict) or not all(isinstance(k, int) and isinstance(v, bytes) for k, v in data[4].items()): # type: ignore
            log.error(f"{cls.__name__}._decode: data[4](binaries) is not a dict[int, bytes]!")
            return None
        data[4] = cast(Dict[int, bytes], data[4])

        if not is_str(data[5]):
            log.error(f"{cls.__name__}._decode: data[5](args) is not a str!")
            return None

        return (*decoded_base, data[4], data[5])

    @classmethod
    def decode(cls, data: list[Any]) -> MessageFlash | None:
        decoded = cls._decode(data)
        if decoded is None: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageFlash(*decoded[1:]) # Skip MessageType

    def encode(self) -> list[Any]:
        super_props: list[Any] = super().encode()
        super_props.extend([self.binaries, self.args])
        return super_props
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},board:{self.board},binaries:{self.binaries},args:{self.args})"

class MessageFlashRequest(ProtocolLinkBoardProjectMessage):
    def __init__(self, sender: Address, reciever: Address, board: str, project_path: str) -> None:
        super().__init__(MessageType.FLASH_REQUEST, sender, reciever, board, project_path)

    @classmethod
    def decode(cls, data: list[Any]) -> MessageFlashRequest | None:
        decoded = cls._decode(data)
        if decoded is None or decoded[0] is not MessageType.FLASH_REQUEST: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageFlashRequest(*decoded[1:]) # Skip MessageType
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},board:{self.board},project_path:{self.project_path})"

class MessageTerm(ProtocolLinkBoardMessage):
    baud_rate: int

    def __init__(self, sender: Address, reciever: Address, board: str, baud_rate: int) -> None:
        super().__init__(MessageType.TERM, sender, reciever, board)
        self.baud_rate = baud_rate

    @classmethod
    def _decode(cls, data: list[Any]) -> tuple[MessageType, Address, Address, str, int] | None: # pyright: ignore[reportIncompatibleMethodOverride]
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}._decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        decoded_base = ProtocolLinkBoardMessage._decode(data)
        if decoded_base is None: 
            log.error(f"{cls.__name__}._decode: Failed to decode data as ProtocolLinkBoardMessage!")
            return None
        
        if type(data[4]) is not int:
            log.error(f"{cls.__name__}._decode: data[4](baud_rate) is not an int!")
            return None

        return (*decoded_base, data[4])

    @classmethod
    def decode(cls, data: list[Any]) -> MessageTerm | None:
        decoded = cls._decode(data)
        if decoded is None: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageTerm(*decoded[1:]) # Skip MessageType

    def encode(self) -> list[Any]:
        super_props: list[Any] = super().encode()
        super_props.extend([self.baud_rate])
        return super_props
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},board:{self.board},baud_rate:{self.baud_rate})"

class MessageTermRequest(ProtocolLinkBoardProjectMessage):
    def __init__(self, sender: Address, reciever: Address, board: str, project_path: str) -> None:
        super().__init__(MessageType.TERM_REQUEST, sender, reciever, board, project_path)

    @classmethod
    def decode(cls, data: list[Any]) -> MessageTermRequest | None:
        decoded = cls._decode(data)
        if decoded is None or decoded[0] is not MessageType.TERM_REQUEST: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageTermRequest(*decoded[1:]) # Skip MessageType
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},board:{self.board},project_path:{self.project_path})"

class MessageLog(ProtocolLinkLogLikeMessage):
    def __init__(self, sender: Address, reciever: Address, log_type: LogType, log_msg: str) -> None:
        super().__init__(MessageType.LOG, sender, reciever, log_type, log_msg)

    @classmethod
    def decode(cls, data: list[Any]) -> ProtocolLinkLogLikeMessage | None:
        decoded = cls._decode(data)
        if decoded is None or decoded[0] is not MessageType.LOG: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageLog(*decoded[1:]) # Skip MessageType
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},log_type:{self.log_type},log_msg:{self.log_msg})"

class MessageInput(ProtocolLinkMessage):
    input_msg: str

    def __init__(self, sender: Address, reciever: Address, input_msg: str) -> None:
        super().__init__(MessageType.INPUT, sender, reciever)
        self.input_msg = input_msg

    @classmethod
    def _decode(cls, data: list[Any]) -> tuple[MessageType, Address, Address, str] | None: # pyright: ignore[reportIncompatibleMethodOverride]
        if len(data) < cls.field_count():
            log.error(f"{cls.__name__}._decode: data was size {len(data)}! (requires >={cls.field_count()})")
            return None
        decoded_base = ProtocolLinkMessage._decode(data)
        if decoded_base is None: 
            log.error(f"{cls.__name__}._decode: Failed to decode data as ProtocolLinkMessage!")
            return None
        
        if not is_str(data[3]):
            log.error(f"{cls.__name__}._decode: data[3](input_msg) is not a str!")
            return None

        return (*decoded_base, data[3])

    @classmethod
    def decode(cls, data: list[Any]) -> MessageInput | None:
        decoded = cls._decode(data)
        if decoded is None: 
            log.error(f"{cls.__name__}.decode: Failed to decode data as {cls.__name__}!")
            return None
        return MessageInput(*decoded[1:]) # Skip MessageType

    def encode(self) -> list[Any]:
        super_props: list[Any] = super().encode()
        super_props.extend([self.input_msg])
        return super_props
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}:(type:{self.type},sender:{self.sender},reciever:{self.receiver},input_msg:{self.input_msg})"



type_to_class: dict[MessageType, type[ProtocolMessage]] = {
    MessageType.CONNECT: MessageConnect,
    MessageType.CONNECT_ACK: MessageConnectAck,
    MessageType.DISCONNECT: MessageDisconnect,
    MessageType.DNR: MessageDNRRequest,
    MessageType.DNR_ACK: MessageDNRAck,
    MessageType.SRM: MessageShellRequest,
    MessageType.SRM_ACK: MessageShellRequestAck,
    MessageType.LTM: MessageLinkTermination,
    MessageType.FLASH: MessageFlash,
    MessageType.FLASH_REQUEST: MessageFlashRequest,
    MessageType.TERM: MessageTerm,
    MessageType.TERM_REQUEST: MessageTermRequest,
    MessageType.LOG: MessageLog,
    MessageType.INPUT: MessageInput,
    # Extend as needed
}

def get_message_class(message_type: MessageType) -> type[ProtocolMessage] | None:
    if message_type in type_to_class:
        return type_to_class[message_type]
    return None
