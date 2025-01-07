"""TDK Lambda power supplies"""

# pylint: disable=C0103
from typing import Optional, Union, Any
from dataclasses import dataclass, field
import decimal
import logging

import serial as pyserial  # type: ignore

from ..scpi import SCPIDevice, SCPIProtocol
from ..transports.rs232 import RS232Transport
from ..transports.tcp import get as get_tcp
from .generic import PowerSupply

StrIntCombo = Union[str, int]
LOGGER = logging.getLogger(__name__)


class TDKSCPI(SCPIDevice):
    """Baseclass for TDK SCPI devices"""

    async def set_power_on_status_clear(self, setting: StrIntCombo) -> None:
        """
        Set the Power-On Status Clear setting.
        * ON/1/True - This choice enables the power-on clearing of the listed registers
        * OFF/0/false - This choice disable the clearing of the listed registers and they retain
                        their status when a power-on condition occurs
        """
        setting = str(setting).upper()
        if setting in ("1", "ON", "TRUE"):
            setting = "1"
        elif setting in ("0", "OFF", "FALSE"):
            setting = "0"
        else:
            raise ValueError
        await super().set_power_on_status_clear(setting)

    async def restore_state(self, state: int) -> None:
        """
        Restores the power supply to a state previously stored in memory by *SAV command.
        """
        state = int(state)
        if state not in (1, 2, 3, 4):
            raise ValueError("invalid state")

        await super().restore_state(state)

    async def save_state(self, state: int) -> None:
        """
        The SAV command saves all applied configuration settings.
        """
        state = int(state)
        if state not in (1, 2, 3, 4):
            raise ValueError("Invalid state")

        await super().save_state(state)

    async def power_on_state(self, setting: StrIntCombo) -> None:
        """
        Set the power-on behavior of the system
        * 1 - AUTO - The power supply output will return to its previous value
                     when the latching fault condition is removed or to the
                     stored value after AC recycle.
        * 0 - SAFE - The power supply output will remain Off after the fault
                     condition is removed or after AC recycle.
        """
        setting = str(setting).upper()
        if setting in ("1", "ON", "TRUE"):
            setting = "1"
        elif setting in ("0", "OFF", "FALSE"):
            setting = "0"
        else:
            raise ValueError
        await super().power_on_state(setting)


