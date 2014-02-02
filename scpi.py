"""Generic SCPI commands, allow sending and reading of raw data, helpers to parse information"""
import time
import re

from exceptions import RuntimeError


class scpi(object):
    """Sends commands to the transport and parses return values"""
    def __init__(self, transport, *args, **kwargs):
        self.transport = transport
        self.transport.set_message_callback(self.message_received)
        self.message_stack = []
        self.error_format_regex = re.compile(r"([+-]\d+),\"(.*?)\"")
    
    def message_received(self, message):
        print " *** Got message '%s' ***" % message
        self.message_stack.append(message)
        pass

    def parse_error(self, message):
        """Parses given message for error code and string, raises error if message format is invalid"""
        match = self.error_format_regex.search(message)
        if not match:
            # PONDER: Make our own exceptions ??
            raise RuntimeError("message '%s' does not have correct error format" % message)
        code = int(match.group(1))
        errstr = match.group(2)
        return (code, errstr)

    def send_command(self, command, expect_response=True):
        """Sends the command, waits for the given time and then starts checking for response"""
        stack_size_start = len(self.message_stack)
        self.transport.send_command(command)
        timeout_start = time.time()
        while(   self.transport.incoming_data()
              or (    expect_response
                  and len(self.message_stack) < stack_size_start+1)
              ):
            time.sleep(0)
            if ((time.time() - timeout_start) > 5):
                # TODO: Make a separate timeoutexception
                raise RuntimeError("Timeout: No response to '%s' (or timeout waiting for incoming_data())" % command)

    def send_command_and_check(self, command, expect_response=True):
        self.send_command(command, expect_response)
        self.send_command("SYST:ERR?", True)
        code, errstr = self.parse_error(self.message_stack[-1])
        if code != 0:
            # TODO: Make a separate scpiexception or something...
            raise RuntimeError("Command '%s' returned error %d: %s" % (command, code, errstr))
        # Pop the no-error out
        self.message_stack.pop()



class scpi_device(object):
    """Implements nicer wrapper methods for the raw commands from the generic SCPI command set"""

    def __init__(self, transport, *args, **kwargs):
        """Initializes a device for the given transport"""
        super(scpi_device, self).__init__(*args, **kwargs)
        self.scpi = scpi(transport)
        # always reset to known status
        self.reset()

    def reset(self):
        """Resets the device to known state (with *RST) and clears the error log"""
        self.scpi.send_command("*RST;*CLS", False)

    def measure_voltage(self):
        self.scpi.send_command_and_check("MEAS:SCAL:VOLT?")
        