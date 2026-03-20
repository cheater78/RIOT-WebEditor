from __future__ import annotations
from dataclasses import dataclass, fields
from abc import ABC
from enum import Enum
from typing import Any, Type, get_type_hints, get_origin, cast

from riot_web_tools.utils.types.smart_struct import *
from riot_web_tools.utils.types.string import to_str

PakageType = list
Package = PakageType[Any]

def __pack__(data: Any) -> Any:
    if isinstance(data, PkgableTaggedStruct):
        return data.to_package()
    elif isinstance(data, Enum):
        return data.value
    # add packaged type representations as needed
    else:
        return data

def __unpack__(expected_type: type[Any], data: Any) -> Any:
    if issubclass(get_origin(expected_type) or expected_type, PkgableTaggedStruct):
        strong_expected_type: PkgableTaggedStruct[Any] = cast(PkgableTaggedStruct[Any], expected_type)
        if isinstance(data, PakageType):
            packaged_data: Package = cast(Package, data)
            return strong_expected_type.from_package(packaged_data)
        else:
            raise ValueError(f"Data provided for PkgableTaggedStruct field was not of PakageType({PakageType.__name__}), was Type: {type(data).__name__} instead!")
    # add further unpackaging strategies as needed
    try:
        # covers: Enum, int, str, bytes,.. -> basically just a validation step
        return expected_type(data)
    except:
        raise ValueError(f"Data provided for Type: {expected_type.__name__} field did not match, was Type: {type(data).__name__} with Value: {to_str(data)} instead!")

@smartdataclass
class PkgableTaggedStruct(TaggedSmartStruct[StructTagType], ABC):

    def to_package(self) -> Package:
        pkg: Package = [ __pack__(self._tag) ]

        for f in fields(self):
            v = getattr(self, f.name)
            v_pkg = __pack__(v)
            pkg.append(v_pkg)

        return pkg
    
    @classmethod
    def from_package(cls: Type[DomainRootClassType], pkg: Package) -> DomainRootClassType:
        if not pkg:
            raise ValueError("Empty package cannot be unpacked")
        tag_value = pkg[0]
        tag = __unpack__(cls._tag_type, tag_value) # will reconstruct the StructTagType Enum

        if tag not in cls._registry:
            raise ValueError(f"Tag({tag}) provided by packkage was not known in domain registry!")


        target_cls: Type[DomainRootClassType] = cls.registry_get(tag)
        target_cls_fields = fields(target_cls)
        target_cls_type_hints = get_type_hints(target_cls)
        
        values: list[Any] = []

        for f, v in zip(target_cls_fields, pkg[1:]): # skip tag at 0
            expected_type: type[Any] | None
            if isinstance(f.type, type):
                expected_type = f.type
            else:
                expected_type = target_cls_type_hints.get(f.name)
            
            if expected_type is not None and expected_type is not Any:
                v = __unpack__(expected_type, v)
            
            values.append(v)

        return target_cls(*values)

__all__ = ["Package", "PkgableTaggedStruct", "StructTag", "smartdataclass"]