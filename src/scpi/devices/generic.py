"""Mixins for different device functionalities"""

import decimal

from ..scpi import SCPIDevice


class MultiMeter(SCPIDevice):
    """Multimeter related features"""

    async def measure_voltage(self, extra_params: str = "") -> decimal.Decimal:
        """Returns the measured (scalar) actual output voltage (in volts),
        pass extra_params string to append to the command (like ":ACDC")"""
        resp = await self.ask(f"MEAS:SCAL:VOLT{extra_params}?")
        return decimal.Decimal(resp)

    async def measure_current(self, extra_params: str = "") -> decimal.Decimal:
        """Returns the measured (scalar) actual output current (in amps),
        pass extra_params string to append to the command (like ":ACDC")"""
        resp = await self.ask(f"MEAS:SCAL:CURR{extra_params}?")
        return decimal.Decimal(resp)

    async def set_measure_current_max(self, amps: float) -> None:
        """Sets the upper bound (in amps) of current to measure,
        on some devices low-current accuracy can be increased by keeping this low"""
        await self.command(f"SENS:CURR:RANG {amps:f}")

    async def query_measure_current_max(self) -> decimal.Decimal:
        """Returns the upper bound (in amps) of current to measure,
        this is not neccessarily same number as set with set_measure_current_max"""
        resp = await self.ask("SENS:CURR:RANG?")
        return decimal.Decimal(resp)


class PowerSupply(SCPIDevice):
    """Power supply related features"""

    async def set_voltage(self, millivolts: float, extra_params: str = "") -> None:
        """Sets the desired output voltage (but does not auto-enable outputs) in millivolts,
        pass extra_params string to append to the command (like ":PROT")"""
        await self.command(f"SOUR:VOLT{extra_params} {millivolts:f} MV")

    async def query_voltage(self, extra_params: str = "") -> decimal.Decimal:
        """Returns the set output voltage (in volts),
        pass extra_params string to append to the command (like ":PROT")"""
        resp = await self.ask(f"SOUR:VOLT{extra_params}?")
        return decimal.Decimal(resp)

    async def set_current(self, milliamps: float, extra_params: str = "") -> None:
        """Sets the desired output current (but does not auto-enable outputs) in milliamps,
        pass extra_params string to append to the command (like ":TRIG")"""
        await self.command(f"SOUR:CURR{extra_params} {milliamps:f} MA")

    async def query_current(self, extra_params: str = "") -> decimal.Decimal:
        """Returns the set output current (in amps),
        pass extra_params string to append to the command (like ":TRIG")"""
        resp = await self.ask(f"SOUR:CURR{extra_params}?")
        return decimal.Decimal(resp)

    async def set_output(self, state: bool) -> None:
        """Enables/disables output"""
        await self.command(f"OUTP:STAT {state:d}")

    async def query_output(self) -> bool:
        """Returns the output state"""
        resp = await self.ask("OUTP:STAT?")
        return bool(int(resp))
