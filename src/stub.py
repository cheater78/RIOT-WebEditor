from __future__ import annotations
from abc import abstractmethod
import argparse
import asyncio
from enum import Enum
import os
from typing import Any

import log, protocol
from file_descriptor_io import STDIO, MultiplexIO
from protocol_message_types import *

class CommandArgParser:
    parser: argparse.ArgumentParser
    parsed: bool = False
    args: Any
    
    def __init__(self) -> None:
        self.parser = argparse.ArgumentParser(description=f"trigger and handle a riot web command")
        self.parser.add_argument("command", type=str, help="the riot web command to run")

        self.parsed = False

    def parse(self) -> None:
        self.args = self.parser.parse_args()
        self.parsed = True

    def __parse_once__(self) -> None:
        if not self.parsed:
            self.parse()

    def command(self) -> CommandType:
        self.__parse_once__()
        command_str: str = self.args.command
        return CommandType.decode(command_str)

class CommandHandler:
    event_loop: asyncio.AbstractEventLoop
    stdio: STDIO
    stdio_multiplex: MultiplexIO
    stdio_multiplex_protocol_channel: int = 1

    p_shell_id: int
    protocol_Address_me: Address

    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self.event_loop = event_loop

        self.stdio = STDIO(self.__on_raw_stdin__, self.event_loop)
        self.stdio_multiplex = MultiplexIO(self.stdio)
        self.stdio_multiplex.setChannelCallbackFunction(self.stdio_multiplex_protocol_channel, self.__on_raw_protocol_in__)

        env = os.environ.copy()
        self.p_shell_id = int(env["RIOT_WEB_SHELL_ID"])
        self.protocol_Address_me = Address(AddressType.SHELL, self.p_shell_id)

    @abstractmethod 
    def run(self) -> None:
        self.event_loop.run_forever()

    def write(self, message: ProtocolMessage) -> None:
        raw: bytes = protocol.encode(message)
        self.stdio_multiplex.write_channel(self.stdio_multiplex_protocol_channel, raw)

    def __on_raw_protocol_in__(self, message: bytes) -> None:
        unsafe_message: ProtocolMessage | None = protocol.decode(message)
        if not unsafe_message:
            log.error(f"CommandHandler.__on_raw_protocol_in__: Message could not be decoded!")
            return
        self.__on_protocol_in__(unsafe_message)

    @abstractmethod
    def __on_raw_stdin__(self, message: bytes) -> None:
        pass

    @abstractmethod
    def __on_protocol_in__(self, message: ProtocolMessage) -> None:
        pass

class FlashCommandArgParser(CommandArgParser):

    def __init__(self) -> None:
        super().__init__()
        self.parser.add_argument("programmer", type=str, help="programmer / flasher that would be used locally.")
        self.parser.add_argument("board", type=str, help="target board to build for.")
        self.parser.add_argument("port", type=str, help="port / device to flash to.")

        self.parser.add_argument("bootloader_pos", type=str, help="offset to the bootloader.")
        self.parser.add_argument("bootloader_bin", type=str, help="binary of the bootloader.")
        self.parser.add_argument("partitions_pos", type=str, help="offset to partitions.")
        self.parser.add_argument("partitions_bin", type=str, help="binary of partitions.")
        self.parser.add_argument("flashfile_pos", type=str, help="offset to the flashfile.")
        self.parser.add_argument("flashfile_bin", type=str, help="binaryof the flashfile.")

        self.parser.add_argument("fflags", type=str, help="All Flasher args that would be used locally.")
    
    def programmer(self) -> str:
        self.__parse_once__()
        return self.args.programmer
    
    def board(self) -> str:
        self.__parse_once__()
        return self.args.board

    def port(self) -> str:
        self.__parse_once__()
        return self.args.port
    
    def fflags(self) -> str:
        self.__parse_once__()
        return self.args.fflags
    
    def binaries(self) -> dict[int, str]:
        self.__parse_once__()
        return {
            self.args.bootloader_pos: self.args.bootloader_bin,
            self.args.partitions_pos: self.args.partitions_bin,
            self.args.flashfile_pos: self.args.flashfile_bin,
        }

