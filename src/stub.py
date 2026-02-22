#!/usr/bin/env python3
from __future__ import annotations
from abc import abstractmethod
import argparse
import asyncio
from enum import StrEnum
import os
from typing import Any, Optional

from safe_types import to_bytes, str_is_int
from tty_io import TTYRawIO, TTYActionRaw
from protocol_fd_io import ProtocolMUXFDIO
from protocol_message import *

class CommandType(StrEnum):
    NONE = ""
    FLASH = "flash"
    TERM = "term"

    @staticmethod
    def decode(data: str) -> CommandType:
        try:
            return CommandType(data)
        except:
            return CommandType.NONE

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
        return CommandType.decode(command_str)
    
    def port(self) -> str:
        return self.args.port
    
    def board(self) -> str:
        return self.args.board

class CommandHandler:
    _event_loop: asyncio.AbstractEventLoop
    _p_shell_id: int

    _arg_parser: CommandArgParser

    _ttyio: TTYRawIO
    _std_protocol_io: ProtocolMUXFDIO
    _protocol_me: Address

    _device_name: str
    _device_resolved: bool
    _device: Address

    def __init__(self, arg_parser: CommandArgParser, event_loop: asyncio.AbstractEventLoop) -> None:
        self._event_loop = event_loop
        self._p_shell_id = self.__query_web_shell_id__()
        self._arg_parser = arg_parser

        self._ttyio = TTYRawIO(
            self.__on_raw_stdin__,
            self._on_tty_windowresize_,
            event_loop=self._event_loop)
        self._std_protocol_io = ProtocolMUXFDIO(
            self._ttyio, 
            self.__on_protocol_in__)
        self._protocol_me = Address(AddressType.SHELL, self._p_shell_id)
        
        self._device_resolved = str_is_int(self._arg_parser.port())
        self._device_name = self._arg_parser.port() if not self._device_resolved else ""
        self._device = Address(AddressType.DEVICE, int(self._arg_parser.port()) if self._device_resolved else -1)

    def _stop_(self) -> None:
        self._event_loop.stop()

    def _send_ltm_(self, termination_type: TerminationType, msg: str) -> None:
        ltm: MessageLinkTermination = MessageLinkTermination(self._protocol_me, self._device, termination_type, msg)
        self._std_protocol_io.write(ltm)

    @abstractmethod
    def _on_raw_stdin_(self, message: bytes) -> None:
        pass

    @abstractmethod
    def _on_protocol_in_(self, message: ProtocolMessage) -> None:
        pass

    @abstractmethod
    def _on_link_established_(self) -> None:
        pass

    @abstractmethod
    def _on_tty_windowresize_(self, rows: int, cols: int) -> None:
        pass
    
    def run(self) -> None:
        if not self._device_resolved:
            self.__send_dnr__()
        else:
            self._on_link_established_()
        
        self._event_loop.run_forever()
        self._ttyio.close()

    def __send_dnr__(self) -> None:
        dnr = MessageDNRRequest(
                self._protocol_me,
                self._device_name
            )
        self._std_protocol_io.write(dnr)

    def __on_raw_stdin__(self, message: bytes) -> None:
        if bytes(TTYActionRaw.CANCEL) == message:
            self._send_ltm_(TerminationType.ERROR, "Action interrupted by user!")
            self._stop_()
            return
        self._on_raw_stdin_(message)
    
    def __on_protocol_in__(self, message: ProtocolMessage) -> None:
        match message:
            case MessageDNRAck() as dnr_ack:
                if self._device_resolved:
                    log.warn(f"Unexpected DNRAck received!")
                    return
                self._device = dnr_ack.sender
                self._device_resolved = True
                self._on_link_established_()
            case MessageLinkTermination() as ltm:
                if ltm.termination_type == TerminationType.SUCCESS:
                    os.write(1, to_bytes(ltm.termination_message))
                else:
                    os.write(2, to_bytes(ltm.termination_message))
                self._stop_()
            case _:
                self._on_protocol_in_(message)

    @staticmethod
    def __query_web_shell_id__() -> int:
        unsafe_id_str: str | None = os.environ.get("RIOT_WEB_SHELL_ID")
        if not unsafe_id_str:
            log.error(f"RIOT_WEB_SHELL_ID was not found in the current environment! (FATAL)")
            exit(1) #TODO: send LTM?
        try:
            return int(unsafe_id_str)
        except:
            log.error(f"RIOT_WEB_SHELL_ID was not an int! was:{unsafe_id_str} (FATAL)")
            exit(1) #TODO: send LTM?

