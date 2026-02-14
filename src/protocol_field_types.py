from __future__ import annotations
from typing import Any
from enum import Enum
import log
from safe_types import is_list

class MessageType(Enum):
    CONNECT = "connect"
    CONNECT_ACK = "connect ACK"
    DISCONNECT = "disconnet"
    DNR = "DNR"
    DNR_ACK = "DNR ACK"
    SRM = "SRM"
    SRM_ACK = "SRM ACK"
    LTM = "LTM"
    FLASH = "flash"
    FLASH_REQUEST = "flash request"
    TERM = "term"
    TERM_REQUEST = "term request"
    LOG = "log"
    INPUT = "input"

    def encode(self) -> str:
        return str(self.value)

    @staticmethod
    def decode(data: list[Any]) -> MessageType | None: # taking a list[Any] may seem odd, but its main use is for raw messages (use [str] else)
        if len(data) < 1:
            log.error(f"MessageType.decode: data was size {len(data)}! (requires >=1)")
            return None
        if not isinstance(data[0], str):
            log.error(f"MessageType.decode: data[0] was not str!")
            return None
        try:
            return MessageType(data[0])
        except ValueError:
            log.error(f"MessageType.decode: data was not a valid MessageType! (was {str(data[0])})")
        except:
            log.error(f"MessageType.decode: A non ValueError occured (very bad)! (was {str(data[0])})")
        return None

class AddressType(Enum):
    SHELL = "shell"
    DEVICE = "device"
    CLIENT = "client"

    def encode(self) -> str:
        return str(self.value)

    @staticmethod
    def decode(data: list[Any]) -> AddressType | None: # taking a list[Any] may seem odd, but its main use is for raw addresses (use [str] else)
        if len(data) < 1:
            log.error(f"AdressType.decode: data was size {len(data)}! (requires >=1)")
            return None
        if not isinstance(data[0], str):
            log.error(f"AdressType.decode: data[0] was not str!")
            return None
        try:
            return AddressType(data[0])
        except ValueError:
            log.error(f"AdressType.decode: data was not a valid AdressType! (was {str(data[0])})")
        except:
            log.error(f"AdressType.decode: A non ValueError occured (very bad)! (was {str(data[0])})")
        return None

class Address():
    type: AddressType
    value: int

    def __init__(self, type: AddressType, value: int) -> None:
        self.type = type
        self.value = value

    def encode(self) -> list[Any]:
        return [self.type.encode(), self.value]

    @staticmethod
    def decode(data: Any) -> Address | None:
        if not is_list(data):
            log.error(f"Address.decode: data was not a list! (was {type(data)})")
            return None
        if len(data) != 2:
            log.error(f"Address.decode: data was size {len(data)}! (requires ==2)")
            return None
        unsafe_address_type = AddressType.decode(data)
        if unsafe_address_type is None:
            log.error(f"Address.decode: data[0] was not a valid AdressType! (was {data[0]})")
            return None
        # AdressType at data[0] is valid
        if not isinstance(data[1], int):
            log.error(f"Address.decode: data[1] was not type int! (was {type(data[1])})")
            return None
        # AdressValue at data[1] is valid
        return Address(unsafe_address_type, data[1])
    
         

class LogType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    LOG = "log"

    def encode(self) -> str:
        return str(self.value)

    @staticmethod
    def decode(data: str) -> LogType | None:
        try:
            return LogType(data)
        except ValueError:
            return None
