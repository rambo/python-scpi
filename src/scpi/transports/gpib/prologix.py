""" "Driver" for http://prologix.biz/gpib-usb-controller.html GPIB controller"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, override

import serial

from ..rs232 import RS232Transport
from .base import AddressTuple, GPIBTransport

SCAN_DEVICE_TIMEOUT = 0.5
READ_TIMEOUT = 1.0
LOGGER = logging.getLogger(__name__)


@dataclass
class PrologixGPIBTransport(GPIBTransport, RS232Transport):
    """Transport "driver" for the Prologix USB-GPIB controller (v6 protocol)"""

    _terminator = b"\n"

    @override
    async def _initialize(self) -> None:
        await self._initialize_controller()

    async def _initialize_controller(self) -> None:
        # Controller mode, manual reads, EOI, CRLF, no EOT, timeout, then IFC.
        for command in ("++mode 1", "++auto 0", "++eoi 1", "++eos 0", "++eot_enable 0", "++read_tmo_ms 500", "++ifc"):
            await self._write_line(command)

    async def initialize_controller(self) -> None:
        """Reset the controller; first use initializes it automatically."""
        async with self.lock:
            if self._writer is None:
                await self._connect()
            else:
                await self._initialize_controller()

    @override
    async def get_response(self) -> str:
        """Request a device response from the controller."""
        return await self.send_and_read("++read eoi")

    async def send_and_read(self, send: str) -> str:
        """Keep a controller command and its response under one lock and timeout."""
        async with asyncio.timeout(READ_TIMEOUT):
            async with self.lock:
                await self._connect()
                self._receiving = True
                try:
                    await self._write_line(send)
                    return await self._read_response()
                finally:
                    self._receiving = False

    @override
    async def set_address(self, primary: int, secondary: int | None = None) -> None:
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

    @override
    async def query_address(self) -> AddressTuple:
        """Query the address we are talking to, returns tuple with primary and secondary parts
        secondary is None if not set"""
        resp = await self.send_and_read("++addr")
        parts = resp.split(" ")
        primary = int(parts[0])
        secondary: int | None = None
        if len(parts) > 1:
            secondary = int(parts[1])
        return (primary, secondary)

    @override
    async def send_scd(self) -> None:
        """Sends the Selected Device Clear (SDC) message to the currently specified GPIB address"""
        await self.send_command("++clr")

    @override
    async def send_ifc(self) -> None:
        """Asserts GPIB IFC signal"""
        await self.send_command("++ifc")

    @override
    async def send_llo(self) -> None:
        """Send LLO (disable front panel) to currently specified address"""
        await self.send_command("++llo")

    @override
    async def send_loc(self) -> None:
        """Send LOC (enable front panel) to currently specified address"""
        await self.send_command("++loc")

    @override
    async def get_srq(self) -> int:
        """Get SRQ assertion status"""
        resp = await self.send_and_read("++srq")
        return int(resp)

    @override
    async def poll(self) -> int:
        """Do serial poll on the selected device"""
        resp = await self.send_and_read("++spoll")
        return int(resp)

    @override
    async def send_group_trig(self, addresses: Sequence[int] | None = None) -> None:
        """Send trigger to listed addresses

        For some reason Prologix does not trigger the whole bus but only listed devices (if none listed then
        the currently selected device is used)"""
        if addresses is None:
            return await self.send_command("++trg")
        await self.send_command("++trg " + " ".join(str(x) for x in addresses))

    @override
    async def scan_devices(self) -> Sequence[tuple[int, str]]:
        """Scan for devices in the bus.
        Returns list of addresses and identifiers for found primary addresses (0-30)"""
        found_addresses: list[int] = []
        # We do not lock on this level since the commands we use need to manipulate the lock
        prev_addr = await self.query_address()
        prev_read_tmo_ms = int(await self.send_and_read("++read_tmo_ms"))
        new_read_tmo_ms = int((SCAN_DEVICE_TIMEOUT / 2) * 1000)
        await self.send_command(f"++read_tmo_ms {new_read_tmo_ms:d}")
        for addr in range(0, 31):  # 0-30 inclusive

            async def _scan_addr(addr: int) -> None:
                """Sacn single address"""
                nonlocal found_addresses, self
                await self.set_address(addr)
                await self.poll()
                found_addresses.append(addr)

            try:
                await asyncio.wait_for(_scan_addr(addr), timeout=SCAN_DEVICE_TIMEOUT)
            except (TimeoutError, asyncio.CancelledError):
                pass
        await self.send_command(f"++read_tmo_ms {prev_read_tmo_ms:d}")
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

    @override
    async def abort_command(self) -> None:
        """Not implemented for prologix"""
        LOGGER.debug("not implemented on PrologixGPIBTransport")


def get(serial_url: str, **serial_kwargs: Any) -> PrologixGPIBTransport:
    """Shorthand for creating the port from url and initializing the transport"""
    port = serial.serial_for_url(serial_url, **serial_kwargs)
    return PrologixGPIBTransport(serialdevice=port)