class FlashCommandArgParser(CommandArgParser):
    def __init__(self, other: Optional[CommandArgParser]) -> None:
        super().__init__(other)
        self.parser.add_argument("programmer", type=str, help="programmer / flasher that would be used locally.")
        self.parser.add_argument("binaries", type=str, help="binaries with their offset.")
        self.parser.add_argument("fflags", type=str, help="All Flasher args that would be used locally.")
        
        self.args, _ = self.parser.parse_known_args()
    
    def programmer(self) -> str:
        return self.args.programmer
    
    def fflags(self) -> str:
        return self.args.fflags
    
    def binaries(self) -> dict[int, str]:
        # TODO: does this work? - cleanup
        import json
        def parse_map(value: str) -> dict[int, str]:
            raw = json.loads(value)
            return {int(k): str(v) for k, v in raw.items()}
        return parse_map(self.args.binaries)

class FlashCommandHandler(CommandHandler):
    def __init__(self, arg_parser: CommandArgParser, event_loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(FlashCommandArgParser(arg_parser), event_loop)

    def run(self) -> None:
        # TODO: needed?
        super().run()

    def args(self) -> FlashCommandArgParser:
        return self._arg_parser #type: ignore

    def _on_link_established_(self) -> None:
        binaries: dict[int, bytes] = { }
        for offset, path in self.args().binaries().items():
            with open(path, "rb") as f:
                binaries[offset] = f.read()
        flash_message: MessageFlash = MessageFlash(
            self._protocol_me,
            self._device,
            self.args().board(),
            binaries,
            self.args().fflags())
        self._std_protocol_io.write(flash_message)

    def _on_raw_stdin_(self, message: bytes) -> None:
        pass # cancel only

    def _on_protocol_in_(self, message: ProtocolMessage) -> None:
        match message:
            case MessageLog() as lm:
                os.write(1, to_bytes(lm.log_msg))
                return
            case _:
                log.warn(f"received unexpected Message of type {str(message.type)}")
                pass

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
        # TODO: needed?
        super().run()

    def args(self) -> TermCommandArgParser:
        return self._arg_parser #type: ignore

    def _stop_(self, success: bool = False, message: str = "Term was stopped!"):
        self._send_ltm_(TerminationType.SUCCESS if success else TerminationType.ERROR, message)
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
                self._ttyio.write(f"{chr(b)}".encode())
            else:
                if f"{b}".encode() == TTYActionRaw.EOF:
                    write()
                    self._stop_(success=True, message="Term was ended by user input.")
                elif f"{b}".encode() == TTYActionRaw.CANCEL:
                    write()
                    self._stop_(success=False, message="Term was killed by the user.")
                elif chr(b) == "\r" or chr(b) == "\n":
                    write() # human_message += chr(b) -> but tty is raw
                else:
                    print(f"[w] user entered a byte that wasnt human readable!\n\r")
                return
        
        self.user_input += human_message
        
    def _on_link_established_(self) -> None:
        term_message: MessageTerm = MessageTerm(
            self._protocol_me,
            self._device,
            self.args().board(),
            self.args().baud())
        self._std_protocol_io.write(term_message)

    def _on_protocol_in_(self, message: ProtocolMessage) -> None:
        match message:
            case MessageLog() as log:
                print(log.log_msg) # TODO: type? - os.write?
                return
            case _:
                print(f"received unexpected Message of type {str(message.type)}")
                pass


command_type_to_handler: dict[str, type[CommandHandler]] = {
    CommandType.FLASH: FlashCommandHandler,
    CommandType.TERM: TermCommandHandler,
}

def __main__() -> None:
    command_arg_parser: CommandArgParser = CommandArgParser()

    command_type: CommandType = command_arg_parser.command()
    if command_type == CommandType.NONE:
        log.error("Illegal or missing Command Type!")
        return
    
    command_handler_class: type[CommandHandler] | None = command_type_to_handler.get(command_type)
    if not command_handler_class:
        log.error("Specified CommandType did not have an associated CommandHandler!")
        return
    
    event_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    command_handler: CommandHandler = command_handler_class(command_arg_parser, event_loop)
    command_handler.run()

__main__()