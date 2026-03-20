from __future__ import annotations
from abc import ABC
from enum import Enum
from typing import Any, ClassVar, Generic, Type, TypeVar, get_origin, get_args, cast, Tuple, Dict

from riot_web_tools.utils.types.smart_class import SmartClass, smartdataclass

@smartdataclass
class SmartStruct(SmartClass, ABC):
    # optional: Add some safe guards, e.g. __dict__.keys immutability
    pass

StructTag = Enum
StructTagType = TypeVar("StructTagType", bound=StructTag)
DomainRootClassType = TypeVar("DomainRootClassType", bound="TaggedSmartStruct[Any]") # TaggedSmartStruct[Any] will always be TaggedSmartStruct[StructTagType]
TaggedStructRegistryType = dict[StructTag, type["TaggedSmartStruct[Any]"]]

def get_generic_fully_resolved(search_cls: Type[Any], generic_cls: Type[Any]) -> Tuple[Type[Any], ...] | None:
    if not hasattr(generic_cls, "__parameters__"):
        return () # generic_cls is not even generic -> fully resolved
    if not issubclass(search_cls, generic_cls):
        return None # search_cls is not subclass of generic_cls -> can never resolve
    
    # Map from TypeVar -> concrete type
    typevar_map: Dict[TypeVar, Any] = {}
    # prepare TypeVars we actually look for
    for param in getattr(generic_cls, "__parameters__"):
        typevar_map[param] = param

    # search classes bottom up to find the least derived,
    # but generically fully(all of generic_cls) defined class
    skip: bool = True
    for cls in reversed(getattr(search_cls, "__mro__")):
        # Skip ahead to one after generic_cls
        if skip:
            if cls is generic_cls:
                skip = False
            continue
        # iterate all generic base classes
        if not hasattr(search_cls, "__orig_bases__"):
            continue
        for base in getattr(search_cls, "__orig_bases__"):
            origin = get_origin(base) or base # base class type
            args = get_args(base) # specified base class variables

            if not args or not hasattr(origin, "__parameters__"):
                continue
            for param, arg in zip(getattr(origin, "__parameters__"), args):
                for gp, p in typevar_map.items():
                    if param == p:
                        typevar_map[gp] = arg
    
    for c in typevar_map.values():
        if isinstance(c, TypeVar):
            return None # if any TypeVar is still unresolved -> not resolved

    return tuple(typevar_map.get(param, param) for param in getattr(generic_cls, "__parameters__"))

@smartdataclass
class TaggedSmartStruct(Generic[StructTagType], SmartStruct, ABC):
    """
    Abstract base class for tagged structs,
    ought to be inherited by a domain root class,
    which then serves as a base class for domain specific specializations,
    all domain specific final specializations need to have their own unique StructTag value
    such a domain root class may look like:
        DomainTaggedStruct(TaggedSmartStruct[DomainStructTag], ABC)
    """
    _registry: ClassVar[TaggedStructRegistryType] # domain root class
    _tag_type: ClassVar[type[StructTag]] # domain root class
    _tag: ClassVar[StructTag] # final class

    def __init_subclass__(cls, *, tag: StructTag | None = None, **kwargs: dict[str, Any]):
        super().__init_subclass__(**kwargs)

        generic_args = get_generic_fully_resolved(cls, TaggedSmartStruct)
        generic_args_fully_resolved = generic_args != None

        # search for registry in parents, take the first
        # -> intermediary classes should already point down to the domain root class
        registry: TaggedStructRegistryType | None = None
        for base in cls.__mro__[1:]:
            if not issubclass(base, TaggedSmartStruct):
                break # this base class was reached
            strong_tagged_smart_struct: TaggedSmartStruct[Any] = cast(TaggedSmartStruct[Any], base)
            if hasattr(strong_tagged_smart_struct, "_registry"):
                registry = base._registry
                break

        # no parent registry -> infrastructure classes 
        if registry is None:
            if generic_args_fully_resolved:
                # this is the domain root, create registry
                cls._registry = {}
                cls._tag_type = generic_args[0]
            return

        # derived from domain root class -> just inherit registry from below
        cls._registry = registry

        # tag != None -> final class, register it into the registry
        if tag is not None:
            if tag in cls._registry:
                raise ValueError(f"Duplicate tag {tag} for {cls.__name__}")
            
            cls._tag = tag
            cls._registry[tag] = cls
    
    @classmethod
    def registry_get(cls: Type[DomainRootClassType], tag: StructTagType) -> Type[DomainRootClassType]:
        if tag not in cls._registry:
            raise KeyError(f"Unknown tag {tag} for {cls.__name__}")
        return cast(Type[DomainRootClassType], cls._registry[tag]) # __init_subclass__ should enforce this at RT
    
    @classmethod
    def tag(cls: Type[DomainRootClassType]) -> StructTagType:
        return cast(StructTagType, cls._tag) # __init_subclass__ should enforce this at RT

__all__ = ["SmartStruct", "StructTagType", "StructTag", "DomainRootClassType", "TaggedSmartStruct", "smartdataclass"]