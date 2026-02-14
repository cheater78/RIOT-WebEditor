from abc import abstractmethod
import asyncio
import struct
import os, sys, select, errno
from typing import Callable

FileDescriptorMessageType = bytes
FileDescriptorCallbackFunc = Callable[[FileDescriptorMessageType], None]

class AsyncFileDescriptorReader:
    fd: int
    fd_callback: FileDescriptorCallbackFunc
    event_loop: asyncio.AbstractEventLoop

    def __init__(self,
                 fd: int,
                 fd_callback: FileDescriptorCallbackFunc,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self.fd  = fd
        self.fd_callback = fd_callback
        self.event_loop = event_loop

        self.event_loop.add_reader(self.fd, self.__read__)

    def _(self) -> None:
        self.event_loop.remove_reader(self.fd)

    def __read__(self) -> None:
        # Never run if fd is empty
        if not self.__is_ready_read__():
            return

        data: FileDescriptorMessageType = FileDescriptorMessageType()
        while self.__is_ready_read__(): # Only enter when fd has content
            try:
                # Danger: Blocks until FD has content! (pty FD is a blocking FD)
                # Only run when fd has content!
                data += os.read(self.fd, 4096)
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    # only if FD is non-blocking, we can save a misscall
                    return
                else:
                    # something actually went wrong
                    raise
        # Forward to handler (data in bytes or empty if EOF)
        self.fd_callback(data)

    def __is_ready_read__(self) -> bool:
        return bool(select.select([self.fd], [], [], 0)[0])
    

class FileDescriptorWriter:
    fd: int

    def __init__(self, fd: int):
        self.fd = fd

    def write(self, data: FileDescriptorMessageType) -> None:
        total_written = 0
        length = len(data)

        while total_written < length:
            try:
                n = os.write(self.fd, data[total_written:])
                if n == 0:
                    raise RuntimeError("AsyncFileDescriptorHandler.__write__: os.write failed to write anything!") # TODO: when would that even happen
                total_written += n
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    # only if FD is non-blocking -> block ourselves
                    self.__wait_ready_write__()
                    continue
                elif e.errno == errno.EINTR:
                    # interrupted by signal, retry
                    #TODO: check when this happens
                    continue
                else:
                    raise
    
    def __wait_ready_write__(self) -> bool:
        return bool(select.select([], [self.fd], [])[1])

class FDIO:
    @abstractmethod
    def write(self, data: FileDescriptorMessageType) -> None:
        pass

    @abstractmethod
    def setCallbackFunction(self, callback: FileDescriptorCallbackFunc) -> None:
        pass

    @abstractmethod
    def getCallbackFunction(self) -> FileDescriptorCallbackFunc:
        pass

class STDIO(FDIO):
    stdin: AsyncFileDescriptorReader
    stdout: FileDescriptorWriter
    stderr: FileDescriptorWriter
    
    def __init__(self,
                 stdin_callback: FileDescriptorCallbackFunc,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self.stdin = AsyncFileDescriptorReader(sys.stdin.fileno(), stdin_callback, event_loop)
        self.stdout = FileDescriptorWriter(sys.stdout.fileno())
        self.stderr = FileDescriptorWriter(sys.stderr.fileno())
    
    def write(self, data: FileDescriptorMessageType) -> None:
        self.stdout.write(data)

    def error(self, data: FileDescriptorMessageType) -> None:
        self.stderr.write(data)

    def setCallbackFunction(self, callback: FileDescriptorCallbackFunc) -> None:
        self.stdin.fd_callback = callback

    def getCallbackFunction(self) -> FileDescriptorCallbackFunc:
        return self.stdin.fd_callback

class MasterPTYIO(FDIO):
    pty_in: FileDescriptorWriter
    pty_out: AsyncFileDescriptorReader

    def __init__(self,
                 master_pty_fd: int,
                 pty_out_callback: FileDescriptorCallbackFunc,
                 event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self.pty_in = FileDescriptorWriter(master_pty_fd)
        self.pty_out = AsyncFileDescriptorReader(master_pty_fd, pty_out_callback, event_loop)
    
    def write(self, data: FileDescriptorMessageType) -> None:
        self.pty_in.write(data)

    def setCallbackFunction(self, callback: FileDescriptorCallbackFunc) -> None:
        self.pty_out.fd_callback = callback

    def getCallbackFunction(self) -> FileDescriptorCallbackFunc:
        return self.pty_out.fd_callback
    
class MultiplexIO(FDIO):
    fdio: FDIO
    on_raw_input: FileDescriptorCallbackFunc
    on_channel_input: dict[int, FileDescriptorCallbackFunc]

    header_magic_delimiter: bytes = b"RIOTWebMultiplexFDIO"
    header_format: str = ""
    header_size: int = 0

    header_magic_pos_found: int = 0
    header_buffer: bytearray = bytearray()

    active_channel: int = 0
    active_channel_buget: int = 0

    def __init__(self,
               fdio: FDIO) -> None:#
        self.fdio = fdio
        self.on_raw_input = self.fdio.getCallbackFunction()
        self.fdio.setCallbackFunction(self.__on_raw_fdin__)

        self.header_format = f">{len(self.header_magic_delimiter)}sBI"
        self.header_size = struct.calcsize(self.header_format)
    
    def write(self, data: FileDescriptorMessageType) -> None:
        self.fdio.write(data)

    def write_channel(self, channel: int, data: FileDescriptorMessageType) -> None:
        header = struct.pack(self.header_format, self.header_magic_delimiter, channel, len(data))
        self.write(header + data)

    def setChannelCallbackFunction(self, channel: int, callback: FileDescriptorCallbackFunc) -> None:
        self.on_channel_input[channel] = callback

    def getChannelCallbackFunction(self, channel: int) -> FileDescriptorCallbackFunc | None:
        return self.on_channel_input.get(channel)

    def setCallbackFunction(self, callback: FileDescriptorCallbackFunc) -> None:
        self.on_raw_input = callback

    def getCallbackFunction(self) -> FileDescriptorCallbackFunc:
        return self.on_raw_input
    
    def __on_raw_fdin__(self, message: bytes) -> None:
        message_length: int = len(message)

        if self.active_channel != 0 and self.active_channel_buget > 0:
            if message_length <= self.active_channel_buget:
                self.header_buffer += message
                self.active_channel_buget -= message_length
                return
            else:
                self.header_buffer += message[(self.active_channel_buget - 1):]
                message = message[:self.active_channel_buget]
                self.on_channel_input[self.active_channel](self.header_buffer)
        
        raw_out: bytearray = bytearray()
        for b in message:
            if b == self.header_magic_delimiter[self.pos]:
                # still matching magic
                self.header_buffer.append(b)
                self.pos += 1

                if self.pos == self.header_size:
                    # full match
                    channel, length = struct.unpack(self.header_format, self.header_buffer)
                    self.active_channel = channel
                    self.active_channel_buget = length
                    
                    self.header_buffer.clear()
                    self.pos = 0
            else:
                # mismatch
                if self.pos > 0:
                    # flush what we held so far
                    raw_out += self.header_buffer
                    self.header_buffer.clear()
                    self.pos = 0

                    # re-evaluate current byte
                    if b == self.header_magic_delimiter[0]:
                        self.header_buffer.append(b)
                        self.pos = 1
                    else:
                        raw_out.append(b)
                else:
                    # no partial match, pass through
                    raw_out.append(b)
        
        self.on_raw_input(raw_out)