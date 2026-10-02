"""Exercise real pyserial-asyncio I/O through POSIX pseudo-terminals."""

import asyncio
import contextlib
import os
from collections.abc import Iterator

import pytest
import serial

from scpi.devices.owh9830 import _SerialTransport
from scpi.transports.gpib.prologix import PrologixGPIBTransport
from scpi.transports.rs232 import RS232Transport, get
from scpi.wrapper import AIOWrapper

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Pseudo-terminals require POSIX")
STARTUP = b"++mode 1\n++auto 0\n++eoi 1\n++eos 0\n++eot_enable 0\n++read_tmo_ms 500\n++ifc\n"


@contextlib.contextmanager
def serial_peer() -> Iterator[tuple[int, str]]:
    master, slave = os.openpty()
    os.set_blocking(master, False)
    try:
        yield master, os.ttyname(slave)
    finally:
        for descriptor in (master, slave):
            with contextlib.suppress(OSError):
                os.close(descriptor)


async def read_peer(master: int, expected: bytes) -> None:
    """Wait for the bytes sent to the virtual instrument without blocking."""
    received = b""
    async with asyncio.timeout(2):
        while len(received) < len(expected):
            try:
                received += os.read(master, 4096)
            except BlockingIOError:
                await asyncio.sleep(0.001)
    assert received == expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("transport_type", "terminator", "startup"),
    [(RS232Transport, b"\r\n", b""), (PrologixGPIBTransport, b"\n", STARTUP), (_SerialTransport, b"\n", b"")],
)
async def test_serial_exchange(transport_type: type[RS232Transport], terminator: bytes, startup: bytes) -> None:
    """Verify initialization, framing, fragmented input and replies received before reads."""
    with serial_peer() as (master, path):
        port = serial.serial_for_url(path)
        transport = transport_type(serialdevice=port)
        try:
            async with asyncio.timeout(2):
                await transport.send_command("*IDN?")
                await read_peer(master, startup + b"*IDN?" + terminator)
                assert port.timeout == 0
                assert port.write_timeout == 0
                os.write(master, b"fir")
                await asyncio.sleep(0.01)
                os.write(master, b"st" + terminator + b"second" + terminator)
                await asyncio.sleep(0.01)
                assert await transport.get_response() == "first"
                assert await transport.get_response() == "second"
                if startup:
                    await read_peer(master, b"++read eoi\n++read eoi\n")
                if isinstance(transport, PrologixGPIBTransport):
                    await transport.initialize_controller()
                    await read_peer(master, STARTUP)
        finally:
            await transport.quit()
        await transport.quit()
        assert not port.is_open
        assert transport._read_task is not None and transport._read_task.done()


@pytest.mark.asyncio
@pytest.mark.parametrize("transport_type", [RS232Transport, PrologixGPIBTransport])
async def test_cancelled_read(transport_type: type[RS232Transport]) -> None:
    """Cancelling a response wait leaves the next read usable."""
    with serial_peer() as (master, path):
        transport = transport_type(serialdevice=serial.serial_for_url(path))
        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(transport.get_response(), 0.02)
            if isinstance(transport, PrologixGPIBTransport):
                await read_peer(master, STARTUP + b"++read eoi\n")
            os.write(master, b"next" + transport._terminator)
            assert await asyncio.wait_for(transport.get_response(), 2) == "next"
            if isinstance(transport, PrologixGPIBTransport):
                await read_peer(master, b"++read eoi\n")
        finally:
            await transport.quit()


@pytest.mark.asyncio
async def test_callbacks_and_close_pending_read() -> None:
    with serial_peer() as (master, path):
        transport = get(path)
        received: list[str] = []
        transport.unsolicited_message_callback = received.append
        try:
            await transport.send_command("command")
            await read_peer(master, b"command\r\n")
            os.write(master, b"notice\r\n")
            async with asyncio.timeout(2):
                while not received:
                    await asyncio.sleep(0.001)
            assert received == ["notice"]
            pending = asyncio.create_task(transport.get_response())
            await asyncio.sleep(0)
            os.write(master, b"response\r\n")
            assert await asyncio.wait_for(pending, 2) == "response"
            pending = asyncio.create_task(transport.get_response())
            await asyncio.sleep(0)
            await transport.quit()
            with pytest.raises(ConnectionError, match="closed"):
                await asyncio.wait_for(pending, 2)
        finally:
            await transport.quit()


@pytest.mark.asyncio
async def test_disconnect() -> None:
    with serial_peer() as (master, path):
        transport = get(path)
        try:
            pending = asyncio.create_task(transport.get_response())
            await asyncio.sleep(0.01)
            os.close(master)
            with pytest.raises(serial.SerialException):
                await asyncio.wait_for(pending, 2)
            with pytest.raises(serial.SerialException):
                await transport.get_response()
        finally:
            with contextlib.suppress(serial.SerialException):
                await transport.quit()


def test_blocking_wrapper_and_unused_close() -> None:
    """Factories still work before a loop exists, including through AIOWrapper."""
    with serial_peer() as (master, path):
        transport = get(path, baudrate=9600, rtscts=False)
        wrapper = AIOWrapper(transport)
        try:
            wrapper.send_command("hello")
            wrapper.loop.run_until_complete(read_peer(master, b"hello\r\n"))
            os.write(master, b"reply\r\n")
            assert wrapper.get_response() == "reply"
        finally:
            wrapper.quit()
        unused = get(path)
        asyncio.run(unused.quit())
        assert unused.serialdevice is not None and not unused.serialdevice.is_open


@pytest.mark.asyncio
async def test_cancelled_break() -> None:
    """A cancelled BREAK must not leave the instrument's serial line asserted."""
    with serial_peer() as (_, path):
        transport = get(path)
        try:
            pending = asyncio.create_task(transport.abort_command())
            await asyncio.sleep(0)
            assert transport.serialdevice is not None
            assert transport.serialdevice.break_condition
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            assert not transport.serialdevice.break_condition
        finally:
            await transport.quit()
