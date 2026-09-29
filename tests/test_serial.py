"""Serial startup checks using pyserial's in-memory loopback port."""

import asyncio

import pytest
import serial

from scpi.transports.gpib.prologix import PrologixGPIBTransport, PrologixRS232SerialProtocol
from scpi.transports.rs232 import WRITE_TIMEOUT, RS232SerialProtocol, RS232Transport


@pytest.mark.parametrize(
    ("transport_type", "protocol_type"),
    [(RS232Transport, RS232SerialProtocol), (PrologixGPIBTransport, PrologixRS232SerialProtocol)],
)
def test_serial_startup(transport_type: type[RS232Transport], protocol_type: type[RS232SerialProtocol]) -> None:
    """Construction waits for the correct protocol and sets the actual port timeout."""
    port = serial.serial_for_url("loop://")
    transport = transport_type(serialdevice=port)
    try:
        assert port.write_timeout == WRITE_TIMEOUT
        assert transport._serialhandler is not None
        assert isinstance(transport._serialhandler.protocol, protocol_type)
        received: list[str] = []
        transport.unsolicited_message_callback = received.append
        transport._serialhandler.protocol.handle_line("test")
        assert "test" in received
    finally:
        asyncio.run(transport.quit())
    assert not port.is_open
