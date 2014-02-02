"""Generic SCPI commands, allow sending and reading of raw data, helpers to parse information"""
import time
import re

from exceptions import RuntimeError, ValueError
from errors import Timeout, CommandError


class scpi(object):
    """Sends commands to the transport and parses return values"""
    def __init__(self, transport, *args, **kwargs):
        super(scpi, self).__init__(*args, **kwargs)
        self.transport = transport
        self.transport.set_message_callback(self.message_received)
        self.message_stack = []
        self.error_format_regex = re.compile(r"([+-]\d+),\"(.*?)\"")
        self.command_timeout = 1.5 # Seconds
    
    def message_received(self, message):
        print " *** Got message '%s' ***" % message
        self.message_stack.append(message)
        pass

    def parse_error(self, message):
        """Parses given message for error code and string, raises error if message format is invalid"""
        match = self.error_format_regex.search(message)
        if not match:
            # PONDER: Make our own exceptions ??
            raise ValueError("message '%s' does not have correct error format" % message)
        code = int(match.group(1))
        errstr = match.group(2)
        return (code, errstr)

    def send_command(self, command, expect_response=True):
        """Sends the command, waits for all data to complete (and if response is expected for new entry to message stack)"""
        stack_size_start = len(self.message_stack)
        self.transport.send_command(command)
        timeout_start = time.time()
        while(   self.transport.incoming_data()
              or (    expect_response
                  and len(self.message_stack) < stack_size_start+1)
              ):
            time.sleep(0)
            if ((time.time() - timeout_start) > self.command_timeout):
                raise Timeout(command, self.command_timeout)

    def send_command_and_check(self, command, expect_response=True):
        """Sends the command and makes sure it did not trigger errors"""
        re_raise = None
        try:
            self.send_command(command, expect_response)
        except (Timeout), e:
            re_raise = e
        finally:
            self.send_command("SYST:ERR?", True)
            code, errstr = self.parse_error(self.message_stack[-1])
            if code != 0:
                raise CommandError(command, code, errstr)
            # Pop the no-error out
            self.message_stack.pop()
            if re_raise:
                raise re_raise

    def parse_number(self, message):
        """This is pretty trivial but just in case we want to change from floats to Decimals for example"""
        return float(message)

    def pop_and_parse_number(self):
        """Pops the last value from message stack and parses number from it"""
        data = self.message_stack.pop()
        return self.parse_number(data)

    def ask_number(self, command):
        """Sends the command (checking for errors), then pops and parses the last line as number"""
        self.send_command_and_check(command)
        return self.pop_and_parse_number()


class scpi_device(object):
    """Implements nicer wrapper methods for the raw commands from the generic SCPI command set"""

    def __init__(self, transport, *args, **kwargs):
        """Initializes a device for the given transport"""
        super(scpi_device, self).__init__(*args, **kwargs)
        self.scpi = scpi(transport)
        # always reset to known status on init
        self.reset()

    def reset(self):
        """Resets the device to known state (with *RST) and clears the error log"""
        self.scpi.send_command("*RST;*CLS", False)

    def measure_voltage(self, extra_params=""):
        """Returns the measured (scalar) voltage, pass extra_params string to append to the command (like ":ACDC")"""
        return self.scpi.ask_number("MEAS:SCAL:VOLT%s?" % extra_params)

    def measure_current(self, extra_params=""):
        """Returns the measured current, pass extra_params string to append to the command (like ":ACDC")"""
        return self.scpi.ask_number("MEAS:SCAL:CURR%s?" % extra_params)



