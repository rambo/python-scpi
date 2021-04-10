""""Driver" for http://prologix.biz/gpib-usb-controller.html GPIB controller"""
from typing import Optional, Sequence, List, Any, Tuple, cast
import asyncio
import logging
from dataclasses import dataclass

import serial  # type: ignore
import serial.threaded  # type: ignore

from ..rs232 import RS232SerialProtocol, RS232Transport
from .base import GPIBTransport, AddressTuple

SCAN_DEVICE_TIMEOUT = 0.5
READ_TIMEOUT = 1.0
LOGGER = logging.getLogger(__name__)


class PrologixRS232SerialProtocol(RS232SerialProtocol):
    """Basically the same deal as with the stock RS232 PySerial "protocol" but different EOL"""

    TERMINATOR = b"\n"


@dataclass
class PrologixGPIBTransport(GPIBTransport, RS232Transport):
    """Transport "driver" for the Prologix USB-GPIB controller (v6 protocol)"""

    def __post_init__(self) -> None:
        """Init the serial and controller"""
        self._serialhandler = serial.threaded.ReaderThread(self.serialdevice, PrologixRS232SerialProtocol)
        self._serialhandler.start()
        self._serialhandler.protocol.handle_line = self.message_received
        self.initialize_controller()

    def initialize_controller(self) -> None:
        """Initializes the controller to known state"""
        if not self._serialhandler:
            raise RuntimeError("Serialhandler isn't")
        # Set to controller mode
        self._serialhandler.protocol.write_line("++mode 1")
        # Disable automatic read after write
        self._serialhandler.protocol.write_line("++auto 0")
        # Auto-assert End Of Instruction after commands
        self._serialhandler.protocol.write_line("++eoi 1")
        # Append CRLF to device commands (EOI above *should* be enough but this is probably more compatible)
        self._serialhandler.protocol.write_line("++eos 0")
        # We do not have parsing support for the EOT character so disable it
        self._serialhandler.protocol.write_line("++eot_enable 0")
        # Set inter-character timeout for read commands
        self._serialhandler.protocol.write_line("++read_tmo_ms 500")
        # Assert IFC, make us Controller In Charge
        self._serialhandler.protocol.write_line("++ifc")

    async def send_command(self, command: str) -> None:
        """Wrapper for write_line on the protocol with some sanity checks"""
        if not self._serialhandler or not self._serialhandler.is_alive():
            raise RuntimeError("Serial handler not ready")
        async with self.lock:
            self._serialhandler.protocol.write_line(command)

    async def get_response(self) -> str:
        """Get device response"""
        return await self.send_and_read("++read eoi")

    async def send_and_read(self, send: str) -> str:
        """Send a line, read the response. NOTE: This is for talking with the controller, device responses
        need to use get_response as usual"""
        if not self._serialhandler:
            raise RuntimeError("Serialhandler isn't")

        async def _send_and_read(send: str) -> str:
            """Wrap the actual work"""
            nonlocal self
            if not self._serialhandler:
                raise RuntimeError("Serialhandler isn't")

            async with self.lock:
                response: Optional[str] = None

                def set_response(message: str) -> None:
                    """Callback for setting the response"""
                    nonlocal response, self
                    response = message
                    self.blevent.set()

                self.blevent.clear()
                self.message_callback = set_response
                self._serialhandler.protocol.write_line(send)
                await asyncio.get_event_loop().run_in_executor(None, self.blevent.wait)
                self.message_callback = None
                return cast(str, response)

        return await asyncio.wait_for(_send_and_read(send), timeout=READ_TIMEOUT)

    async def set_address(self, primary: int, secondary: Optional[int] = None) -> None:
        """Set the address we want to talk to"""
        if secondary is None:
            await self.send_command(f"++addr {primary:d}")
        else:
            await self.send_command(f"++addr {primary:d} {secondary:d}")

        while True:
            await asyncio.sleep(0.001)
            resp = await self.query_address()
            if resp == (primary, secondary):
                break

    async def query_address(self) -> AddressTuple:
        """Query the address we are talking to, returns tuple with primary and secondary parts
        secondary is None if not set"""
        resp = await self.send_and_read("++addr")
        parts = resp.split(" ")
        primary = int(parts[0])
        secondary: Optional[int] = None
        if len(parts) > 1:
            secondary = int(parts[1])
        return (primary, secondary)

    async def send_scd(self) -> None:
        """Sends the Selected Device Clear (SDC) message to the currently specified GPIB address"""
        await self.send_command("++clr")

    async def send_ifc(self) -> None:
        """Asserts GPIB IFC signal"""
        await self.send_command("++ifc")

    async def send_llo(self) -> None:
        """Send LLO (disable front panel) to currently specified address"""
        await self.send_command("++llo")

    async def send_loc(self) -> None:
        """Send LOC (enable front panel) to currently specified address"""
        await self.send_command("++loc")

    async def get_srq(self) -> int:
        """Get SRQ assertion status"""
        resp = await self.send_and_read("++srq")
        return int(resp)

    async def poll(self) -> int:
        """Do serial poll on the selected device"""
        resp = await self.send_and_read("++spoll")
        return int(resp)

    async def send_group_trig(self, addresses: Optional[Sequence[int]] = None) -> None:  # pylint: disable=W0221
        """Send trigger to listed addresses

        For some reason Prologix does not trigger the whole bus but only listed devices (if none listed then
        the currently selected device is used)"""
        if addresses is None:
            return await self.send_command("++trg")
        await self.send_command("++trg " + " ".join((str(x) for x in addresses)))

    async def scan_devices(self) -> Sequence[Tuple[int, str]]:
        """Scan for devices in the bus.
        Returns list of addresses and identifiers for found primary addresses (0-30)"""
        if not self._serialhandler:
            raise RuntimeError("Serialhandler isn't")
        found_addresses: List[int] = []
        # We do not lock on this level since the commands we use need to manipulate the lock
        prev_addr = await self.query_address()
        prev_read_tmo_ms = int(await self.send_and_read("++read_tmo_ms"))
        new_read_tmo_ms = int((SCAN_DEVICE_TIMEOUT / 2) * 1000)
        self._serialhandler.protocol.write_line(f"++read_tmo_ms {new_read_tmo_ms:d}")
        for addr in range(0, 31):  # 0-30 inclusive

            async def _scan_addr(addr: int) -> None:
                """Sacn single address"""
                nonlocal found_addresses, self
                await self.set_address(addr)
                await self.poll()
                found_addresses.append(addr)

            try:
                await asyncio.wait_for(_scan_addr(addr), timeout=SCAN_DEVICE_TIMEOUT)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        self._serialhandler.protocol.write_line(f"++read_tmo_ms {prev_read_tmo_ms:d}")
        # Wait a moment for things to settle
        await asyncio.sleep(float(prev_read_tmo_ms) / 1000)
        # Get ids for the devices we found
        ret = []
        for addr in found_addresses:
            await self.set_address(addr)
            await self.send_command("*IDN?")
            idstr = await self.get_response()
            ret.append((addr, idstr))
        await self.set_address(*prev_addr)
        return ret

    async def abort_command(self) -> None:
        """Not implemented for prologix"""
        LOGGER.debug("not implemented on PrologixGPIBTransport")


def get(serial_url: str, **serial_kwargs: Any) -> PrologixGPIBTransport:
    """Shorthand for creating the port from url and initializing the transport"""
    port = serial.serial_for_url(serial_url, **serial_kwargs)
    return PrologixGPIBTransport(serialdevice=port)
