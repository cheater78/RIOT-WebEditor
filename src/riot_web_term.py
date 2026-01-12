#!/usr/bin/env python3
import os, sys, signal, time, pty, tty, select, errno, termios
import asyncio
import websockets.client as wsc
from websockets import exceptions as wse
import random
from typing import Optional, Tuple, Callable

def fd_readable(fd: int) -> bool:
    return bool(select.select([fd], [], [], 0)[0])

def fd_writable(fd: int) -> bool:
    return bool(select.select([], [fd], [], 0)[1])

def read_all(fd: int) -> bytes:
    """
    Read all available data from a file descriptor. Non-blocking.
    
    :param fd: File descriptor to read from
    :type fd: int
    :return: Data read from the file descriptor
    :rtype: bytes
    """
    chunks: list[bytes] = []
    while True:
        data = b""
        try:
            if fd_readable(fd):
                data = os.read(fd, 4096)
        except OSError: # silenntly fail and return what we have
            break
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks)

def write_all(fd: int, data: bytes) -> int:
    total = 0
    length = len(data)

    while total < length:
        try:
            n = os.write(fd, data[total:])
            if n == 0:
                raise RuntimeError("write returned 0 bytes")
            total += n
        except OSError as e:
            if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                # wait until fd is writable
                select.select([], [fd], [])
                continue
            elif e.errno == errno.EINTR:
                # interrupted by signal, retry
                continue
            else:
                raise

    return total

def split_at_first_match(buffer: bytes | str, patterns: list[bytes | str]) -> Tuple[Optional[bytes | str], bytes | str]:
    """
    Find the first occurrence of any pattern in buffer, split there.
    
    Returns:
        front: the part before the match (None if no match)
        back:  the remainder starting from the match (unchanged if no match)
    """
    first_pos = len(buffer)
    first_pattern = None

    # Find the earliest occurrence of any pattern
    for p in patterns:
        idx = buffer.find(p)
        if idx != -1 and idx < first_pos:
            first_pos = idx
            first_pattern = p

    if first_pattern is None:
        # No match found
        return None, buffer

    # Split at the position
    if first_pos == 0:
        # [:0] case → include first element in front
        front = buffer[:1]
        back = buffer[1:]   # remainder after first element
    else:
        front = buffer[:first_pos]
        back = buffer[first_pos + 1:]
    return front, back

def child_alive(pid: int) -> bool:
    """ Check if child process is still running """
    try:
        pid_ret, _ = os.waitpid(pid, os.WNOHANG)
        if pid_ret == 0:
            return True
        else:
            return False
    except ChildProcessError:
        return False

def child_kill(pid: int) -> None:
    """ Gracefully kill child process """
    # Send a friendly SIGTERM first
    os.kill(pid, signal.SIGTERM)
    # wait for a sec to exit
    for _ in range(10):
        pid2, _ = os.waitpid(pid, os.WNOHANG)
        if pid2 != 0:
            break
        time.sleep(0.1)
    else:
        # didn't exit -> force kill
        os.kill(pid, signal.SIGKILL)
        os.waitpid(pid, 0)

class WebsocketConnection:
    uuid: int
    address: str = "127.0.0.1"
    port: int = 7777
    ssl: bool = False
    websocket: wsc.WebSocketClientProtocol
    on_message: Callable[[str], None]

    def __init__(self):
        self.uuid = random.randint(1, sys.maxsize)
        self.on_message = self.__on_message__

    async def connect(self):
        location: str = "ws" 
        location += "s" if self.ssl else ""
        location += "://" + str(self.address) + ":" + str(self.port)
        self.websocket = await wsc.connect(location)
        await self.write(str(self.uuid))

    async def handle(self):
        try:
            await asyncio.wait_for(self.__read__(), timeout=0.1)
        except asyncio.exceptions.TimeoutError:
            return
        except wse.ConnectionClosed:
            await self.connect()
            return

    async def write(self, msg: str):
        await self.websocket.send(msg)

    def set_msg_cllbk_func(self, func: Callable[[str], None]):
        self.on_message = func

    async def __read__(self):
        message = await self.websocket.recv()
        if type(message) is bytes:
            msg: str = message.decode()
        elif type(message) is str:
            msg = message
        else:
            raise RuntimeError("msg was weirdly typed!" + str(type(message)))
        if msg:
            self.on_message(msg)

    def __on_message__(self, msg: str) -> None:
        print("[+] WS_MSG: " + msg)
        pass
    

