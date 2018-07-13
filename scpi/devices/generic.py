"""Mixins for different device functionalities"""
import decimal

from ..scpi import SCPIDevice


class MultiMeter(SCPIDevice):
    """Multimeter related features"""

    async def measure_voltage(self, extra_params=""):
        """Returns the measured (scalar) actual output voltage (in volts),
        pass extra_params string to append to the command (like ":ACDC")"""
        resp = await self.ask("MEAS:SCAL:VOLT%s?" % extra_params)
        return decimal.Decimal(resp)

    async def measure_current(self, extra_params=""):
        """Returns the measured (scalar) actual output current (in amps),
        pass extra_params string to append to the command (like ":ACDC")"""
        resp = await self.ask("MEAS:SCAL:CURR%s?" % extra_params)
        return decimal.Decimal(resp)

    async def set_measure_current_max(self, amps):
        """Sets the upper bound (in amps) of current to measure,
        on some devices low-current accuracy can be increased by keeping this low"""
        await self.command("SENS:CURR:RANG %f" % amps)

    async def query_measure_current_max(self):
        """Returns the upper bound (in amps) of current to measure,
        this is not neccessarily same number as set with set_measure_current_max"""
        resp = await self.ask("SENS:CURR:RANG?")
        return decimal.Decimal(resp)


class PowerSupply(SCPIDevice):
    """Power supply related features"""

    async def set_voltage(self, millivolts, extra_params=""):
        """Sets the desired output voltage (but does not auto-enable outputs) in millivolts,
        pass extra_params string to append to the command (like ":PROT")"""
        await self.command("SOUR:VOLT%s %f MV" % (extra_params, millivolts))

    async def query_voltage(self, extra_params=""):
        """Returns the set output voltage (in volts),
        pass extra_params string to append to the command (like ":PROT")"""
        resp = await self.ask("SOUR:VOLT%s?" % extra_params)
        return decimal.Decimal(resp)

    async def set_current(self, milliamps, extra_params=""):
        """Sets the desired output current (but does not auto-enable outputs) in milliamps,
        pass extra_params string to append to the command (like ":TRIG")"""
        await self.command("SOUR:CURR%s %f MA" % (extra_params, milliamps))

    async def query_current(self, extra_params=""):
        """Returns the set output current (in amps),
        pass extra_params string to append to the command (like ":TRIG")"""
        resp = await self.ask("SOUR:CURR%s?" % extra_params)
        return decimal.Decimal(resp)

    async def set_output(self, state):
        """Enables/disables output"""
        await self.command("OUTP:STAT %d" % state)

    async def query_output(self):
        """Returns the output state"""
        resp = await self.ask("OUTP:STAT?")
        return bool(int(resp))
