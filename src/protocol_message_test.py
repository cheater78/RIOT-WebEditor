#!/usr/bin/env python3
import log
import protocol
from protocol_message import *

log.log_level=log.Level.INFO
log.enable_asserts=True

dummy_sender: Address = Address(AddressType.CLIENT, 0)
dummy_receiver: Address = Address(AddressType.DEVICE, 42)

dummy_messages: list[ProtocolMessage] = [
    MessageConnect(
        dummy_sender
    ),
    MessageConnectAck(),
    MessageDisconnect(),
    MessageDNRRequest(
        sender=dummy_sender,
        device_name="MyDevice"
    ),
    MessageDNRAck(
        sender=dummy_sender,
        reciever=dummy_receiver
    ),
    MessageShellRequest(
        sender=dummy_sender,
        reciever=dummy_receiver
    ),
    MessageShellRequestAck(
        sender=dummy_receiver,
        reciever=dummy_sender
    ),
    MessageLinkTermination(
        sender=dummy_sender,
        reciever=dummy_receiver,
        termination_type=TerminationType.ERROR,
        termination_message="Test log message"
    ),
    MessageFlash(
        sender=dummy_sender,
        reciever=Address(AddressType.DEVICE, 42),
        board="esp32-wroom-32",
        binaries={0x00: b"\xDE\xAD\xBE\xEF"},
        args="--flash-args"
    ),
    MessageFlashRequest(
        sender=dummy_sender,
        reciever=Address(AddressType.DEVICE, 42),
        board="esp32-wroom-32",
        project_path="/path/to/project"
    ),
    MessageTerm(
        sender=dummy_sender,
        reciever=Address(AddressType.DEVICE, 42),
        board="esp32-wroom-32",
        baud_rate=115200
    ),
    MessageTermRequest(
        sender=dummy_sender,
        reciever=Address(AddressType.DEVICE, 42),
        board="esp32-wroom-32",
        project_path="/path/to/project"
    ),
    MessageLog(
        sender=dummy_sender,
        reciever=dummy_receiver,
        log_type=LogType.LOG,
        log_msg="This is a log message"
    ),
    MessageInput(
        sender=dummy_sender,
        reciever=dummy_receiver,
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