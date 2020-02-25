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
    transport = get_tcp(ip,port)
    protocol = SCPIProtocol(transport)
    dev = TDKLambdaZplus(protocol)
    return dev