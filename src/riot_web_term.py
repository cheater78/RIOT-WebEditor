#!/usr/bin/env python3
import fcntl
import os, sys, signal, time, pty, tty, select, errno, termios
import asyncio
import websockets.client as wsc
from websockets import exceptions as wse
import random
from typing import Optional, Tuple, Callable

#TODO: Interception handling with prompt_toolkit
# from prompt_toolkit import PromptSession

def to_bytes(data: bytes | str) -> bytes:
    if isinstance(data, bytes):
        return data
    elif isinstance(data, str):
        return data.encode()
    else:
        return b""

class PTYFileDescriptor: 
    handle: int

    def __init__(self, fd: int):
        self.handle = fd

    def close(self):
        os.close(self.handle)

    def is_ready_read(self):
        return bool(select.select([self.handle], [], [], 0)[0])

    def is_ready_write(self):
        return bool(select.select([], [self.handle], [], 0)[1])

    def wait_ready_read(self):
        select.select([self.handle], [], [])
    
    def wait_ready_write(self):
        select.select([], [self.handle], [])

    def read(self) -> bytes:
        """
        Read all available data from the file descriptor. Non-blocking.

        """
        chunks: list[bytes] = []
        while True:
            data = b""
            try:
                if self.is_ready_read():
                    data = os.read(self.handle, 4096)
            except OSError: # silently fail and return what we have
                break
            if not data:
                break
            chunks.append(data)
        return b"".join(chunks)
    
    def write(self, data: bytes | str) -> int:
        """
        Write all data to the file descriptor. Blocking, until all is written.
        
        """
        data_bytes: bytes = to_bytes(data)
        total = 0
        length = len(data_bytes)

        while total < length:
            try:
                n = os.write(self.handle, data_bytes[total:])
                if n == 0:
                    raise RuntimeError("write returned 0 bytes") # TODO: when would that even happen
                total += n
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    # wait until fd is writable
                    self.wait_ready_write()
                    continue
                elif e.errno == errno.EINTR:
                    # interrupted by signal, retry
                    continue
                else:
                    raise

        return total
    
    def bind_to_std(self):
        """
        Duplicates the PTY FileDescriptor into the current processes std in out and err
        You usually want to close this one afterwards.
        
        """
        os.dup2(self.handle, 0) # stdin
        os.dup2(self.handle, 1) # stdout
        os.dup2(self.handle, 2) # stderr

    def close_on_exec(self):
        fcntl.fcntl(self.handle, fcntl.F_SETFD, fcntl.FD_CLOEXEC)

def open_pty():
    front_fd, back_fd = pty.openpty()
    return [PTYFileDescriptor(front_fd), PTYFileDescriptor(back_fd)]

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

class BackendShell:
    """
    BackendShell, that creates an async process running the specified Shell
    It provides a front pty for the shells stdin, stdout and stderr

    Never keep using this object in the child process itself!
    The BackendShell object is ought to be an easy access Handle for the main thread.
    """
    front: PTYFileDescriptor
    pid: int
    shell: str = "/bin/bash"
    shell_args: list[str] = ["-i"]
    kill_timeout: int = 3000 # in ms 

    def __init__(self):
        self.front, back = open_pty()
        self.pid = os.fork()

        if self.pid == 0:
            # Child process - setup, then replace with a shell
            os.setsid()
            self.front.close() # cleanup non associated FD
            back.bind_to_std() # connect the pty fd to std

            shell_name: str = os.path.basename(self.shell)
            child_pid: int = os.getpid()
            back.write(f"[_] Starting BackendShell({shell_name}): {child_pid}")
            
            back.close_on_exec() # close, the shell will be the only one to interact with the fd
            try:
                os.execvp(self.shell, [shell_name] + self.shell_args) # replace process with a shell
                os._exit(1) # should never be reached!
            except OSError:
                back.write(f"[_] Failed to start BackendShell({shell_name})! terminating...")
                back.close() # close, the shell will be the only one to interact with the fd
                os._exit(127) # should never be reached!
        else:
            # Main process
            back.close() # close, owned by the child process

    def is_alive(self):
        """ Check if child process is still running """
        if self.pid == 0:
            return
        try:
            pid_ret, _ = os.waitpid(self.pid, os.WNOHANG)
            if pid_ret == 0:
                return True
            else:
                return False
        except ChildProcessError:
            return False
    
    def kill(self) -> None:
        """ Gracefully kill child process """
        if self.pid == 0:
            return
        # Send a friendly SIGTERM first
        os.kill(self.pid, signal.SIGTERM)
        # wait for a sec to exit
        for _ in range(self.kill_timeout):
            pid2, _ = os.waitpid(self.pid, os.WNOHANG)
            if pid2 != 0:
                break
            time.sleep(0.001)
        else:
            # didn't exit -> force kill
            os.kill(self.pid, signal.SIGKILL)
            os.waitpid(self.pid, 0)
    
class ShellProxyInterface:
    __running = True
    
    def __init__(self) -> None:
        pass

    def run(self):
        pass



term_pid = os.getpid()

runner = BackendShell()

# Parent process
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

front_in  = sys.stdin.fileno()
front_out = sys.stdout.fileno()
front_err = sys.stderr.fileno()

old = termios.tcgetattr(front_in)
tty.setraw(front_in)

pid_str_bytes = str(term_pid).encode()

write_all(front_out, b"[+] ShellProxy with PID=" + pid_str_bytes + b"\n\r")

write_all(front_out, b"[+] Connecting WebSocket...\n\r")
#ws_relay = WebsocketConnection()

def ws_on_msg(msg: str):
    write_all(front_fd, msg.encode())
    pass

#ws_relay.set_msg_cllbk_func(ws_on_msg)
#loop.run_until_complete(ws_relay.connect())
write_all(front_out, b"[+] WebSocket connected!\n\r")

try:
    front_input_buffer: bytes = b""
    front_fd_buffer: bytes = b""
    while parent_running:
        if not child_alive(pid):
            parent_running = False

        #loop.run_until_complete(ws_relay.handle())
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