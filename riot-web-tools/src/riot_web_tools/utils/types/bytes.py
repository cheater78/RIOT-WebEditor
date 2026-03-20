from typing import Any

def to_bytes(data: Any) -> bytes:
    match data:
        case bytes():
            return data
        case str():
            return data.encode()
        # add non trivial conversions as needed
        case _:
            try:
                return bytes(data)
            except:
                raise

__all__ = ["to_bytes"]