'''
Created on febrary 21 2020

@author: qmor
'''
import decimal

from ..scpi import SCPIDevice
from ..transports.tcp import TCPTransport
from .generic import PowerSupply


class TDKSCPI(SCPIDevice):

    async def query_options(self):
        """
        Queries the model's options.
        """
        await self.ask("*OPT?")

    async def set_power_on_status_clear(self, setting):
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
        await self.command("*PSC %s" % setting)

    async def restore_state(self, state):
        """
        Restores the power supply to a state previously stored in memory by *SAV command.
        """
        state = int(state)
        assert state in (1, 2, 3, 4)

        await self.command("*RCL %d" % state)

    async def save_state(self, state):
        """
        The SAV command saves all applied configuration settings.
        """
        state = int(state)
        assert state in (1, 2, 3, 4)

        await self.command("*SAV %d" % state)

    async def power_on_state(self, setting):
        """
        Set the power-on behavior of the system
        * AUTO - The power supply output will return to its previous value when the latching fault
                 condition is removed or to the stored value after AC recycle.
        * SAFE - The power supply output will remain Off after the fault condition is removed or
                 after AC recycle.
        @ TODO: THE DOCS ARE VERY UNCLEAR WHAT VALUE IS WHICH
        """
        setting = str(setting).upper()
        if setting in ("1", "ON", "TRUE"):
            setting = "1"
        elif setting in ("0", "OFF", "FALSE"):
            setting = "0"
        else:
            raise ValueError
        await self.command("*OUTP:PON %s" % setting)



class TDKLambdaZplus(PowerSupply, TDKSCPI):

    async def measure_current(self, extra_params=""):
        """
        Returns the actual output current in amps.

        extra_params: String to append to the command.  The only valid command
                for this device is ":DC"
        """

        resp = await self.ask("MEAS:CURR%s?" % extra_params)
        return decimal.Decimal(resp)

    async def measure_voltage(self, extra_params=""):
        """
        Returns the actual output voltage in volts.

        extra_params: String to append to the command.  The only valid command
                for this device is ":DC"
        """

        resp = await self.ask("MEAS:VOLT%s?" % extra_params)
        return decimal.Decimal(resp)

    async def measure_power(self, extra_params=""):
        """
        Returns the actual output power in watts.

        extra_params: String to append to the command.  The only valid command
                for this device is ":DC"
        """

        resp = await self.ask("MEAS:POW%s?" % extra_params)
        return decimal.Decimal(resp)

    async def select_active_instrument(self, id):
        """
        Select the power supply for communication.

        id: the ID of the power supply to select.  int from 1-31
        """

        _id = int(id)

        if _id < 1 or id > 31:
            raise ValueError('id %d is outside of the valid id range' % _id)

        await self.command("INSTrument:NSELect %d" % _id)

    async def query_active_instrument(self):
        """
        Returns the ID of the active instrument.
        """

        resp = await self.ask("INSTrument:NSELect?")
        return decimal.Decimal(resp)

    async def couple_mode(self, couple="NONE"):
        """
        Couple for all Z+ power supplies.
        """

        couple = couple.upper()

        if couple in ("NONE", "ALL"):
            await self.command("INSTrument:COUPle %s" % couple)
        else:
            raise ValueError("Argument '%s' not valid for INST:COUP" % couple)

    async def set_voltage_protection(self, volts):
        """
        Set over-voltage protection level.
        """

        _volts = str(volts).upper()

        await self.command("VOLTage:PROTection:LEVel")

    async def query_voltage_protection(self, mode=None):
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
            resp = await self.ask("VOLTage:PROTection:LEVel? %s" % mode)
        return decimal.Decimal(resp)

    async def flash_display(self, setting):
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
        await self.command("DISPlay:FLASh %s" % setting)

    async def global_enable(self, setting):
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
        await self.command("GLOBal:OUTPut:STATe %s" % setting)

    async def global_set_voltage(self, volts):
        """
        Set enable status of all units.
        """

        _volts = str(volts)

        await self.command("GLOBal:VOLTage:AMPLitude %s" % _volts)

    async def global_reset(self):
        """
        Reset all units.
        """

        await self.command("GLOBal:*RST")


def tcp(ip, port):
    """Quick helper to connect via TCP"""
    from ..transports.tcp import get as get_tcp
    from ..scpi import SCPIProtocol
    transport = get_tcp(ip, port)
    protocol = SCPIProtocol(transport)
    dev = TDKLambdaZplus(protocol)
    return dev


def rs232(port, baudrate=9600):
    """ Quick helper to connect via serial """
    from ..transports.rs232 import RS232Transport
    from ..scpi import SCPIProtocol
    import serial
    port = serial.Serial(port,
                         baudrate=baudrate,
                         bytesize=8,
                         parity=serial.PARITY_NONE,
                         stopbits=1,
                         xonxoff=False,
                         rtscts=False,
                         dsrdtr=False,
                         timeout=10)
    transport = RS232Transport(port)
    protocol = SCPIProtocol(transport)
    dev = TDKLambdaZplus(protocol)
    # TODO: these are for my debugging purposes, remove before release
    from ..wrapper import AIOWrapper
    wdev = AIOWrapper(dev)
    wdev.command('INSTrument:NSELect 1')
    return dev
