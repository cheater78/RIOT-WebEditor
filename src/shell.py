#!/usr/bin/env python3
import asyncio, os

import log
from tty_io import TTYRawIO
from shell_process import RiotWebShellProcess
from protocol_remote_socket_client import ProtocolAsyncRemoteSocketClient
from protocol_message import *
from protocol_field_types import *

class RiotWebShellProxy:
    async_event_loop: asyncio.AbstractEventLoop
    shell_id: int

    tty_io: TTYRawIO
    shell_process: RiotWebShellProcess
    protocol_socket: ProtocolAsyncRemoteSocketClient

    def __init__(self) -> None:
        self.shell_id = self.__retrieve_shell_identifier__()
        log.info(f">Starting ShellProxy with ID={self.shell_id}")

        self.async_event_loop = asyncio.new_event_loop()

        log.info(f">Starting TTYIO...")
        self.tty_io = TTYRawIO(
            self.__on_tty_raw_stdin__,
            on_tty_win_resize=self.__on_tty_window_resize__,
            event_loop=self.async_event_loop)

        log.info(f">Starting ShellProcess...")
        self.shell_process = RiotWebShellProcess(
            self.__on_raw_shell_output__,
            self.__on_protocol_shell_output__,
            self.__on_shell_closed__,
            riot_web_shell_id = self.shell_id,
            event_loop = self.async_event_loop)

        log.info(f">Creating AsyncWebsocketClient...")
        self.remote_socket_me = Address(AddressType.SHELL, self.shell_id)
        # TODO: send smth to stub when running and connection lost! - aborty
        self.protocol_socket = ProtocolAsyncRemoteSocketClient(
            self.shell_id,
            self.__on_socket_protocol__,
            self.__on_socket_failed__,
            event_loop=self.async_event_loop)

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
    
    def stop(self) -> None:
        if self.async_event_loop.is_running():
            log.info(f">Stopping event loop...")
            self.async_event_loop.stop()
    
    # Front: TTYIO
    def __on_tty_raw_stdin__(self, data: bytes) -> None:
        # Forwand to Shell
        self.shell_process.write(data)

    def __on_tty_window_resize__(self, rows: int, cols: int) -> None:
        # Resize PTY
        self.shell_process.set_window_size(rows, cols)

    # Back: ShellProcess
    def __on_raw_shell_output__(self, data: bytes) -> None:
        # Forward to STDOUT
        self.tty_io.write(data)

    def __on_protocol_shell_output__(self, message: ProtocolMessage) -> None:
        log.info(f"Forwarding ShellProtocol to SocketProtocol: {message}")
        if self.protocol_socket.is_established():
            self.protocol_socket.write_protocol(message)
        else:
            log.warn(f"Remote Socket is not connected!")

    def __on_shell_closed__(self) -> None:
        self.stop()

    # Remote Socket: WebSocket
    def __on_socket_protocol__(self, message: ProtocolMessage) -> None:
        match message:
            case MessageShellRequest() as srm:
                if self.shell_process.is_busy():
                    self.protocol_socket.write_protocol(MessageLinkTermination(srm.receiver, srm.sender, TerminationType.ERROR, "Shell is busy!"))
                    return
                
                self.protocol_socket.write_protocol(MessageShellRequestAck(srm.receiver, srm.sender))
                return
            case MessageFlashRequest() as frm:
                if self.shell_process.is_busy():
                    self.protocol_socket.write_protocol(MessageLinkTermination(frm.receiver, frm.sender, TerminationType.ERROR, "Shell is busy!"))
                    return
                
                #TODO: PORT={message.sender.value} is NOT the device name here -> double use of PORT, not great
                log.warn("MessageFlashRequest is currently unstable!")
                self.shell_process.run_cmd(f"cd {frm.project_path} && make BOARD={frm.board} PORT={frm.sender.value} flash")
                return
            case MessageFlashRequest() as trm:
                if self.shell_process.is_busy():
                    self.protocol_socket.write_protocol(MessageLinkTermination(trm.receiver, trm.sender, TerminationType.ERROR, "Shell is busy!"))
                    return

                #TODO: PORT={message.sender.value} is NOT the device name here -> double use of PORT, not great
                log.warn("MessageFlashRequest is currently unstable!")
                self.shell_process.run_cmd(f"cd {trm.project_path} && make BOARD={trm.board} PORT={trm.sender.value} term")
                return
            case _:
                if not self.shell_process.is_stub_protocol_ready():
                    log.warn(f"Missing Stub! Dropping message: {message}")
                    return
                
                log.info(f"Forwarding SocketProtocol to ShellProtocol: {message}")
                self.shell_process.write_protocol(message)
    
    def __on_socket_failed__(self, retry: bool) -> None:
        log.warn("Socket connection failed!" + ("Retrying..." if retry else ""))
        pass

shell_proxy = RiotWebShellProxy()
shell_proxy.run()
