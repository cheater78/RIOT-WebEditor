#!/usr/bin/env python3
import asyncio
from enum import Enum
import os

import log
from file_descriptor_io import STDIO, MultiplexIO
from shell_process import ShellProcess
from async_remote_socket_client import AsyncRemoteSocketClient, AsyncWebsocketClient
import protocol
from protocol_message_types import *
from protocol_field_types import *

from typing import Callable

class TTYActions(Enum):
    MOVE_START = b"\x01"  # Ctrl-A
    MOVE_END = b"\x05"    # Ctrl-E
    DELETE_BEFORE = b"\x15" # Ctrl-U
    DELETE_AFTER = b"\x0b"  # Ctrl-K
    EXECUTE = b"\n"      # Return
    CANCEL = b"\x03"      # Ctrl-C
    EOF = b"\x04"         # Ctrl-D

ShellInputCallbackFunc = Callable[[bytes], None]
class WhackySTDINParser:
    command_execution_trigger: bytes = TTYActions.EXECUTE.value
    input_buffer: bytes
    on_command_callback: ShellInputCallbackFunc

    def __init__(self, on_command_callback: ShellInputCallbackFunc) -> None:
        self.input_buffer = b""
        self.on_command_callback = on_command_callback

    def feed(self, data: bytes) -> bytes:
        self.input_buffer += data

        while self.command_execution_trigger in self.input_buffer:
            line, self.input_buffer = self.input_buffer.split(self.command_execution_trigger, 1)
            self.on_command_callback(line)
            return self.input_buffer
        
        return data