# Linked FDs for IPC
front_fd, back_fd = pty.openpty()
pid = os.fork()
parent_running = True

if pid == 0:
    # Child process
    os.setsid()
    os.close(front_fd) # cleanup non associated FD
    # Connect the backend shell to the slave side of the pty
    back_in = os.dup2(back_fd, 0) # stdin
    back_out = os.dup2(back_fd, 1) # stdout
    back_err = os.dup2(back_fd, 2) # stderr
    # FD was duplicated, close original
    os.close(back_fd)

    os.write(back_out, b"[_] Starting shell...\n")
    os.execvp("bash", ["bash", "-i"])
    os.write(back_err, b"[_] Failed to spawn bash inplace!\n")
    os._exit(0)

else:
    # Parent process
    os.close(back_fd)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    front_in  = sys.stdin.fileno()
    front_out = sys.stdout.fileno()
    front_err = sys.stderr.fileno()
    old = termios.tcgetattr(front_in)
    tty.setraw(front_in)

    write_all(front_out, b"[+] Parent here..\n\r")

    write_all(front_out, b"[+] Connecting WebSocket...\n\r")
    ws_relay = WebsocketConnection()

    def ws_on_msg(msg: str):
        write_all(front_fd, msg.encode())
        pass
    
    ws_relay.set_msg_cllbk_func(ws_on_msg)
    loop.run_until_complete(ws_relay.connect())
    write_all(front_out, b"[+] WebSocket connected!\n\r")

    try:
        front_input_buffer: bytes = b""
        front_fd_buffer: bytes = b""
        while parent_running:
            if not child_alive(pid):
                parent_running = False

            loop.run_until_complete(ws_relay.handle())
            r, _, _ = select.select([front_in, front_fd], [], [], 0.1)

            if front_in in r:
                data = read_all(front_in)
                if data:
                    if data == b'\x03':  # (Ctrl-C)
                        write_all(front_out, b"\n\r[+] Ctrl-C detected")
                        child_kill(pid)
                    elif data == b'\x04':
                        write_all(front_fd, b"echo hello world\n")
                    else:
                        front_input_buffer += data
                        
                        line, rest = split_at_first_match(front_input_buffer, [b"\n", b"\r"])
                        if line is None:
                            write_all(front_fd, data)
                        while line is not None:
                            if isinstance(rest, bytes):
                                front_input_buffer = rest
                            elif isinstance(rest, str):
                                front_input_buffer = rest.encode()
                            else:
                                raise TypeError(f"(shouldnt happen)Unexpected type: {type(rest)}")
                            cmd = line.strip()
                            if isinstance(line, str):
                                lineBytes: bytes = line.encode()
                            else:
                                lineBytes = line

                            if not lineBytes:
                                break
                            if cmd:
                                if cmd.startswith(b"ls"):
                                    write_all(front_fd, b" -la")
                                write_all(front_out, b"\n\r[+] Running command>" + lineBytes)
                                write_all(front_fd, b"\n")
                            line, rest = split_at_first_match(front_input_buffer, [b"\n", b"\r"])
            
            if front_fd in r:
                data = read_all(front_fd)
                if data:
                    front_fd_buffer += data
                    write_all(front_out, data)
        
        if child_alive(pid):
            write_all(front_out, b"\n\r[+] Waiting for child to exit...")
            os.wait() # wait for child process to finish
        write_all(front_out, b"\n\r[+] Parent Closing...\n\r")
    finally:
        loop.close()
        termios.tcsetattr(front_in, termios.TCSADRAIN, old)