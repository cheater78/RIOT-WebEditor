from abc import ABC, abstractmethod
from typing import Any

class Strable(ABC):
    @abstractmethod
    def __str__(self) -> str:
        pass 

def str_is_instance(data: str, type: type[Any]) -> bool:
    try:
        type(data)
        return True
    except:
        return False
    
def to_str(data: Any) -> str:
    match data:
        case str():
            return data
        case bytes():
            return data.decode()
        case strable if isinstance(data, Strable):
            return str(strable)
        case cls if isinstance(data, type):
            return cls.__name__
        # add non trivial conversions as needed
        case _:
            try:
                return str(data)
            except:
                return repr(data)

__all__ = ["Strable", "str_is_instance", "to_str"]