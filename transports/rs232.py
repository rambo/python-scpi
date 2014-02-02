"""Serial port transport helper"""
import serial as pyserial
import threading
import string
import binascii
import time
import sys
from baseclass import transports_base

# basically a wrapper for Serial
class transports_rs232(transports_base):
    def __init__(self, port, *args, **kwargs):
        """Initializes a serial transport, requires open serial port and message callback as arguments"""
        super(transports_rs232, self).__init__(*args, **kwargs)
        self.line_terminator = "\r\n"
        self._terminator_slice = -1*len(self.line_terminator)
        # For tracking state changes
        self._previous_states = {
            'getCTS': None,
            'getDSR': None,
            'getRI': None,
            'getCD': None
        }
        self._current_states = {
            'getCTS': None,
            'getDSR': None,
            'getRI': None,
            'getCD': None
        }
        self.serial_port = port
        self.initialize_serial()

    def initialize_serial(self):
        """Creates a background thread for reading the serial port"""
        self.input_buffer = ""
        self.receiver_thread = threading.Thread(target=self.serial_reader)
        self.receiver_thread.setDaemon(1)
        self.receiver_thread.start()

    def serial_reader(self):
        self.serial_alive = True
        try:
            while self.serial_alive:
                for method in self._current_states:
                    self._current_states[method] = getattr(self.serial_port, method)()
                    if self._current_states[method] != self._previous_states[method]:
                        print " *** %s changed to %d *** " % (method, self._current_states[method])
                        self._previous_states[method] = self._current_states[method]
                if not self.serial_port.inWaiting():
                    # Don't try to read if there is no data, instead sleep (yield) a bit
                    time.sleep(0)
                    continue
                data = self.serial_port.read(1)
                if len(data) == 0:
                    continue
                # hex-encode unprintable characters
#               if data not in string.letters.join(string.digits).join(string.punctuation).join("\r\n"):
#                    sys.stdout.write("\\0x".join(binascii.hexlify(data)))
                # OTOH repr was better afterall
                if data not in self.line_terminator:
                    sys.stdout.write(repr(data))
                else:
                    sys.stdout.write(data)
                # Put the data into inpit buffer and check for CRLF
                self.input_buffer += data
                # Trim prefix NULLs and linebreaks
                self.input_buffer = self.input_buffer.lstrip(chr(0x0) + "\r\n")
                #print "input_buffer=%s" % repr(self.input_buffer)
                if (    len(self.input_buffer) > 0
                    and self.input_buffer[self._terminator_slice:] == self.line_terminator):
                    # Got a message, parse it (sans the CRLF) and empty the buffer
                    #print "DEBUG: calling self.message_received()"
                    self.message_received(self.input_buffer[:self._terminator_slice])
                    self.input_buffer = ""

        except (IOError, pyserial.SerialException), e:
            print "Got exception %s" % e
            self.serial_alive = False
            # It seems we cannot really call this from here, how to detect the problem in main thread ??
            #self.launcher_instance.unload_device(self.object_name)

    def incoming_data(self):
        """It seems there is no better way to check for transaction-in-progress than this (I was hoping RI or some other modem signal would be used)"""
        return bool(self.serial_port.inWaiting())

    def send_command(self, command):
        """Adds the line terminator and writes the command out"""
        send_str = command + self.line_terminator
        self.serial_port.write(send_str)
