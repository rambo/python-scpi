"""Serial transport backed by pyserial-asyncio."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, ClassVar, override

import serial
import serial_asyncio

from .baseclass import BaseTransport

WRITE_TIMEOUT = 1.0


@dataclass
class RS232Transport(BaseTransport):
    """Attach an existing serial port to the running loop on first use."""

    serialdevice: serial.Serial | None = field(default=None)
    _terminator: ClassVar[bytes] = b"\r\n"
    _writer: asyncio.StreamWriter | None = field(default=None, init=False, repr=False)
    _read_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    # ponytail: unbounded replies; add backpressure for continuously streaming devices.
    _responses: asyncio.Queue[str | Exception] = field(default_factory=asyncio.Queue, init=False, repr=False)
    _read_error: Exception | None = field(default=None, init=False, repr=False)
    _receiving: bool = field(default=False, init=False)
    _closed: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.serialdevice is None:
            raise ValueError("serialdevice must be given")

    async def _connect(self) -> None:
        """Called under the transport lock, so initialization happens only once."""
        if self._closed:
            raise RuntimeError("Serial transport is closed")
        if self._writer is not None:
            return
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await serial_asyncio.connection_for_serial(loop, lambda: protocol, self.serialdevice)
        self._writer = asyncio.StreamWriter(transport, protocol, reader, loop)
        self._read_task = asyncio.create_task(self._read_lines(reader))
        try:
            await self._initialize()
        except BaseException:
            await self.quit()
            raise

    async def _initialize(self) -> None:
        """Hook for serial controllers that need startup commands."""

    async def _read_lines(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                line = await reader.readuntil(self._terminator)
                self.message_received(line[: -len(self._terminator)].decode("ascii", errors="replace"))
        except Exception as exc:
            self._read_error = exc
            self._responses.put_nowait(exc)

    @override
    def message_received(self, message: str) -> None:
        """Keep early replies while retaining explicit callback support."""
        if self.message_callback is not None or (self.unsolicited_message_callback is not None and not self._receiving):
            super().message_received(message)
        else:
            self._responses.put_nowait(message)

    async def _write_line(self, command: str) -> None:
        if self._writer is None or self._writer.is_closing():
            raise RuntimeError("Serial transport is not connected")
        self._writer.write(command.encode("ascii", errors="replace") + self._terminator)
        await asyncio.wait_for(self._writer.drain(), timeout=WRITE_TIMEOUT)

    @override
    async def send_command(self, command: str) -> None:
        async with self.lock:
            await self._connect()
            await self._write_line(command)

    async def _read_response(self) -> str:
        if self._responses.empty() and self._read_error is not None:
            raise self._read_error
        self._receiving = True
        try:
            response = await self._responses.get()
        finally:
            self._receiving = False
        if isinstance(response, Exception):
            raise response
        return response

    @override
    async def get_response(self) -> str:
        async with self.lock:
            await self._connect()
            return await self._read_response()

    @override
    async def abort_command(self) -> None:
        """Send a serial BREAK without blocking the event loop."""
        async with self.lock:
            await self._connect()
            assert self.serialdevice is not None
            self.serialdevice.break_condition = True
            try:
                await asyncio.sleep(0.25)
            finally:
                self.serialdevice.break_condition = False

    @override
    async def quit(self) -> None:
        """Close the port and wake pending reads; safe before first use or repeatedly."""
        if self._closed:
            return
        self._closed = True
        self._read_error = ConnectionError("Serial transport is closed")
        self._responses.put_nowait(self._read_error)
        if self._read_task is not None:
            self._read_task.cancel()
            await asyncio.gather(self._read_task, return_exceptions=True)
        if self._writer is not None:
            self._writer.close()
            await self._writer.wait_closed()
        elif self.serialdevice is not None:
            self.serialdevice.close()


def get(serial_url: str, **serial_kwargs: Any) -> RS232Transport:
    """Open the port synchronously; attach async I/O when the transport is used."""
    port = serial.serial_for_url(serial_url, **serial_kwargs)
    return RS232Transport(serialdevice=port)
