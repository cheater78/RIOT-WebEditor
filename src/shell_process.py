import asyncio
import os, signal, time, pty, fcntl
from safe_types import to_bytes
from file_descriptor_io import MasterPTYIO, FileDescriptorMessageType, FileDescriptorCallbackFunc

class ShellProcess:
    """
    ShellProcess, that creates an async process running the specified Shell
    It provides a front pty for the shells stdin, stdout and stderr

    Never keep using this object in the child process itself!
    The ShellProcess object is ought to be an easy access Handle for the main thread.
    """
    pty_master: MasterPTYIO
    shell_pid: int # pid of the child/shell process
    shell: str = "/bin/bash"
    shell_args: list[str] = ["-i"]
    kill_timeout: int = 3000 # in ms 

    def __init__(self,
                shell_output_callback: FileDescriptorCallbackFunc,
                shell_binary_path: str = "/bin/bash",
                shell_args: list[str] = ["-i"],
                shell_kill_grace_period_ms: int = 1000,
                event_loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()):
        self.shell = shell_binary_path
        self.shell_args = shell_args
        self.kill_timeout = shell_kill_grace_period_ms

        # Create a PTY (Pseudoterminal), yielding 2 FDs (Master = Front, Slave = Child/Back/Shell)
        pty_master_fd, pty_slave_fd = pty.openpty()
        # Fork to Main and Child(pid=0)/Shell process
        pid: int = os.fork()

        if pid == 0:
            # Child/Shell process - setup, then replace with a shell
            os.setsid()
            os.close(pty_master_fd) # close, owned by the child/shell process
            # Duplicate pty_slave_fd into stdin/out/err of the child/shell process
            os.dup2(pty_slave_fd, 0) # stdin
            os.dup2(pty_slave_fd, 1) # stdout
            os.dup2(pty_slave_fd, 2) # stderr

            shell_name: str = os.path.basename(self.shell)
            child_pid: int = os.getpid()
            os.write(pty_slave_fd, to_bytes(f"[_] Starting BackendShell({shell_name}): {child_pid}"))
            
            env = os.environ.copy()
            env["RIOT_WEB"] = "1" # TODO: ENV in docker img possibly not needed + img could run a local setup
            env["RIOT_WEB_SHELL_ID"] = f"{self.shell_pid}"

            # mark pty_slave_fd to close when execvp was successful (allows for err if not)
            fcntl.fcntl(pty_slave_fd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
            try:
                # replace process with a shell
                # self.shell is called as os path to be executed
                # args are always: [0]=program, [1..]=args
                os.execvpe(self.shell, [shell_name] + self.shell_args, env)
                os._exit(1) # should never be reached!
            except OSError:
                os.write(pty_slave_fd, to_bytes(f"[_] Failed to start BackendShell({shell_name})! terminating..."))
                os.close(pty_slave_fd) # close, shell spawn failed and Error was printed
                os._exit(127) # Exit the process
            # End of Child/Shell process code
        else:
            # Main process
            self.shell_pid = pid
            self.pty_master = MasterPTYIO(pty_master_fd, shell_output_callback, event_loop)
            os.close(pty_slave_fd) # close, owned by the child (shell) process

    def write(self, data: FileDescriptorMessageType) -> None:
        self.pty_master.write(data)

    def is_alive(self):
        """ Check if child process is still running """
        if self.shell_pid == 0:
            os.write(2, to_bytes(f"[_] is_alive: called on child process!"))
            return # should never be reached, only in child
        try:
            pid_ret, _ = os.waitpid(self.shell_pid, os.WNOHANG)
            if pid_ret == 0:
                return True
            else:
                return False
        except ChildProcessError:
            return False
    
    def kill(self) -> None:
        """ Gracefully kill child process """
        if self.shell_pid == 0:
            os.write(2, to_bytes(f"[_] kill: called on child process!"))
            return # should never be reached, only in child
        # Send a friendly SIGTERM first
        os.kill(self.shell_pid, signal.SIGTERM)
        # wait for a sec to exit
        for _ in range(self.kill_timeout):
            pid2, _ = os.waitpid(self.shell_pid, os.WNOHANG)
            if pid2 != 0:
                break
            time.sleep(0.001)
        else:
            # didn't exit -> force kill
            os.kill(self.shell_pid, signal.SIGKILL)
            os.waitpid(self.shell_pid, 0)
