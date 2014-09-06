"""HP/Agilent 3362B specific device implementation and helpers"""

#import os,sys
## Add the parent dir to search paths
#libs_dir = os.path.join(os.path.dirname( os.path.realpath( __file__ ) ),  '..',)
#if os.path.isdir(libs_dir):                                       
#    sys.path.append(libs_dir)

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

    def measure_current_autorange(self, extra_params=""):
        """Measures the current, then make sure we are running on the correct measurement range and if not switch range and measure again"""
        ret = self.measure_current(extra_params)
        if abs(ret) < 0.020:
            # We need to be in low-current mode
            if not self.query_low_current_mode():
                # Enter low current mode and measure again
                self.set_low_current_mode(True)
                return self.measure_current(extra_params)
            else:
                return ret
        # We need to be in high-current mode
        if self.query_low_current_mode():
            # Switch mode and measure again
            self.set_low_current_mode(False)
            return self.measure_current(extra_params)
        return ret

    def set_remote_mode(self, state=True):
        """RS232 only, prevent accidental button mashing on the fron panel, this switches between SYSTem:REMote and SYSTem:LOCal according to state, this overrides previous value set with set_rwlock"""
        from scpi.transports import rs232 
        if not isinstance(self.scpi.transport, rs232):
            from exceptions import RuntimeError
            raise RuntimeError("Only usable with RS232 transports")
        if state:
            return self.scpi.send_command("SYST:REM", False)
        return self.scpi.send_command("SYST:LOC", False)

    def set_rwlock(self, state=True):
        """RS232 only, prevent *any* button mashing on the fron panel, this switches between SYSTem:RWLock and SYSTem:LOCal according to state, this overrides previous value set with set_remote_mode"""
        from transports import rs232 as serial_transport
        if not isinstance(self.scpi.transport, serial_transport.transports_rs232):
            from exceptions import RuntimeError
            raise RuntimeError("Only usable with RS232 transports")
        if state:
            return self.scpi.send_command("SYST:RWL", False)
        return self.scpi.send_command("SYST:LOC", False)

    def display_on(self, state=True):
        """Sets display on/off"""
        if state:
            return self.scpi.send_command("DISP ON", False)
        return self.scpi.send_command("DISP OFF", False)

    def set_display_mode(self, mode):
        """Set the display mode, valied values are NORM and TEXT"""
        mode = mode.upper()
        if not mode in ( 'NORM', 'TEXT' ):
            raise RuntimeError("Invalid mode %s, valid ones are NORM and TEXT" % mode)
        return self.scpi.send_command("DISP:MODE %s" % mode, False)

    def set_display_text(self, text):
        """Used to display text on the display, max 14 characters, NOTE: does *not* set display mode, you need to do it yourself"""
        if len(text) > 14:
            raise RuntimeError("Max text length is 14 characters")
        if (    '"' in text
            and "'" in text):
            raise RuntimeError("Text may only contain either single or double quotes, not both")
        if '"' in text:
            return self.scpi.send_command("DISP:TEXT '%s'" % text, False)
        return self.scpi.send_command('DISP:TEXT  "%s"' % text, False)
        

def rs232(port, **kwargs):
    """Quick helper to connect via RS232 port"""
    # TODO: figure out why I can't communicate with rtscts enabled (try dsrdtr as well)
    import serial as pyserial
    from scpi.transports import rs232 as serial_transport
    serial_port = pyserial.Serial(port, 9600, timeout=0, **kwargs)
    transport = serial_transport(serial_port)
    dev = hp6632b(transport)
    return dev

