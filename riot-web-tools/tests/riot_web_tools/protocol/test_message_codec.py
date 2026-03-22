#!/usr/bin/env python3
import riot_web_tools.utils.log as log
from riot_web_tools.protocol.model.message import *
from riot_web_tools.protocol.model.address import *
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
    MessageRequest(
        sender=dummy_sender,
        receiver=dummy_receiver,
        spawned=True,
        request=RequestFlash("board_str", "project_path")
    ),
    MessageRequest(
        sender=dummy_sender,
        receiver=dummy_receiver,
        spawned=True,
        request=RequestTerm("board_str", "project_path")
    ),
    MessageCommand(
        sender=dummy_sender,
        receiver=dummy_receiver,
        command=CommandFlash("board_str", {0x00: b"empty"}, "args_str")
    ),
    MessageCommand(
        sender=dummy_sender,
        receiver=dummy_receiver,
        command=CommandTerm("board_str", 115200)
    ),
    MessageACK(
        sender=dummy_sender,
        receiver=dummy_receiver
    ),
    MessageReset(
        sender=dummy_sender,
        receiver=dummy_receiver,
        termination_type=TerminationType.ERROR,
        termination_message="term msg"
    ),
    MessageLog(
        sender=dummy_sender,
        receiver=dummy_receiver,
        log_type=LogType.LOG,
        log_msg="This is a log message"
    ),
    MessageIO(
        sender=dummy_sender,
        receiver=dummy_receiver,
        msg=b"User input message"
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