import os,sys
# Add the parent dir to search paths
libs_dir = os.path.join(os.path.dirname( os.path.realpath( __file__ ) ),  '..',)
if os.path.isdir(libs_dir):                                       
    sys.path.append(libs_dir)

from scpi import scpi_device

class hp6632b(scpi_device):
    """Adds the HP/Agilent 3362B specific SCPI commands as methods"""

    def __init__(self, transport, *args, **kwargs):
        """Initializes a device for the given transport"""
        super(hp6632b, self).__init__(transport, *args, **kwargs)

def rs232(port, **kwargs):
    """Quick helper to connect via RS232 port"""
    import serial as pyserial
    from transports import rs232 as serial_transport
    serial_port = pyserial.Serial(port, 9600, timeout=0, **kwargs)
    transport = serial_transport.transports_rs232(serial_port)
    dev = hp6632b(transport)
    return dev

