#!/usr/bin/env python3
from __future__ import annotations
from abc import abstractmethod
import argparse
import asyncio
import os
from typing import Any, Optional

from riot_web_tools.utils import log
from riot_web_tools.utils.types.bytes import to_bytes
from riot_web_tools.shell import *
from riot_web_tools.protocol import *
from riot_web_tools.protocol.transport.protocol_fd_io import *

class CommandArgParser:
    parser: argparse.ArgumentParser
    args: Any
    
    def __init__(self, other: Optional[CommandArgParser] = None) -> None:
        if not other:
            self.parser = argparse.ArgumentParser(description=f"trigger and handle a riot web command")
            self.parser.add_argument("command", type=str, help="the riot web command to run")
            self.parser.add_argument("port", type=str, help="port / device to flash to.")
            self.parser.add_argument("board", type=str, help="target board to build for.")

            self.args, _ = self.parser.parse_known_args()
        else:
            self.parser = other.parser
            self.args = other.args

    def command(self) -> CommandType:
        command_str: str = self.args.command
        return CommandType(command_str)
    
    def port(self) -> str:
        return self.args.port
    
    def board(self) -> str:
        return self.args.board

class CommandHandler:
    _event_loop: asyncio.AbstractEventLoop
    _p_shell_id: int

    _arg_parser: CommandArgParser

    _tty_io: TTYRawIO
    _std_protocol_io: ProtocolMUXFDIO
    _protocol_me: Address

    _device: DeviceAddress

    def __init__(self, arg_parser: CommandArgParser, event_loop: asyncio.AbstractEventLoop) -> None:
        self._event_loop = event_loop
        self._p_shell_id = self.__query_web_shell_id__()
        self._arg_parser = arg_parser

        self._tty_io = TTYRawIO(
            self._on_raw_stdin_,
            self._on_tty_windowresize_,
            event_loop=self._event_loop)
        self._std_protocol_io = ProtocolMUXFDIO(
            self._tty_io, 
            self.__on_protocol_in__)
        self._protocol_me = ShellAddress(self._p_shell_id)
        self._device = DeviceAddress(arg_parser.port())

    def _stop_(self) -> None:
        self._event_loop.stop()

    def _send_reset_(self, termination_type: TerminationType, msg: str) -> None:
        rst: MessageReset = MessageReset(self._protocol_me, self._device, termination_type, msg)
        self._std_protocol_io.write(rst)

    @abstractmethod
    def _on_raw_stdin_(self, message: bytes) -> None:
        pass

    @abstractmethod
    def _on_tty_windowresize_(self, rows: int, cols: int) -> None:
        pass
    
    def run(self) -> None:
        self._event_loop.run_forever()
        self._tty_io.close()
        os._exit(0)
    
    def __on_protocol_in__(self, message: Message) -> None:
        match message:
            case MessageReset() as ltm:
                if ltm.sender not in [self._device, ClientAddress()]:
                    log.warn(f"Stub received MessageReset from illegal source! {ltm}")
                    return
                if ltm.termination_type == TerminationType.SUCCESS:
                    self._tty_io.write(to_bytes(ltm.termination_message + 
                        ("" if ltm.termination_message.endswith("\n") else "\n")))
                else:
                    self._tty_io.error(to_bytes(ltm.termination_message + 
                        ("" if ltm.termination_message.endswith("\n") else "\n")))
                self._stop_()
            case MessageLog() as lm:
                self._tty_io.write(to_bytes(lm.log_msg))
                return
            case _:
                log.warn(f"received unexpected Message of type {message}")
                return

    @staticmethod
    def __query_web_shell_id__() -> int:
        unsafe_id_str: str | None = os.environ.get("RIOT_WEB_SHELL_ID")
        if not unsafe_id_str:
            log.error(f"RIOT_WEB_SHELL_ID was not found in the current environment! (FATAL)")
            os._exit(1)
        try:
            return int(unsafe_id_str)
        except:
            log.error(f"RIOT_WEB_SHELL_ID was not an int! was:{unsafe_id_str} (FATAL)")
            os._exit(1)

