'''
Created on febrary 21 2020

@author: qmor
'''
from ..scpi import SCPIDevice
from ..transports.tcp import TCPTransport
from .generic import MultiMeter, PowerSupply
class TDKLambdaZplus(PowerSupply, MultiMeter, SCPIDevice):
    pass

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
    return dev
