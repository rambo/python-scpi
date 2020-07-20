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
