
from abc import abstractmethod
import asyncio
import os, sys, select, errno
import struct
from typing import Callable

FDMessageType = bytes
FDCallbackFunc = Callable[[FDMessageType], None]

class AsyncFDReader:
    """
    Asyncio reader for a FD.
    Calls fd_callback whenever new data is available.
    FD is made non-blocking!
    """
    fd: int
    fd_callback: FDCallbackFunc
    _event_loop: asyncio.AbstractEventLoop

    def __init__(self,
                 fd: int,
                 fd_callback: FDCallbackFunc,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self.fd  = fd
        self.fd_callback = fd_callback
        self._event_loop = event_loop

        self._event_loop.add_reader(self.fd, self.__read__)

    def stop(self) -> None:
        self._event_loop.remove_reader(self.fd)

    def __read__(self) -> None:
        # asyncio reader, ensures that, there is data available
        data: FDMessageType = FDMessageType()
        try:
            # Danger: blocks if empty
            data += os.read(self.fd, 4096)
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                # only if FD is non-blocking, we can save a misscall
                return
            elif e.errno == errno.EIO:
                # fd closed
                self.stop()
                self.fd_callback(b"")
                return
            else:
                # something actually went wrong
                raise
            
        # Forward to handler (data in bytes or empty if EOF)
        if not data: # EOF
            self.stop()
            self.fd_callback(b"")
        else:
            self.fd_callback(data)
    
class FDWriter:
    fd: int

    def __init__(self, fd: int):
        self.fd = fd

    def write(self, data: FDMessageType) -> None:
        total_written = 0
        length = len(data)

        while total_written < length:
            try:
                n = os.write(self.fd, data[total_written:])
                if n == 0: # non blocking fd buffer is full and accepts no bytes
                    self.__wait_ready_write__()
                total_written += n
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    # for non-blocking fds -> block ourselves and retry
                    self.__wait_ready_write__()
                    continue
                elif e.errno == errno.EINTR:
                    # interrupted by signal, retry
                    continue
                else:
                    raise
            
    def __wait_ready_write__(self) -> bool:
        return bool(select.select([], [self.fd], [])[1])

class FDIO:
    @abstractmethod
    def write(self, data: FDMessageType) -> None:
        pass

    @abstractmethod
    def setCallbackFunction(self, callback: FDCallbackFunc) -> None:
        pass

    @abstractmethod
    def getCallbackFunction(self) -> FDCallbackFunc:
        pass

class STDIO(FDIO):
    stdin: AsyncFDReader
    stdout: FDWriter
    stderr: FDWriter
    
    def __init__(self,
                 stdin_callback: FDCallbackFunc,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self.stdin = AsyncFDReader(sys.stdin.fileno(), stdin_callback, event_loop)
        self.stdout = FDWriter(sys.stdout.fileno())
        self.stderr = FDWriter(sys.stderr.fileno())

    def write(self, data: FDMessageType) -> None:
        self.stdout.write(data)

    def error(self, data: FDMessageType) -> None:
        self.stderr.write(data)

    def setCallbackFunction(self, callback: FDCallbackFunc) -> None:
        self.stdin.fd_callback = callback

    def getCallbackFunction(self) -> FDCallbackFunc:
        return self.stdin.fd_callback

class MUXFDIO(FDIO):
    """
    consumes a FDIO handle and provides multiple channels, while keeping raw FDIO communication
    channels are identified by id: int

    should be used on both ends of the FDIO connection
    """
    fdio: FDIO
    on_raw_input: FDCallbackFunc
    on_channel_input: dict[int, FDCallbackFunc]

    header_magic_delimiter: bytes = b""
    header_format: str = ""
    header_size: int = 0

    header_magic_pos_found: int = 0
    header_buffer: bytearray = bytearray()
    header_to_read: int = 0

    active_channel: int = 0
    active_channel_buffer: bytearray = bytearray()
    active_channel_buget: int = 0
    pos: int = 0

    def __init__(self, fdio: FDIO) -> None:
        self.fdio = fdio
        self.on_raw_input = self.fdio.getCallbackFunction()
        self.fdio.setCallbackFunction(self.__on_raw_fdin__)
        self.on_channel_input = {}

        self.header_magic_delimiter = b"RIOTWebMultiplexFDIO"
        self.header_format = f">{len(self.header_magic_delimiter)}sBI"
        self.header_size = struct.calcsize(self.header_format)

        self.header_magic_check_next = 0
        self.header_buffer = bytearray()
        self.header_to_read: int = 0

        self.active_channel = 0
        self.active_channel_buffer = bytearray()
        self.active_channel_buget = 0
    
    def write(self, data: FDMessageType) -> None:
        self.fdio.write(data)

    def write_channel(self, channel: int, data: FDMessageType) -> None:
        header = struct.pack(self.header_format, self.header_magic_delimiter, channel, len(data))
        self.write(header + data)

    def setChannelCallbackFunction(self, channel: int, callback: FDCallbackFunc) -> None:
        self.on_channel_input[channel] = callback

    def getChannelCallbackFunction(self, channel: int) -> FDCallbackFunc | None:
        return self.on_channel_input.get(channel)

    def setCallbackFunction(self, callback: FDCallbackFunc) -> None:
        self.on_raw_input = callback

    def getCallbackFunction(self) -> FDCallbackFunc:
        return self.on_raw_input
    
    def __on_raw_fdin__(self, message: bytes) -> None:
        raw_out: bytearray = bytearray()
        for b in message:
            # actively reading channel data
            if self.active_channel != 0 and self.active_channel_buget > 0:
                self.active_channel_buffer.append(b)
                self.active_channel_buget -= 1

                if self.active_channel_buget <= 0:
                    unsafe_callback = self.on_channel_input.get(self.active_channel)
                    if unsafe_callback is not None:
                        unsafe_callback(self.active_channel_buffer)
                        self.active_channel = 0
                        self.active_channel_buffer.clear()
                        self.active_channel_buget = 0
                continue

            # header was found already - read the rest(=self.header_to_read)
            if self.header_to_read > 0:
                self.header_buffer.append(b)
                self.header_to_read -= 1

                if self.header_to_read <= 0:
                    # all the header has been read
                    _, channel, length = struct.unpack(self.header_format, self.header_buffer)
                    if channel == 0 or length == 0:
                        raise TypeError(f"MultiplexIO encoding was broken! channel:{channel}, length:{length}")
                    self.active_channel = channel
                    self.active_channel_buffer.clear()
                    self.active_channel_buget = length
                    
                    self.header_buffer.clear()
                    self.header_magic_check_next = 0
                    self.header_to_read = 0
                continue
            
            # searching for header match current(=self.header_magic_check_next) byte
            if b == self.header_magic_delimiter[self.header_magic_check_next]:
                # still matching magic
                self.header_buffer.append(b)
                self.header_magic_check_next += 1

                if self.header_magic_check_next == len(self.header_magic_delimiter):
                    # full match -> mark rest of the header to be read
                    self.header_to_read = self.header_size - len(self.header_magic_delimiter)
                    self.header_magic_check_next = 0
            else:
                # mismatch
                if self.header_magic_check_next > 0:
                    # flush what we held so far
                    raw_out += self.header_buffer
                    self.header_buffer.clear()
                    self.header_magic_check_next = 0

                    # re-evaluate current byte
                    if b == self.header_magic_delimiter[0]:
                        self.header_buffer.append(b)
                        self.header_magic_check_next = 1
                    else:
                        raw_out.append(b)
                else:
                    # no partial match, pass through
                    raw_out.append(b)
        
        # Call on_raw_input only when:
        # no channel is being read
        # raw_out has content (empty could be interpreted as EOF) or message was empty (was EOF)
        if (self.active_channel == 0) and (len(raw_out) != 0 or len(message) == 0):
            self.on_raw_input(raw_out)
