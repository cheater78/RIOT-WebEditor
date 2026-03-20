from __future__ import annotations
import asyncio
import termios, tty, fcntl, signal
import struct
from typing import Any, Callable
from enum import Enum

from .fd_io import FDIO, STDIO, AsyncFDReader, FDWriter, FDCallbackFunc, FDMessageType

class TTYActionRaw(Enum):
    MOVE_START = b"\x01"    # Ctrl-A
    MOVE_END = b"\x05"      # Ctrl-E
    DELETE_BEFORE = b"\x15" # Ctrl-U
    DELETE_AFTER = b"\x0b"  # Ctrl-K
    RETURN = b"\r"          # Return
    CANCEL = b"\x03"        # Ctrl-C
    EOF = b"\x04"           # Ctrl-D

    def __bytes__(self) -> bytes:
        return self.value
    
    def __add__(self, other: TTYActionRaw | bytes) -> bytes:
        return bytes(self) + bytes(other)
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, TTYActionRaw):
            return Enum.__eq__(self, other)
        elif isinstance(other, int):
            return int.from_bytes(self.value, byteorder='big') == other
        else:
            return NotImplemented

TTYWindowResizeCallbackFunc = Callable[[int, int], None]
class TTYRawIO(STDIO):
    # original_attr: termios._AttrReturn
    _reformat_output: bool

    @staticmethod
    def replace_raw_newline(data: bytes) -> bytes:
        return data.replace(b"\n", b"\n\r")

    def __init__(self,
                    stdin_callback: FDCallbackFunc,
                    on_tty_win_resize: TTYWindowResizeCallbackFunc,
                    reformat_output: bool = False,
                    event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        # STDIO setup
        super().__init__(stdin_callback, event_loop)
        self._reformat_output = reformat_output

        # store orinial tty attributes
        self.original_attr = termios.tcgetattr(self.stdin.fd)
        # make tty raw - no input handling (passing raw bytes)
        tty.setraw(self.stdin.fd)

        # register tty window resize callback
        def sigwinch_handler(signum, frame) -> None: # type: ignore
            on_tty_win_resize(*self.get_window_size())
        signal.signal(signal.SIGWINCH, sigwinch_handler) # type: ignore

    def write(self, data: FDMessageType) -> None:
        super().write(self.replace_raw_newline(data) if self._reformat_output else data)

    def error(self, data: FDMessageType) -> None:
        super().write(self.replace_raw_newline(data) if self._reformat_output else data)

    def close(self) -> None:
        # restore orinial tty attributes
        termios.tcsetattr(self.stdin.fd, termios.TCSADRAIN, self.original_attr)

    def get_window_size(self) -> tuple[int, int]:
        data = fcntl.ioctl(self.stdin.fd, termios.TIOCGWINSZ, b"\x00" * 8)
        rows, cols, _, _ = struct.unpack("HHHH", data)
        return rows, cols

class PTYMasterIO(FDIO):
    master_fd: int
    pty_in: FDWriter
    pty_out: AsyncFDReader

    def __init__(self,
                 master_pty_fd: int,
                 pty_out_callback: FDCallbackFunc,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self.master_fd = master_pty_fd
        self.pty_in = FDWriter(self.master_fd)
        self.pty_out = AsyncFDReader(self.master_fd, pty_out_callback, event_loop)
    
    def write(self, data: FDMessageType) -> None:
        self.pty_in.write(data)

    def setCallbackFunction(self, callback: FDCallbackFunc) -> None:
        self.pty_out.fd_callback = callback

    def getCallbackFunction(self) -> FDCallbackFunc:
        return self.pty_out.fd_callback
    
    def set_window_size(self, rows: int, cols: int) -> None:
        fcntl.ioctl(
            self.master_fd,
            termios.TIOCSWINSZ,
            struct.pack("HHHH", rows, cols, 0, 0),
        )