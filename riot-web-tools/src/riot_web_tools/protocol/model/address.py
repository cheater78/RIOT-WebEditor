from __future__ import annotations
from abc import ABC
from riot_web_tools.protocol.model.pkgable_struct import *

class AddressType(StructTag):
    SHELL = "shell"
    CLIENT = "client"
    DEVICE = "device"

@smartdataclass
class Address(PkgableTaggedStruct[AddressType], ABC):
    
    @classmethod
    def is_client_side(cls) -> bool:
        return issubclass(cls, ClientAddress) or issubclass(cls, DeviceAddress)

@smartdataclass
class IDAddress(Address, ABC):
    id: int

@smartdataclass
class ClientAddress(IDAddress, tag=AddressType.CLIENT):
    id: int = 0

@smartdataclass
class ShellAddress(IDAddress, tag=AddressType.SHELL):
    id: int

@smartdataclass
class DeviceAddress(Address, tag=AddressType.DEVICE):
    device_name: str

__all__ = [
    "AddressType",
    "Address",
    "IDAddress",
    "ClientAddress",
    "ShellAddress",
    "DeviceAddress"
]