class FlashCommandArgParser(CommandArgParser):
    
    def __init__(self, other: Optional[CommandArgParser]) -> None:
        super().__init__(other)
        self.parser.add_argument("programmer", type=str, help="programmer / flasher that would be used locally.")
        self.parser.add_argument("binaries", help="binaries with their offset.")
        self.parser.add_argument("fflags", type=str, help="All Flasher args that would be used locally.")
        
        self.args, _ = self.parser.parse_known_args()
    
    def programmer(self) -> str:
        return self.args.programmer
    
    def fflags(self) -> str:
        return self.args.fflags
    
    def binaries(self) -> dict[int, str]:
        import json
        def parse_map(value: str) -> dict[int, str]:
            raw = json.loads(value)
            return {int(k, base=16): str(v) for k, v in raw.items()}
        return parse_map(self.args.binaries)

class FlashCommandHandler(CommandHandler):
    @staticmethod
    def __load_binaries__(binary_index: dict[int, str]) -> dict[int, bytes]:
        binaries: dict[int, bytes] = { }
        for offset, path in binary_index.items():
            with open(path, "rb") as f:
                binaries[offset] = f.read()
        return binaries

    def __init__(self, arg_parser: CommandArgParser, event_loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(FlashCommandArgParser(arg_parser), event_loop)

    def args(self) -> FlashCommandArgParser:
        return self._arg_parser #type: ignore

    def run(self) -> None:
        binaries: dict[int, bytes] = self.__load_binaries__(self.args().binaries())
        flash_message: MessageCommand = MessageCommand(
            self._protocol_me,
            self._device,
            CommandFlash(
                self.args().board(),
                binaries,
                self.args().fflags()
            ))
        self._std_protocol_io.write(flash_message)

        super().run()

    def _on_raw_stdin_(self, message: bytes) -> None:
        for b in message:
            if b == TTYActionRaw.CANCEL:
                self._tty_io.error(b"Flash in progress, cannot be canceled!")
                break

class TermCommandArgParser(CommandArgParser):

    def __init__(self, other: Optional[CommandArgParser]) -> None:
        super().__init__(other)
        self.parser.add_argument("baud", type=int, help="baud rate for the serial connection.")
        
        self.args, _ = self.parser.parse_known_args()

    def baud(self) -> int:
        return self.args.baud

class TermCommandHandler(CommandHandler):
    user_input: str

    def __init__(self, arg_parser: CommandArgParser, event_loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(TermCommandArgParser(arg_parser), event_loop)
        self.user_input = ""

    def run(self) -> None:
        term_message: MessageCommand = MessageCommand(
            self._protocol_me,
            self._device,
            CommandTerm(
                self.args().board(),
                self.args().baud()
            ))
        self._std_protocol_io.write(term_message)
        super().run()

    def args(self) -> TermCommandArgParser:
        return self._arg_parser #type: ignore

    def _stop_term_(self, success: bool = False, message: str = "Term was stopped!"):
        self._send_reset_(TerminationType.SUCCESS if success else TerminationType.ERROR, message)
        super()._stop_()

    def _on_raw_stdin_(self, message: bytes) -> None:
        human_message: str = ""

        def write() -> None:
            if self.user_input != "":
                self._std_protocol_io.write(MessageInput(self._protocol_me, self._device, self.user_input))
                self.user_input = ""
        
        for b in message:
            if chr(b).isprintable():
                human_message += chr(b)
                self._tty_io.write(f"{chr(b)}".encode())
            else:
                if b == TTYActionRaw.EOF:
                    write()
                    self._stop_term_(success=True, message="Term was ended by user input.")
                elif b == TTYActionRaw.CANCEL:
                    write()
                    self._stop_term_(success=False, message="Term was killed by the user.")
                elif b == TTYActionRaw.RETURN:
                    write()
                return
        
        self.user_input += human_message

command_type_to_handler: dict[CommandType, type[CommandHandler]] = {
    CommandType.FLASH: FlashCommandHandler,
    CommandType.TERM: TermCommandHandler,
}

def __main__() -> None:
    command_arg_parser: CommandArgParser = CommandArgParser()
    command_type: CommandType = command_arg_parser.command()
    
    command_handler_class: type[CommandHandler] | None = command_type_to_handler.get(command_type)
    if not command_handler_class:
        log.error("Specified CommandType did not have an associated CommandHandler!")
        return
    
    event_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    command_handler: CommandHandler = command_handler_class(command_arg_parser, event_loop)
    command_handler.run()

__main__()