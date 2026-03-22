import asyncio
import struct
import os, signal, time, pty, fcntl, termios
from typing import MutableMapping, Optional, Callable

from riot_web_tools.utils import log
from riot_web_tools.utils.types.bytes import to_bytes
from riot_web_tools.protocol import *
from riot_web_tools.protocol.transport.protocol_fd_io import *
from .fd_io import FDMessageType, FDCallbackFunc
from .tty_io import PTYMasterIO, TTYActionRaw

ShellEnvironment = MutableMapping[str, str]
ShellClosedCallbackFunc = Callable[[], None]
class ShellProcess:
    """
    ShellProcess, main thread handle that creates a forked shell process
    It provides a pty master for the shells stdin, stdout and stderr,
    as well as a protocol mux on the same pty

    Never keep using this object in the child process itself!
    The ShellProcess object is ought to be an easy access handle for the main thread.
    """
    _pty_master: PTYMasterIO
    _kill_timeout: int # in ms

    _shell_binary_path: str
    _shell_args: list[str]
    _shell_raw_output_cb: FDCallbackFunc
    _shell_closed_cb: ShellClosedCallbackFunc
    
    # pid of the child - used for the shell process
    _child_pid: int

    def __init__(self,
                shell_raw_output_cb: FDCallbackFunc,
                shell_closed_cb: ShellClosedCallbackFunc,
                shell_binary_path: str = "/bin/bash",
                shell_args: list[str] = ["-i"],
                shell_environment: Optional[ShellEnvironment] = None,
                shell_kill_grace_period_ms: int = 1000,
                event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self._shell_binary_path = shell_binary_path
        self._shell_args = shell_args
        self._shell_raw_output_cb = shell_raw_output_cb
        self._shell_closed_cb = shell_closed_cb
        self._kill_timeout = shell_kill_grace_period_ms

        # supplied env or default to current
        environment: ShellEnvironment = shell_environment if shell_environment else os.environ.copy()
        # acquire the current (front) terminal
        # shells may require ENV["TERM"] to be set to a capable terminal for interactiveness
        # default to "xterm-256color", since it has these capabilities
        if not environment.get("TERM"):
            environment["TERM"] = "xterm-256color"

        # Create a PTY (Pseudoterminal)
        # yielding 2 FDs (Master = Front, Slave = Child/Back/Shell)
        # used for IPC between the main thread and the shell thread
        pty_master_fd, pty_slave_fd = pty.openpty()

        # Fork to Main and Child/Shell process
        # Note: posix fork: main(pid=child_pid), child(pid=0 -> semantic of "my pid" - I shouldn't need to know my own "real pid")
        self._child_pid: int = os.fork()

        if self._child_pid == 0: # Child/Shell process - setup, then replace with a shell
            # close the master pty fd - child owns the slave pty fd only
            os.close(pty_master_fd)

            # become session leader
            os.setsid()
            # Make PTY the controlling terminal
            fcntl.ioctl(pty_slave_fd, termios.TIOCSCTTY)

            # Connect the pty slave to stdio
            # done by duplicating the pty slave fd into the stdio fds
            os.dup2(pty_slave_fd, 0) # stdin
            os.dup2(pty_slave_fd, 1) # stdout
            os.dup2(pty_slave_fd, 2) # stderr
            # Close the pty slave fd since its connected to stdio now and no longer needed
            if pty_slave_fd > 2:
                os.close(pty_slave_fd)

            # We need job control, redundant if the shell starts interactively successfully
            # Explicitly make this child process its own group leader
            # Use child pid as process group id
            if os.getpid() != os.getpgrp(): # setsid should have done so, in case it didn't
                os.setpgid(0, 0) # (pid=0 -> self, pgid=0 -> own pid)
            # Explicitly set the foreground process group of STDIN(=pty slave, which is the controlling terminal)
            proc_group_id: int = os.getpgrp()
            fcntl.ioctl(0, termios.TIOCSPGRP, struct.pack("i", proc_group_id))

            # Replace this child process with an interactive shell
            try:
                # Replace this process with a shell, given the set environment
                # Note: posix args are: [0]=program_name, [1..]=args
                shell_name: str = os.path.basename(self._shell_binary_path)
                os.execvpe(self._shell_binary_path, [shell_name] + self._shell_args, environment)
                # this should never be reached!
                os.write(2, to_bytes(f"[{self.__class__.__name__}.Child] (Fatal) Replacing the shild process with a shell (execvpe) was passed, without rasing an OSError!"))
            except OSError:
                os.write(2, to_bytes(f"[{self.__class__.__name__}.Child] (Fatal) Replacing the shild process with a shell (execvpe) was failed!"))
            os._exit(127) # Exit the process with error
            # End of Child/Shell process code
        else: # Main process - finish setting up the ShellProcess handle
            # close the slave pty fd - child owns the master pty fd only
            os.close(pty_slave_fd)
            # warp the pty master fd in our class
            self._pty_master = PTYMasterIO(pty_master_fd, self.__shell_raw_output_cb__, event_loop)

    def write(self, data: FDMessageType) -> None:
        self._pty_master.write(data)

    def is_busy(self) -> bool:
        """
        Return True if the shell is currently running a foreground job.
        Return False if the shell itself owns the terminal (idle / prompt-ready).
        Note: If the shell is running a builtin (e.g. cd, export, read) this returns still False, but input is buffered
        TODO: except on read,readarray,... -> input is consumed - this only happens if the user enters those themself (scripts invoke new procs)
        """

        # Retrive the process group id of the child process
        shell_pgid = os.getpgid(self._child_pid)

        # Foreground process group of the PTY
        buf = fcntl.ioctl(
            self._pty_master.fd,
            termios.TIOCGPGRP,
            struct.pack("i", 0)
        )
        fg_pgid = struct.unpack("i", buf)[0]

        # If shell is not foreground -> definitely busy
        if fg_pgid != shell_pgid:
            return True

        # TODO: handle builtins
        return False

    def run_cmd(self, cmd: str) -> None:
        log.err_assert(not self.is_busy(), f"ShellProcess.run_cmd: called while shell is busy! Check before calling!")
        # clear the current line/multiline(\) input from the shell
        self.write(TTYActionRaw.MOVE_END + TTYActionRaw.DELETE_BEFORE)
        # enter the command and submit it for execution
        self.write(cmd.encode() + bytes(TTYActionRaw.RETURN))
    
    def is_alive(self):
        """ Check if child process is still running """
        if self._child_pid == 0:
            os.write(2, to_bytes(f"[{self.__class__.__name__}.Child] (Warn) is_alive: called on child process!"))
            return # should never be reached, only in child
        try:
            pid_ret, _ = os.waitpid(self._child_pid, os.WNOHANG)
            if pid_ret == 0:
                return True
            else:
                return False
        except ChildProcessError:
            return False
    
    def stop(self) -> None:
        """ Gracefully kill child process """
        if self._child_pid == 0:
            os.write(2, to_bytes(f"[{self.__class__.__name__}.Child] (Warn) kill: called on child process!"))
            return # should never be reached, only in child
        # Send a friendly SIGTERM first
        os.kill(self._child_pid, signal.SIGTERM)
        # wait for a sec to exit
        for _ in range(self._kill_timeout):
            pid2, _ = os.waitpid(self._child_pid, os.WNOHANG)
            if pid2 != 0:
                break
            time.sleep(0.001)
        else:
            # didn't exit -> force kill
            os.kill(self._child_pid, signal.SIGKILL)
            os.waitpid(self._child_pid, 0)
    
    def set_window_size(self, rows: int, cols: int) -> None:
        self._pty_master.set_window_size(rows, cols)

    def __shell_raw_output_cb__(self, message: FDMessageType) -> None:
        if not message:
            self._shell_closed_cb()
        self._shell_raw_output_cb(message)

class RiotWebShellProcess(ShellProcess):
    """
    A ShellProcess that provides the necessary environment (RIOT_WEB=1, RIOT_WEB_SHELL_ID) to the shell,
    as well as Stub awareness for protocol communication
    """
    _pty_master_protocol: ProtocolMUXFDIO
    _shell_protocol_output_cb: ProtocolClientCallbackFunc

    _stub_protocol_ready: bool

    def __init__(self,
                shell_raw_output_cb: FDCallbackFunc,
                shell_protocol_output_cb: ProtocolClientCallbackFunc,
                shell_closed_cb: ShellClosedCallbackFunc,
                riot_web_shell_id: int,
                shell_binary_path: str = "/bin/bash",
                shell_args: list[str] = ["-i"],
                shell_kill_grace_period_ms: int = 1000,
                event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self._shell_protocol_output_cb = shell_protocol_output_cb

        # Setup the Shell environment
        env = os.environ
        # RIOT_WEB flag, activates riot-patches to call the stub instead of the local toolchains
        env["RIOT_WEB"] = "1"
        # RIOT_WEB_SHELL_ID, identifier used by the riot web frontend for communication
        env["RIOT_WEB_SHELL_ID"] = f"{riot_web_shell_id}"
        
        super().__init__(
            shell_raw_output_cb,
            shell_closed_cb,
            shell_binary_path,
            shell_args,
            env,
            shell_kill_grace_period_ms,
            event_loop
        )
        # provide a FDProtocolIO handle to mux protocol messages through the pty
        self._pty_master_protocol = ProtocolMUXFDIO(self._pty_master, self.__on_shell_protocol_output__)

        self._stub_protocol_ready = False

    def is_stub_protocol_ready(self) -> bool:
        return self.is_busy() and self._stub_protocol_ready
    
    def set_link_established(self) -> None:
        self._stub_protocol_ready = True

    def write_protocol(self, message: Message) -> None:
        log.err_assert(self.is_busy() and self.is_stub_protocol_ready(), f"ShellProcess.write_protocol: called while no stub was running! Check before calling!")

        # Device closed the Link -> Stub will close connection
        if isinstance(message, MessageReset):
            self._stub_protocol_ready = False 

        self._pty_master_protocol.write(message)

    def __on_shell_protocol_output__(self, message: Message) -> None:
        if not isinstance(message, LinkMessage):
            log.warn(f"Received non LinkMessage from Stub! Message: {message}")
            return

        # Any non MessageLinkTermination from the Stub is considered a ready connection.
        # The Stub initiates protocol communication availability
        # Protocol communication availability to the Stub can be revoked by either a Stub or Device LTM
        self._stub_protocol_ready = not isinstance(message, MessageReset)

        self._shell_protocol_output_cb(message)

