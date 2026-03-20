from __future__ import annotations
from abc import ABC
from dataclasses import dataclass
from typing import Any, TypeVar, dataclass_transform, Callable, cast

from .string import Strable, to_str

class SmartClass(Strable, ABC):

    @classmethod
    def class_attr_names(cls: type[SmartClass]) -> list[str]:
        """
        Return a list of class attribute names from cls and superclasses.
        """
        attrs: list[str] = []
        seen: set[str] = set()
        for c in reversed(cls.__mro__):
            if c is object:
                continue
            annotations: dict[str, Any] = getattr(c, '__annotations__', {})
            for name in annotations:
                if name not in seen:
                    attrs.append(name)
                    seen.add(name)
        return attrs

    def instance_attr_names(self) -> list[str]:
        """
        Return a list of instance attribute names.
        """
        return list(self.__dict__.keys())

    def __eq__(self, other: Any) -> bool:
        """
        Equality based on instance attributes only.
        Returns False if other is not the same type.
        """
        if not isinstance(other, self.__class__):
            return False
        for name in self.instance_attr_names():
            if getattr(self, name) != getattr(other, name):
                return False
        return True

    def __hash__(self) -> int:
        """
        Hash based on a tuple of instance attribute values.
        """
        values = tuple(getattr(self, name) for name in self.instance_attr_names())
        return hash(values)

    def __str__(self) -> str:
        """
        Return string representation using only instance attributes:
        ClassName(attr=value, ...)
        """
        attrs: list[str] = self.instance_attr_names()
        attr_strs: list[str] = [
            f"{name}={to_str(getattr(self, name))}" for name in attrs
        ]
        return f"{self.__class__.__name__}({', '.join(attr_strs)})"


DataClassType = TypeVar("DataClassType", bound=type)
@dataclass_transform(eq_default=True, frozen_default=True)
def smartdataclass(cls: DataClassType | None = None, **kwargs: Any) -> Callable[[DataClassType], DataClassType] | DataClassType:
    def wrap(c: DataClassType) -> DataClassType:
        return cast(DataClassType, dataclass(c, frozen=True, eq=True, **kwargs))

    return wrap(cls) if cls is not None else wrap

__all__ = ["SmartClass", "smartdataclass"]