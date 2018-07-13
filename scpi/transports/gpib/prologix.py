""""Driver" for http://prologix.biz/gpib-usb-controller.html GPIB controller"""
import serial
import serial.threaded

from ..rs232 import RS232SerialProtocol
from .base import GPIBTransport


class PrologixRS232SerialProtocol(RS232SerialProtocol):
    """Basically the same deal as with the stock RS232 PySerial "protocol" but different EOL"""
    TERMINATOR = b'\n'


class PrologixGPIBTransport(GPIBTransport):
    """Transport "driver" for the Prologix USB-GPIB controller (v6 protocol)"""
    serialhandler = None

    def __init__(self, serial_device):
        self.serialhandler = serial.threaded.ReaderThread(serial_device, PrologixRS232SerialProtocol)
        self.serialhandler.start()
        self.serialhandler.protocol.handle_line = self.message_received

    async def send_group_trig(self, addresses=None):
        """Send trigger to listed addresses

        For some reason Prologix does not trigger the whole bus but only listed devices (if none listed then
        the currently selected device is used)"""
        raise NotImplementedError()


def get(serial_url, **serial_kwargs):
    """Shorthand for creating the port from url and initializing the transport"""
    port = serial.serial_for_url(serial_url, **serial_kwargs)
    return PrologixGPIBTransport(port)
