"""Serial port transport layer"""

from __future__ import annotations
from typing import Optional, Any, Dict, cast
import asyncio
import logging
from dataclasses import field, dataclass

import serial  # type: ignore
import serial.threaded  # type: ignore

from .baseclass import BaseTransport

LOGGER = logging.getLogger(__name__)
WRITE_TIMEOUT = 1.0


class RS232SerialProtocol(serial.threaded.LineReader):  # type: ignore
    """PySerial "protocol" class for handling stuff"""

    ENCODING = "ascii"

    def connection_made(self, transport: RS232Transport) -> None:
        """Overridden to make sure we have write_timeout set"""
        super().connection_made(transport)
        # Make sure we have a write timeout of expected size
        self.transport.write_timeout = WRITE_TIMEOUT

    def handle_line(self, line: str) -> None:
        raise RuntimeError("This should have been overloaded by RS232Transport")


@dataclass
class RS232Transport(BaseTransport):
    """Uses PySerials ReaderThread in the background to save us some pain"""

    serialdevice: Optional[serial.SerialBase] = field(default=None)
    _serialhandler: Optional[serial.threaded.ReaderThread] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Initialize the transport"""
        if not self.serialdevice:
            raise ValueError("serialdevice must be given")
        self._serialhandler = serial.threaded.ReaderThread(self.serialdevice, RS232SerialProtocol)
        self._serialhandler.start()
        self._serialhandler.protocol.handle_line = self.message_received

    async def send_command(self, command: str) -> None:
        """Wrapper for write_line on the protocol with some sanity checks"""
        if not self._serialhandler or not self._serialhandler.is_alive():
            raise RuntimeError("Serial handler not ready")
        async with self.lock:
            self._serialhandler.protocol.write_line(command)

    async def get_response(self) -> str:
        """Serial devices send responses without needing to be told to, just reads it"""
        # TODO: we probably have a race-condition possibility here, maybe always put all received
        # messages to a stack and return popleft ??
        async with self.lock:
            response: Optional[str] = None

            # pylint: disable=R0801
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

    async def quit(self) -> None:
        """Closes the port and background threads"""
        if not self._serialhandler:
            raise RuntimeError("No serialhandler")
        if not self._serialhandler.serial:
            raise RuntimeError("No serialhandler.serial")
        self._serialhandler.close()


def get(serial_url: str, **serial_kwargs: Dict[str, Any]) -> RS232Transport:
    """Shorthand for creating the port from url and initializing the transport"""
    port = serial.serial_for_url(serial_url, **serial_kwargs)
    return RS232Transport(serialdevice=port)
