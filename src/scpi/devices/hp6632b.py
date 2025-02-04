"""HP/Agilent 3362B specific device implementation and helpers"""

from typing import Any
import logging
import decimal

from ..scpi import SCPIDevice, SCPIProtocol
from ..transports.rs232 import RS232Transport
from ..transports.rs232 import get as get_rs232
from .generic import MultiMeter, PowerSupply

LOGGER = logging.getLogger(__name__)


class HP6632B(PowerSupply, MultiMeter, SCPIDevice):
    """Adds the HP/Agilent 3362B specific SCPI commands as methods"""

    async def set_low_current_mode(self, state: bool) -> None:
        """The low-current mode is enabled by setting the range to (max) 20mA, anything over that is high-current mode.
        This model has max 5A output"""
        if state:
            return await self.set_measure_current_max(0.020)
        return await self.set_measure_current_max(5.0)

    async def query_low_current_mode(self) -> bool:
        """Returns boolean indicating whether we are in low or high current mode"""
        max_current = await self.query_measure_current_max()
        if max_current <= 0.020:
            return True
        return False

    async def measure_current_autorange(self, extra_params: str = "") -> decimal.Decimal:
        """Measures the current, then make sure we are running on the correct measurement range
        and if not switch range and measure again"""
        ret = await self.measure_current(extra_params)
        if abs(ret) < 0.020:
            # We need to be in low-current mode
            if not await self.query_low_current_mode():
                # Enter low current mode and measure again
                await self.set_low_current_mode(True)
                return await self.measure_current(extra_params)
            return ret
        # We need to be in high-current mode
        if await self.query_low_current_mode():
            # Switch mode and measure again
            await self.set_low_current_mode(False)
            return await self.measure_current(extra_params)
        return ret

    def ensure_transport_is_rs232(self) -> None:
        """Ensures transport is RS232, raises error if not"""
        if not isinstance(self.protocol.transport, RS232Transport):
            raise RuntimeError("Only usable with RS232 transports")

    async def set_remote_mode(self, state: bool = True) -> None:
        """RS232 only, prevent accidental button mashing on the fron panel, this switches between SYSTem:REMote
        and SYSTem:LOCal according to state, this overrides previous value set with set_rwlock"""
        self.ensure_transport_is_rs232()
        if state:
            return await self.command("SYST:REM")
        return await self.command("SYST:LOC")

    async def set_rwlock(self, state: bool = True) -> None:
        """RS232 only, prevent *any* button mashing on the fron panel, this switches between SYSTem:RWLock
        and SYSTem:LOCal according to state, this overrides previous value set with set_remote_mode"""
        self.ensure_transport_is_rs232()
        if state:
            return await self.command("SYST:RWL")
        return await self.command("SYST:LOC")

    async def display_on(self, state: bool = True) -> None:
        """Sets display on/off"""
        if state:
            return await self.command("DISP ON")
        return await self.command("DISP OFF")

    async def set_display_mode(self, mode: str) -> None:
        """Set the display mode, valied values are NORM and TEXT"""
        mode = mode.upper()
        if mode not in ("NORM", "TEXT"):
            raise ValueError("Invalid mode %s, valid ones are NORM and TEXT" % mode)
        return await self.command(f"DISP:MODE {mode}")

    async def set_display_text(self, text: str) -> None:
        """Used to display text on the display, max 14 characters,
        NOTE: does *not* set display mode, you need to do it yourself"""
        if len(text) > 14:
            raise ValueError("Max text length is 14 characters")
        if '"' in text and "'" in text:
            raise ValueError("Text may only contain either single or double quotes, not both")
        if '"' in text:
            return await self.command(f"DISP:TEXT '{text}'")
        return await self.command(f"""DISP:TEXT  "{text}" """.strip())


def rs232(serial_url: str, **kwargs: Any) -> HP6632B:
    """Quick helper to connect via RS232 port"""
    transport = get_rs232(serial_url, **kwargs)
    protocol = SCPIProtocol(transport)
    dev = HP6632B(protocol)
    return dev