class ShellProxy:
    shell_id: int

    async_event_loop: asyncio.AbstractEventLoop
    terminal_io: STDIO
    shell_process: ShellProcess
    shell_process_multiplex_pty: MultiplexIO

    remote_socket_client: AsyncRemoteSocketClient
    connection_established: bool = False
    remote_socket_me: Address
    
    whacky_parser: WhackySTDINParser

    class CurrentTask(Enum):
        NONE = 0
        FLASHING = 1
        TERM = 2
    current_task: CurrentTask = CurrentTask.NONE
    current_device: int = -1
    current_board: str = ""
    current_project_path: str = ""
    current_baudrate: int = 115200

    def __init__(self) -> None:
        self.shell_id = os.getpid()
        log.info(f">Starting ShellProxy with ID={self.shell_id}")
        self.async_event_loop = asyncio.new_event_loop()

        log.info(f">Starting BackendShell...")
        log.info(f">Starting TerminalIO...")
        self.terminal_io = STDIO(self.__on_stdin_raw__, event_loop=self.async_event_loop)
        log.info(f">Starting ShellProcess...")
        self.shell_process = ShellProcess(self.__shell_callback__, event_loop=self.async_event_loop)
        log.info(f">Starting MultiplexIO...")
        self.shell_process_multiplex_pty = MultiplexIO(self.shell_process.pty_master)

        log.info(f">Starting AsyncWebsocketClient...")
        self.remote_socket_me = Address(AddressType.SHELL, self.shell_id)
        self.remote_socket_client = AsyncWebsocketClient(self.__on_ws_open__, self.__on_ws_close__, self.__on_ws_message__, event_loop=self.async_event_loop)

    def run(self):
        log.info(">Starting event loop...")
        self.async_event_loop.run_forever()
        # Cleanup
        log.info(">Shutting down: ShellProcess")
        self.shell_process.kill()

    def __on_stdin_raw__(self, data: bytes) -> None:
        if data == TTYActions.EOF.value or data == b"" or data == TTYActions.CANCEL.value:
            if self.current_task == ShellProxy.CurrentTask.NONE:
                log.info("EOF/CANCEL received on STDIN, Shutting down...")
                self.async_event_loop.stop()
                return
            else:
                log.info("EOF/CANCEL received on STDIN, stopping tasks...")
                self.remote_socket_client.write(
                    protocol.encode(
                        MessageLinkTermination(
                            sender=self.remote_socket_me,
                            reciever=Address(AddressType.DEVICE, self.current_device),
                            log_type=LogType.ERROR,
                            log_msg="Task terminated by user via EOF/CANCEL."
                )))
                self.current_task = ShellProxy.CurrentTask.NONE
                self.shell_process.write(TTYActions.CANCEL.value)
                return
        remaining: bytes = self.whacky_parser.feed(data)
        if remaining != b"":
            log.info(f"ShellSTDIN> {str(remaining)}")
            self.shell_process.write(remaining) # only forward remaining data (not a full command)

    def __cancel_current_task__(self) -> None:
        if self.current_task == ShellProxy.CurrentTask.NONE:
            return
        log.info("Cancelling current task...")
        self.remote_socket_client.write(
            protocol.encode(
                MessageLinkTermination(
                    sender=self.remote_socket_me,
                    reciever=Address(AddressType.DEVICE, self.current_device),
                    log_type=LogType.ERROR,
                    log_msg="Task cancelled by user."
        )))
        self.current_task = ShellProxy.CurrentTask.NONE
        self.shell_process.write(TTYActions.CANCEL.value)

    def __on_stdin_command__(self, data: bytes) -> None:
        data_str: str = data.decode()

        if self.current_task == ShellProxy.CurrentTask.TERM and self.current_device != -1:
            term_message: MessageInput = MessageInput(
                sender=self.remote_socket_me,
                reciever=Address(AddressType.DEVICE, self.current_device),
                input_msg=data_str
            )
            self.remote_socket_client.write(protocol.encode(term_message))
            return

        if self.current_task != ShellProxy.CurrentTask.NONE:
            log.warn("Unhandled STDIN command while task running!")
            return

        log.info(f"STDIN Command> {str(data)}")

        def wipe_shell_input():
            self.shell_process.write(TTYActions.MOVE_END.value)
            self.shell_process.write(TTYActions.DELETE_BEFORE.value)

        primitive_command_line: list[str] = data_str.strip().split(" ")
        primitive_command: str = primitive_command_line[0].lower()
        if primitive_command == "exit":
            log.info("Exit command received, shutting down...")
            self.async_event_loop.stop()
        elif primitive_command == "flash":
            if len(primitive_command_line) != 3:
                log.error("Flash command: flash <device_name> <board_name>")
                wipe_shell_input()
                self.shell_process.write(TTYActions.CANCEL.value)
                return
            device_name: str = primitive_command_line[1]
            board_name: str = primitive_command_line[2]
            log.info(f"Flash command received: device='{device_name}', board='{board_name}'")

            dnr_message: MessageDNRRequest = MessageDNRRequest(
                sender=self.remote_socket_me,
                device_name=device_name
            )
            self.current_task = ShellProxy.CurrentTask.FLASHING
            self.remote_socket_client.write(protocol.encode(dnr_message))
            self.current_board = board_name

            wipe_shell_input()
            return
        elif primitive_command == "term":
            if len(primitive_command_line) != 4:
                log.error("Term command: term <device_name> <board_name> <baudrate>")
                wipe_shell_input()
                self.shell_process.write(TTYActions.CANCEL.value)
                return
            device_name: str = primitive_command_line[1]
            board_name: str = primitive_command_line[2]
            baudrate_str: str = primitive_command_line[3]
            try:
                baudrate: int = int(baudrate_str)
            except ValueError:
                log.error("Term command: baudrate must be an integer!")
                wipe_shell_input()
                self.shell_process.write(TTYActions.CANCEL.value)
                return
            log.info(f"Term command received: device='{device_name}', board='{board_name}', baudrate={baudrate}")

            dnr_message: MessageDNRRequest = MessageDNRRequest(
                sender=self.remote_socket_me,
                device_name=device_name
            )
            self.current_task = ShellProxy.CurrentTask.TERM
            self.remote_socket_client.write(protocol.encode(dnr_message))
            self.current_board = board_name
            self.current_baudrate = baudrate
            wipe_shell_input()
            return
        else:
            log.info(f"Forwarding command to shell: {data_str}")
            self.shell_process.write(data + TTYActions.EXECUTE.value) # pass raw if unhandled

    def __shell_callback__(self, data: bytes) -> None:
        log.info("shell>" + data.decode())

    def __on_ws_open__(self) -> None:
        self.remote_socket_client.write(protocol.encode(MessageConnect(Address(AddressType.SHELL, self.shell_id))))

    def __on_ws_close__(self) -> None:
        log.info(f"SP WS closed!")
        self.connection_established = False

    def __on_ws_message__(self, message: bytes) -> None:
        decoded: ProtocolMessage | None = protocol.decode(message)
        if decoded is None:
            log.error("Failed to decode message from WS!")
            return
        match decoded.type:
            case MessageType.CONNECT_ACK:
                log.info("Connection established with RemoteSocketServer!")
                self.connection_established = True
            case MessageType.DNR_ACK:
                if self.current_task == ShellProxy.CurrentTask.NONE:
                    log.error("Received unexpected MessageDNRAck while not in any task!")
                    return
                if not isinstance(decoded, MessageDNRAck):
                    log.error("Decoded MessageDNRAck is not of type MessageDNRAck!")
                    return
                log.info(f"Received MessageDNRAck: device ID={decoded.sender.value}")
                self.current_device = decoded.sender.value
                if self.current_task == ShellProxy.CurrentTask.FLASHING:
                    binaries: dict[int, bytes] = {
                        0x00000000: b"\x00"
                    }
                    flash_message: MessageFlash = MessageFlash(
                        sender=self.remote_socket_me,
                        reciever=Address(AddressType.DEVICE, self.current_device),
                        board=self.current_board,
                        binaries=binaries,
                        args=""
                    )
                    self.remote_socket_client.write(protocol.encode(flash_message))
                elif self.current_task == ShellProxy.CurrentTask.TERM:
                    term_message: MessageTerm = MessageTerm(
                        sender=self.remote_socket_me,
                        reciever=Address(AddressType.DEVICE, self.current_device),
                        board=self.current_board,
                        baud_rate=self.current_baudrate
                    )
                    self.remote_socket_client.write(protocol.encode(term_message))
            case MessageType.SRM:
                if self.current_task != ShellProxy.CurrentTask.NONE:
                    log.error("Received unexpected ShellRequestMessage while task running!")
                    return
                if not isinstance(decoded, MessageShellRequest):
                    log.error("Decoded MessageShellRequest is not of type MessageShellRequest!")
                    return
                log.info(f"Received MessageShellRequest for device ID={decoded.sender.value}")
                self.current_device = decoded.sender.value
                srm_ack_message: MessageShellRequestAck = MessageShellRequestAck(
                    sender=self.remote_socket_me,
                    reciever=decoded.sender
                )
                self.remote_socket_client.write(protocol.encode(srm_ack_message))
                log.info("SRM Acknoledged!")
            case MessageType.FLASH_REQUEST:
                if self.current_task != ShellProxy.CurrentTask.NONE:
                    log.error("Received unexpected MessageFlashRequest while task running!")
                    return
                if self.current_device == -1:
                    log.error("Received unexpected MessageFlashRequest while SRM was succesful!")
                    return
                if not isinstance(decoded, MessageFlashRequest):
                    log.error("Decoded MessageFlashRequest is not of type MessageFlashRequest!")
                    return
                log.info(f"Received MessageFlashRequest for device ID={decoded.sender.value}, board={decoded.board}")
                self.current_task = ShellProxy.CurrentTask.FLASHING
                self.current_board = decoded.board
                binaries: dict[int, bytes] = {
                    0x00000000: b"\x00"
                }
                flash_message: MessageFlash = MessageFlash(
                    sender=self.remote_socket_me,
                    reciever=Address(AddressType.DEVICE, self.current_device),
                    board=self.current_board,
                    binaries=binaries,
                    args=""
                )
                self.remote_socket_client.write(protocol.encode(flash_message))
            case MessageType.TERM_REQUEST:
                if self.current_task != ShellProxy.CurrentTask.NONE:
                    log.error("Received unexpected MessageTermRequest while task running!")
                    return
                if self.current_device == -1:
                    log.error("Received unexpected MessageTermRequest while SRM was succesful!")
                    return
                if not isinstance(decoded, MessageTermRequest):
                    log.error("Decoded MessageTermRequest is not of type MessageTermRequest!")
                    return
                log.info(f"Received MessageTermRequest for device ID={decoded.sender.value}, board={decoded.board}")
                self.current_task = ShellProxy.CurrentTask.TERM
                self.current_board = decoded.board
                term_message: MessageTerm = MessageTerm(
                    sender=self.remote_socket_me,
                    reciever=Address(AddressType.DEVICE, self.current_device),
                    board=self.current_board,
                    baud_rate=self.current_baudrate
                )
                self.remote_socket_client.write(protocol.encode(term_message))
            case MessageType.LOG:
                if self.current_task == ShellProxy.CurrentTask.NONE:
                    log.warn("Received unexpected MessageLog while no task running!")
                    return
                if not isinstance(decoded, MessageLog):
                    log.error("Decoded MessageLog is not of type MessageLog!")
                    return
                if decoded.log_type == LogType.ERROR:
                    log.error(f"Device {decoded.sender.value}> {decoded.log_msg}")
                elif decoded.log_type == LogType.LOG:
                    log.info(f"Device {decoded.sender.value}> {decoded.log_msg}")
                else:
                    log.info(f"Device SUCESS illegal!> {decoded.log_msg}")
            case MessageType.LTM:
                if self.current_task == ShellProxy.CurrentTask.NONE:
                    log.warn("Received unexpected MessageLinkTermination while no task running!")
                    return
                else:
                    log.info("LinkTermination received, stopping current task...")
                    if not isinstance(decoded, MessageLinkTermination):
                        log.error("Decoded MessageLinkTermination is not of type MessageLinkTermination!")
                    else:
                        if decoded.log_type == LogType.ERROR:
                            log.error(f"Task terminated with error: {decoded.log_msg}")
                        else:
                            log.info(f"Task terminated with success: {decoded.log_msg}")
                    self.current_task = ShellProxy.CurrentTask.NONE
                    self.current_device = -1
                    self.current_board = ""
                    self.current_baudrate = 115200
                    self.shell_process.write(TTYActions.CANCEL.value)
                    return
            case _:
                log.error(f"Received unexpected message type: {str(decoded.type)}")



shell_proxy = ShellProxy()
shell_proxy.run()
