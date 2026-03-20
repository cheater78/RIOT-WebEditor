#!/usr/bin/env python3
import asyncio, os, sys

from riot_web_tools.utils import log
from riot_web_tools.shell import *
from riot_web_tools.protocol import *

class RiotWebShellProxy:
    async_event_loop: asyncio.AbstractEventLoop
    shell_id: int

    tty_io: TTYRawIO
    shell_process: RiotWebShellProcess
    protocol_socket: ProtocolAsyncRemoteSocketClient

    user_mode: bool # if true the shell belongs to the user and cant be reclaimed
    locked_device: DeviceAddress | None

    def __init__(self) -> None:
        self.shell_id = self.__retrieve_shell_identifier__()
        log.info(f">Starting ShellProxy with ID={self.shell_id}")

        self.async_event_loop = asyncio.new_event_loop()

        log.info(f">Starting RiotWebShellProcess...")
        self.shell_process = RiotWebShellProcess(
            self.__on_raw_shell_output__,
            self.__on_protocol_shell_output__,
            self.__on_shell_closed__,
            shell_args=sys.argv[1:],
            riot_web_shell_id = self.shell_id,
            event_loop = self.async_event_loop)
        
        log.info(f">Creating AsyncWebsocketClient...")
        self.remote_socket_me = ShellAddress(self.shell_id)
        self.protocol_socket = ProtocolAsyncRemoteSocketClient(
            self.shell_id,
            self.__on_remote_socket_protocol_link_message__,
            event_loop=self.async_event_loop)

        log.info(f">Starting TTYIO...")
        self.tty_io = TTYRawIO(
            self.__on_tty_raw_stdin__,
            on_tty_win_resize=self.__on_tty_window_resize__,
            reformat_output=True,
            event_loop=self.async_event_loop)

        self.shell_process.set_window_size(*self.tty_io.get_window_size())

        self.user_mode = False
        self.locked_device = None

    def __shutdown__(self) -> None:
        # Cleanup
        if self.protocol_socket.is_connected():
            log.info(">Shutting down ProtocolSocketClient...")
            self.protocol_socket.disconnect()
        if self.shell_process.is_alive():
            log.info(">Shutting down ShellProcess...")
            self.shell_process.stop()
        log.info(">Closing TTYIO...")
        self.tty_io.close()

    def __retrieve_shell_identifier__(self) -> int:
        """
        Shell id is the process id on the system:
        - its unique for the process (during its lifetime)
        - it can be retrieved when spawning a new Shell in a VSCode WebExtensionHost
        """
        return os.getpid()

    def run(self):
        log.info(">Connecting AsyncWebsocketClient...")
        self.protocol_socket.connect()
        log.info(">Running event loop...")
        self.async_event_loop.run_forever()
        self.__shutdown__()

        os._exit(0)
    
    def stop(self) -> None:
        if self.async_event_loop.is_running():
            log.info(f">Stopping event loop...")
            self.async_event_loop.stop()
    
    # Front: TTYIO
    def __on_tty_raw_stdin__(self, data: bytes) -> None:
        if not self.shell_process.is_busy() and bytes(TTYActionRaw.RETURN) in data:
            self.user_mode = True
        if self.locked_device is not None and bytes(TTYActionRaw.CANCEL) in data:
            self.protocol_socket.write_protocol(MessageReset(self.remote_socket_me, self.locked_device, TerminationType.ERROR, "Action canceled by user!"))
            self.locked_device = None
        # Forwand to Shell
        self.shell_process.write(data)

    def __on_tty_window_resize__(self, rows: int, cols: int) -> None:
        # Resize PTY
        self.shell_process.set_window_size(rows, cols)

    # Back: ShellProcess
    def __on_raw_shell_output__(self, data: bytes) -> None:
        # Forward to STDOUT
        self.tty_io.write(data)

    def __on_protocol_shell_output__(self, message: Message) -> None:
        log.info(f"Forwarding ShellProtocol to SocketProtocol: {message}")
        if self.protocol_socket.is_established():
            match message:
                case MessageReset(): # if stub ends its task by RESET, device will unlock
                    self.locked_device = None
                case _:
                    pass
            self.protocol_socket.write_protocol(message)
        else:
            log.warn(f"Remote Socket is not connected!")

    def __on_shell_closed__(self) -> None:
        self.stop()

    # Remote Socket: WebSocket
    def __on_remote_socket_protocol_link_message__(self, link_message: LinkMessage) -> None:
        match link_message:
            case MessageRequest() as req:
                if self.user_mode or self.shell_process.is_busy():
                    self.protocol_socket.write_protocol(MessageReset(req.receiver, req.sender, TerminationType.ERROR, "Shell is busy or in user mode!"))
                    return
                elif not isinstance(req.sender, DeviceAddress):
                    self.protocol_socket.write_protocol(MessageReset(req.receiver, req.sender, TerminationType.ERROR, "Only Devices can Request Commands!"))
                    return
                
                match req.request:
                    case RequestFlash() as flash:
                        board = flash.board
                        project_path = flash.project_path
                        command = "flash"
                    case RequestTerm() as term:
                        board = term.board
                        project_path = term.project_path
                        command = "term"
                    case _:
                        self.protocol_socket.write_protocol(MessageReset(req.receiver, req.sender, TerminationType.ERROR, "Unknown Request!"))
                        return
                self.protocol_socket.write_protocol(MessageACK(req.receiver, req.sender))
                self.locked_device = req.sender
                self.shell_process.run_cmd(f"cd {project_path}")
                self.shell_process.run_cmd(f"make BOARD={board} PORT={req.sender.device_name} {command}")
                return
            case MessageReset() as ltm:
                if not self.shell_process.is_busy():
                    log.warn(f"MessageReset received, shell not busy! Dropping message: {link_message}")
                    return
                if not self.shell_process.is_stub_protocol_ready():
                    log.info(f"Received MessageReset on busy Shell, sending CANCEL! {ltm}")
                    self.shell_process.write(bytes(TTYActionRaw.CANCEL))
                    self.locked_device = None
                    return
                log.info(f"Forwarding SocketProtocol to ShellProtocol: {link_message}")
                self.shell_process.write_protocol(link_message)
            case _:
                if not self.shell_process.is_stub_protocol_ready():
                    log.warn(f"Missing Stub! Dropping message: {link_message}")
                    return
                
                log.info(f"Forwarding SocketProtocol to ShellProtocol: {link_message}")
                self.shell_process.write_protocol(link_message)

shell_proxy = RiotWebShellProxy()
shell_proxy.run()