class FlashCommandHandler(CommandHandler):

    class Stage(Enum):
        PRE_DNR = 0
        DNR = 1
        FLASHING = 2
        SUCCESS = 3
        ERROR = 4

    arg_parser: FlashCommandArgParser
    stage: Stage = Stage.PRE_DNR

    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(event_loop)
        self.arg_parser = FlashCommandArgParser()
        self.stage = self.Stage.PRE_DNR

    def run(self) -> None:
        self.stage = self.Stage.DNR
        dnr_message = MessageDNRRequest(
            self.protocol_Address_me,
            self.arg_parser.port()
        )
        self.write(dnr_message)

        super().run()

    def __on_raw_stdin__(self, message: bytes) -> None:
        pass

    def __on_protocol_in__(self, message: ProtocolMessage) -> None:
        match message.type:
            case MessageType.DNR_ACK:
                if not isinstance(message, MessageDNRAck):
                    log.error("Message of type DNR_ACK was not a MessageDNRAck!")
                    return
                if self.stage == self.Stage.DNR:
                    binaries: dict[int, bytes] = { }
                    for offset, path in self.arg_parser.binaries().items():
                        with open(path, "rb") as f:
                            binaries[offset] = f.read()
                    
                    flash_message: MessageFlash = MessageFlash(self.protocol_Address_me, message.sender, self.arg_parser.board(), binaries, self.arg_parser.fflags())
                    self.write(flash_message)
                    return
                log.warn("received unexpected MessageDNRAck!")
            case MessageType.LOG:
                if not isinstance(message, MessageLog):
                    log.error("Message of type LOG was not a MessageLog!")
                    return
                print(message.log_msg)
                return
            case MessageType.LTM:
                if not isinstance(message, MessageLinkTermination):
                    log.error("Message of type LTM was not a MessageLinkTermination!")
                    return
                self.stage = self.Stage.ERROR if message.log_type == LogType.ERROR else self.Stage.SUCCESS
                self.event_loop.stop()
                return
            case _:
                log.warn(f"received unexpected Message of type {str(message.type)}")
                pass

class TermCommandArgParser(CommandArgParser):

    def __init__(self) -> None:
        super().__init__()
        self.parser.add_argument("board", type=str, help="target board to build for.")
        self.parser.add_argument("port", type=str, help="port / device to flash to.")
        self.parser.add_argument("baud", type=int, help="baud rate for the serial connection.")
    
    def baud(self) -> int:
        self.__parse_once__()
        return self.args.baud
    
    def board(self) -> str:
        self.__parse_once__()
        return self.args.board

    def port(self) -> str:
        self.__parse_once__()
        return self.args.port

class TermCommandHandler(CommandHandler):

    class Stage(Enum):
        PRE_DNR = 0
        DNR = 1
        TERM = 2
        SUCCESS = 3
        ERROR = 4

    arg_parser: TermCommandArgParser
    stage: Stage = Stage.PRE_DNR

    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(event_loop)
        self.arg_parser = TermCommandArgParser()
        self.stage = self.Stage.PRE_DNR

    def run(self) -> None:
        self.stage = self.Stage.DNR
        dnr_message = MessageDNRRequest(
            self.protocol_Address_me,
            self.arg_parser.port()
        )
        self.write(dnr_message)

        super().run()

    def __on_raw_stdin__(self, message: bytes) -> None:
        pass

    def __on_protocol_in__(self, message: ProtocolMessage) -> None:
        match message.type:
            case MessageType.DNR_ACK:
                if not isinstance(message, MessageDNRAck):
                    log.error("Message of type DNR_ACK was not a MessageDNRAck!")
                    return
                if self.stage == self.Stage.DNR:
                    term_message: MessageTerm = MessageTerm(self.protocol_Address_me, message.sender, self.arg_parser.board(), self.arg_parser.baud())
                    self.write(term_message)
                    return
                log.warn("received unexpected MessageDNRAck!")
            case MessageType.LOG:
                if not isinstance(message, MessageLog):
                    log.error("Message of type LOG was not a MessageLog!")
                    return
                log.info(message.log_msg)
                return
            case MessageType.LTM:
                if not isinstance(message, MessageLinkTermination):
                    log.error("Message of type LTM was not a MessageLinkTermination!")
                    return
                self.stage = self.Stage.ERROR if message.log_type == LogType.ERROR else self.Stage.SUCCESS
                self.event_loop.stop()
                return
            case _:
                log.warn(f"received unexpected Message of type {str(message.type)}")
                pass

class CommandType(Enum, str):
    NONE = ""
    FLASH = "flash"
    TERM = "term"

    def __new__(cls, type: str):
        return super().__new__(cls, type)
    
    @staticmethod
    def decode(data: str) -> CommandType:
        try:
            return CommandType(data)
        except:
            return CommandType.NONE
    
commands: dict[str, type[CommandHandler]] = {
    CommandType.FLASH: FlashCommandHandler,
    CommandType.TERM: TermCommandHandler,
}

def command_names() -> list[str]:
    return list(commands.keys())

def __main__() -> None:
    command_arg_parser: CommandArgParser = CommandArgParser()
    command_type: CommandType = command_arg_parser.command()
    if command_type == CommandType.NONE:
        log.error("Illegal or missing Command Type!")
        return
    event_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
    command_handler: CommandHandler = commands[command_type](event_loop)
    command_handler.run()

__main__()