"""Serial port transport layer"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Self, cast, override

import serial
import serial.threaded

from .baseclass import BaseTransport

LOGGER = logging.getLogger(__name__)
WRITE_TIMEOUT = 1.0


class RS232SerialProtocol(serial.threaded.LineReader):
    """PySerial "protocol" class for handling stuff"""

    ENCODING = "ascii"

    @override
    def connection_made(self, transport: serial.threaded.ReaderThread[Self]) -> None:
        """Overridden to make sure we have write_timeout set"""
        super().connection_made(transport)
        # Make sure we have a write timeout of expected size
        transport.serial.write_timeout = WRITE_TIMEOUT

    @override
    def handle_line(self, line: str) -> None:
        raise RuntimeError("This should have been overloaded by RS232Transport")


@dataclass
class RS232Transport(BaseTransport):
    """Uses PySerials ReaderThread in the background to save us some pain"""

    serialdevice: serial.Serial | None = field(default=None)
    _serialhandler: serial.threaded.ReaderThread[RS232SerialProtocol] | None = field(default=None, repr=False)
    _protocol_type: ClassVar[type[RS232SerialProtocol]] = RS232SerialProtocol

    def __post_init__(self) -> None:
        """Initialize the transport"""
        if not self.serialdevice:
            raise ValueError("serialdevice must be given")

        def protocol_factory() -> RS232SerialProtocol:
            protocol = self._protocol_type()
            # Adapt LineReader's `line` keyword to message_received's `message`.
            protocol.handle_line = lambda line: self.message_received(line)  # noqa: PLW0108
            return protocol

        self._serialhandler = serial.threaded.ReaderThread(self.serialdevice, protocol_factory)
        self._serialhandler.start()
        self._serialhandler.connect()

    @override
    async def send_command(self, command: str) -> None:
        """Wrapper for write_line on the protocol with some sanity checks"""
        if not self._serialhandler or not self._serialhandler.is_alive():
            raise RuntimeError("Serial handler not ready")
        async with self.lock:
            self._serialhandler.protocol.write_line(command)

    @override
    async def get_response(self) -> str:
        """Serial devices send responses without needing to be told to, just reads it"""
        # TODO: we probably have a race-condition possibility here, maybe always put all received
        # messages to a stack and return popleft ??
        async with self.lock:
            response: str | None = None

            def set_response(message: str) -> None:
                """Callback for setting the response"""
                nonlocal response, self
                response = message
                self.blevent.set()

            self.blevent.clear()
            self.message_callback = set_response
            await asyncio.get_event_loop().run_in_executor(None, self.blevent.wait)
            self.message_callback = None
            return cast(str, response)

    @override
    async def abort_command(self) -> None:
        """Uses the break-command to issue "Device clear", from the SCPI documentation (for HP6632B):
        The status registers, the error queue, and all configuration states are left unchanged when a device
        clear message is received. Device clear performs the following actions:
             - The input and output buffers of the dc source are cleared.
             - The dc source is prepared to accept a new command string."""
        if not self._serialhandler:
            raise RuntimeError("No serialhandler")
        if not self._serialhandler.serial:
            raise RuntimeError("No serialhandler.serial")
        async with self.lock:
            self._serialhandler.serial.send_break()

    @override
    async def quit(self) -> None:
        """Closes the port and background threads"""
        if not self._serialhandler:
            raise RuntimeError("No serialhandler")
        if not self._serialhandler.serial:
            raise RuntimeError("No serialhandler.serial")
        self._serialhandler.close()


def get(serial_url: str, **serial_kwargs: Any) -> RS232Transport:
    """Shorthand for creating the port from url and initializing the transport"""
    port = serial.serial_for_url(serial_url, **serial_kwargs)
    return RS232Transport(serialdevice=port)
