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

def serial(port, **kwargs):
    import serial
    from transports import serial as serial_transport
    serial_port = serial.Serial(port, 9600, timeout=0, **kwargs)
    transport = serial_transport.transports_serial(serial_port)

