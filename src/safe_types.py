from typing import Any

def is_list(data: Any) -> bool:
    return isinstance(data, list)

def is_str(data: Any) -> bool:
    return isinstance(data, str)

def str_is_int(data: str) -> bool:
    try:
        int(data)
        return True
    except:
        return False

def to_bytes(data: bytes | str) -> bytes:
    match data:
        case str():
            return data.encode()
        case bytes():
            return data
        case _:
            raise RuntimeError("to_bytes: data was of unsupported type: " + str(type(data)))
    
def to_str(data: bytes | str) -> str:
    match data:
        case str():
            return data
        case bytes():
            return data.decode()
        case _:
            raise RuntimeError("to_str: data was of unsupported type: " + str(type(data)))