import os
from enum import IntEnum
from riot_web_tools.utils.types.bytes import to_bytes

class ANSIColor(IntEnum):
    RESET = 0
    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37

def ansi_colorize(msg: str | bytes, color: ANSIColor) -> bytes:
    return to_bytes(f"\x1b[{color}m") + to_bytes(msg) + to_bytes(f"\x1b[{ANSIColor.RESET}m")

class Level(IntEnum):
    NONE = 0
    ERROR = 0
    WARN = 1
    INFO = 2
    TRACE = 3

log_level: Level = Level.ERROR
enable_asserts: bool = True # whether assert should stop execution

def __nl__(msg: bytes) -> bytes:
    msg = msg.replace(b"\n", b"\n\r")
    return msg + (b"" if msg.endswith(b"\n\r") or msg.endswith(b"\r\n") else b"\n\r")

def trace(log_msg: str | bytes) -> None:
    if log_level >= Level.TRACE:
        __write_std_consistent_nl__(ansi_colorize(b"[TRACE]: " + __nl__(to_bytes(log_msg)), ANSIColor.WHITE))

def info(log_msg: str | bytes) -> None:
    if log_level >= Level.INFO:
        __write_std_consistent_nl__(ansi_colorize(b"[INFO]: " + __nl__(to_bytes(log_msg)), ANSIColor.GREEN))

def info_ifn(condition: bool, log_msg: str | bytes) -> None:
    if log_level >= Level.INFO:
        if not condition:
            info(log_msg)

def warn(log_msg: str | bytes) -> None:
    if log_level >= Level.WARN:
        __write_std_consistent_nl__(ansi_colorize(b"[WARN]: " + __nl__(to_bytes(log_msg)), ANSIColor.YELLOW))
def warn_ifn(condition: bool, log_msg: str | bytes) -> None:
    if log_level >= Level.WARN:
        if not condition:
            warn(log_msg)

def error(log_msg: str | bytes) -> None:
    if log_level >= Level.ERROR:
        __write_std_consistent_nl__(ansi_colorize(b"[ERROR]: " + __nl__(to_bytes(log_msg)), ANSIColor.RED), stderr=True)

def error_ifn(condition: bool, log_msg: str | bytes) -> None:
    if log_level >= Level.ERROR:
        if not condition:
            error(log_msg)

def err_assert(condition: bool, log_msg: str | bytes) -> None:
    if log_level >= Level.ERROR:
        if not condition:
            error(log_msg)
            if enable_asserts:
                breakpoint()


def __write_std_consistent_nl__(msg: str | bytes, stderr: bool = False) -> None:
    if not hasattr(__write_std_consistent_nl__, "newlined_last"):
        setattr(__write_std_consistent_nl__, "newlined_last", True)

    message_bytes: bytes = to_bytes(msg)
    if getattr(__write_std_consistent_nl__, "newlined_last") or message_bytes.startswith(b"\n\r"):
        os.write(1 if not stderr else 2, message_bytes)
    else:
        os.write(1 if not stderr else 2, b"\n\r" + message_bytes)
    setattr(__write_std_consistent_nl__, "newlined_last", message_bytes.endswith(b"\n\r"))