@dataclass
class TDKLambdaZplus(PowerSupply, TDKSCPI):
    """TDK Lambda Z+ power supply"""

    voltage_limit: float = field(default=20.0)
    current_limit: float = field(default=10.0)

    async def measure_current(self, extra_params: str = "") -> decimal.Decimal:
        """
        Returns the actual output current in amps.

        extra_params: String to append to the command.  The only valid command
                for this device is ":DC"
        """

        resp = await self.ask(f"MEAS:CURR{extra_params}?")
        return decimal.Decimal(resp)

    async def measure_voltage(self, extra_params: str = "") -> decimal.Decimal:
        """
        Returns the actual output voltage in volts.

        extra_params: String to append to the command.  The only valid command
                for this device is ":DC"
        """

        resp = await self.ask(f"MEAS:VOLT{extra_params}?")
        return decimal.Decimal(resp)

    async def measure_power(self, extra_params: str = "") -> decimal.Decimal:
        """
        Returns the actual output power in watts.

        extra_params: String to append to the command.  The only valid command
                for this device is ":DC"
        """

        resp = await self.ask(f"MEAS:POW{extra_params}?")
        return decimal.Decimal(resp)

    async def select_active_instrument(self, select_id: int) -> None:
        """
        Select the power supply for communication.

        id: the ID of the power supply to select.  int from 1-31
        """

        _id = int(select_id)

        if _id < 1 or _id > 31:
            raise ValueError("id %d is outside of the valid id range" % _id)

        await self.command(f"INSTrument:NSELect {_id:d}")

    async def query_active_instrument(self) -> int:
        """
        Returns the ID of the active instrument.
        """

        resp = await self.ask("INSTrument:NSELect?")
        return int(resp)

    async def couple_mode(self, couple: str = "NONE") -> None:
        """
        Couple for all Z+ power supplies.
        """

        couple = couple.upper()

        if couple in ("NONE", "ALL"):
            await self.command("INSTrument:COUPle %s" % couple)
        else:
            raise ValueError("Argument '%s' not valid for INST:COUP" % couple)

    async def set_voltage_protection(self, volts: Any) -> None:
        """
        Set over-voltage protection level.
        """

        _volts = str(volts).upper()
        # FIXME: shouldn't we pass _volts here ?? Also what are valid types/values ??
        await self.command("VOLTage:PROTection:LEVel")

    async def query_voltage_protection(self, mode: Optional[str] = None) -> decimal.Decimal:
        """
        Query the voltage protection level.  Depending on mode, returns the current level, the
        minimum level, or the maximum level.

        mode: Which value to return.
                - None (default): returns the current voltage protection level
                - "MAX": returns the maximum possible voltage protection level
                - "MIN": returns the minimum possible voltage protection level, approx. 105% the
                         current voltage setting
        """

        if mode is None:
            resp = await self.ask("VOLTage:PROTection:LEVel?")
        else:
            resp = await self.ask(f"VOLTage:PROTection:LEVel? {mode}")
        return decimal.Decimal(resp)

    async def flash_display(self, setting: StrIntCombo) -> None:
        """
        Make the front panel voltage and Current displays flash.
        """

        setting = str(setting).upper()
        if setting in ("1", "ON", "TRUE"):
            setting = "1"
        elif setting in ("0", "OFF", "FALSE"):
            setting = "0"
        else:
            raise ValueError
        await self.command(f"DISPlay:FLASh {setting}")

    async def global_enable(self, setting: StrIntCombo) -> None:
        """
        Set enable status of all units.
        """

        setting = str(setting).upper()
        if setting in ("1", "ON", "TRUE"):
            setting = "1"
        elif setting in ("0", "OFF", "FALSE"):
            setting = "0"
        else:
            raise ValueError
        await self.command(f"GLOBal:OUTPut:STATe {setting}")

    async def global_set_voltage(self, volts: float) -> None:
        """
        Set enable status of all units.
        """

        _volts = str(volts)
        # FIXME: probably just using volts:f would work fine
        await self.command(f"GLOBal:VOLTage:AMPLitude {_volts}")

    async def global_reset(self) -> None:
        """
        Reset all units.
        """

        await self.command("GLOBal:*RST")

    async def set_voltage(self, millivolts: float, extra_params: str = "") -> None:
        """
        Sets the desired output voltage (but does not auto-enable outputs) in
        millivolts, pass extra_params string to append to the command (like ":PROT")

        Limited to five percent greater than the voltage limit of the unit.
        """

        if millivolts / 1000.0 > 1.05 * self.voltage_limit or millivolts < 0:
            raise ValueError

        await super().set_voltage(millivolts, extra_params=extra_params)

    async def set_current(self, milliamps: float, extra_params: str = "") -> None:
        """
        Sets the desired output current (but does not auto-enable outputs) in
        milliamps, pass extra_params string to append to the command (like ":TRIG")

        Limited to five percent greater than the current limit of the unit.
        """

        if milliamps / 1000.0 > 1.05 * self.current_limit or milliamps < 0:
            raise ValueError

        await super().set_current(milliamps, extra_params=extra_params)


def tcp(ipaddr: str, port: int) -> TDKLambdaZplus:
    """Quick helper to connect via TCP"""

    transport = get_tcp(ipaddr, port)
    protocol = SCPIProtocol(transport)
    dev = TDKLambdaZplus(protocol)
    return dev


def serial(serial_url: str, baudrate: int = 9600) -> TDKLambdaZplus:
    """Quick helper to connect via serial"""
    port = pyserial.serial_for_url(
        serial_url,
        baudrate=baudrate,
        bytesize=8,
        parity=pyserial.PARITY_NONE,
        stopbits=1,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
        timeout=10,
    )
    transport = RS232Transport(serialdevice=port)
    protocol = SCPIProtocol(transport)
    dev = TDKLambdaZplus(protocol)
    return dev
