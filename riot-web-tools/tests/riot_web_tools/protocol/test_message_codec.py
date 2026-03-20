#!/usr/bin/env python3
import riot_web_tools.utils.log as log
from riot_web_tools.protocol.model.message import *
import riot_web_tools.protocol.codec.codec as codec

log.log_level=log.Level.TRACE
log.enable_asserts=True

dummy_sender: Address = ClientAddress()
dummy_receiver: Address = DeviceAddress("DummyDevice")

dummy_messages: list[Message] = [
    MessageConnect(
        dummy_sender
    ),
    MessageConnectAck(),
    MessageDisconnect(),
    MessageDeviceRequest(
        sender=dummy_sender,
        receiver=dummy_receiver
    ),
    MessageDeviceRequestAck(
        sender=dummy_sender,
        receiver=dummy_receiver
    ),
    MessageShellRequest(
        sender=dummy_sender,
        receiver=dummy_receiver
    ),
    MessageShellRequestAck(
        sender=dummy_receiver,
        receiver=dummy_sender
    ),
    MessageLinkTermination(
        sender=dummy_sender,
        receiver=dummy_receiver,
        termination_type=TerminationType.ERROR,
        termination_message="Test log message"
    ),
    MessageFlash(
        sender=dummy_sender,
        receiver=dummy_receiver,
        board="esp32-wroom-32",
        binaries={0x00: b"\xDE\xAD\xBE\xEF"},
        args="--flash-args"
    ),
    MessageFlashRequest(
        sender=dummy_sender,
        receiver=dummy_receiver,
        board="esp32-wroom-32",
        project_path="/path/to/project"
    ),
    MessageTerm(
        sender=dummy_sender,
        receiver=dummy_receiver,
        board="esp32-wroom-32",
        baud_rate=115200
    ),
    MessageTermRequest(
        sender=dummy_sender,
        receiver=dummy_receiver,
        board="esp32-wroom-32",
        project_path="/path/to/project"
    ),
    MessageLog(
        sender=dummy_sender,
        receiver=dummy_receiver,
        log_type=LogType.LOG,
        log_msg="This is a log message"
    ),
    MessageInput(
        sender=dummy_sender,
        receiver=dummy_receiver,
        input_msg="User input message"
    )
]

def individual_test(message: Message) -> None:
    log.info(f"{message.__class__.__name__} encoding/decoding...")
    message_encoded = codec.encode(message)
    message_decoded = codec.decode(message_encoded)
    message_reencoded = codec.encode(message_decoded)
    log.trace(str(message_decoded))
    log.err_assert(message_reencoded == message_encoded, f"{message.__class__.__name__} encoding/decoding failed")

def test_all() -> None:
    for message in dummy_messages:
        individual_test(message)
    log.info("All protocol message tests passed!")