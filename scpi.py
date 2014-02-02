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
        self.error_format_regex = self.board_ident_regex = re.compile(r"(+|-\d+),\"(.*?\")")
    
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

    def send_command(self, command):
        self.transport.send_command(command)
        self.transport.send_command("SYST:ERR?")
        # TODO: add timeout check
        while(len(self.message_stack) == 0):
            time.sleep(0)
        code, errstr = self.parse_error(message)
        if code != 0:
            # TODO: Make a separate scpiexception or something...
            raise RuntimeError("Command '%s' returned error %d: %s" % (command, code, errstr))



class scpi_device(object):
    """Implements nicer wrapper methods for the raw commands from the generic SCPI command set"""

    def __init__(self, transport, *args, **kwargs):
        """Initializes a device for the given transport"""
        super(scpi_device, self).__init__(*args, **kwargs)
        self.scpi = scpi(transport)
