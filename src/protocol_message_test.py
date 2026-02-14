#!/usr/bin/env python3
import log
import protocol
from protocol_message_types import *

dummy_messages: list[ProtocolMessage] = [
    MessageConnect(
        Address(AddressType.CLIENT, 1)
    ),
    MessageConnectAck(),
    MessageDisconnect(),
    MessageDNRRequest(
        sender=Address(AddressType.CLIENT, 1),
        device_name="MyDevice"
    ),
    MessageDNRAck(
        sender=Address(AddressType.CLIENT, 1),
        reciever=Address(AddressType.DEVICE, 42)
    ),
    MessageShellRequest(
        sender=Address(AddressType.CLIENT, 1),
        reciever=Address(AddressType.SHELL, 42)
    ),
    MessageShellRequestAck(
        sender=Address(AddressType.SHELL, 42),
        reciever=Address(AddressType.CLIENT, 1)
    ),
    MessageLinkTermination(
        sender=Address(AddressType.CLIENT, 1),
        reciever=Address(AddressType.SHELL, 42),
        log_type=LogType.ERROR,
        log_msg="Test log message"
    ),
    MessageFlash(
        sender=Address(AddressType.CLIENT, 1),
        reciever=Address(AddressType.DEVICE, 42),
        board="esp32-wroom-32",
        project_path="/path/to/project",
        binaries={0x00: b"\xDE\xAD\xBE\xEF"},
        args="--flash-args"
    ),
    MessageFlashRequest(
        sender=Address(AddressType.CLIENT, 1),
        reciever=Address(AddressType.DEVICE, 42),
        board="esp32-wroom-32",
        project_path="/path/to/project"
    ),
    MessageTerm(
        sender=Address(AddressType.CLIENT, 1),
        reciever=Address(AddressType.DEVICE, 42),
        board="esp32-wroom-32",
        project_path="/path/to/project",
        baud_rate=115200
    ),
    MessageTermRequest(
        sender=Address(AddressType.CLIENT, 1),
        reciever=Address(AddressType.DEVICE, 42),
        board="esp32-wroom-32",
        project_path="/path/to/project"
    ),
    MessageLog(
        sender=Address(AddressType.CLIENT, 1),
        reciever=Address(AddressType.SHELL, 42),
        log_type=LogType.LOG,
        log_msg="This is a log message"
    ),
    MessageInput(
        sender=Address(AddressType.CLIENT, 1),
        reciever=Address(AddressType.SHELL, 42),
        input_msg="User input message"
    )
]

def test(message: ProtocolMessage) -> None:
    log.info(f"{message.__class__.__name__} encoding/decoding...")
    message_encoded = protocol.encode(message)
    message_decoded = protocol.decode(message_encoded)
    log.err_assert(message_decoded != None, f"{message.__class__.__name__} decode failed!")
    message_reencoded = protocol.encode(message_decoded) # type: ignore
    log.err_assert(message_reencoded == message_encoded, f"{message.__class__.__name__} encoding/decoding failed")

def test_all() -> None:
    for message in dummy_messages:
        test(message)
    log.info("All protocol message tests passed!")

test_all()