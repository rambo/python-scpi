"""HP/Agilent 3362B specific device implementation and helpers"""

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
        self.scpi.ask_default_wait = 0.050 # Average aquisition time is 30ms + 20ms processing time

    def set_low_current_mode(self, state):
        """The low-current mode is enabled by setting the range to (max) 20mA, anything over that is high-current mode. This model has max 5A output"""
        if state:
            return self.set_measure_current_max(0.020)
        return self.set_measure_current_max(5.0)

    def query_low_current_mode(self):
        """Returns boolean indicating whether we are in low or high current mode"""
        max_current = self.query_measure_current_max()
        if max_current <= 0.020:
            return True
        return False


def rs232(port, **kwargs):
    """Quick helper to connect via RS232 port"""
    import serial as pyserial
    from transports import rs232 as serial_transport
    serial_port = pyserial.Serial(port, 9600, timeout=0, **kwargs)
    transport = serial_transport.transports_rs232(serial_port)
    dev = hp6632b(transport)
    return dev

