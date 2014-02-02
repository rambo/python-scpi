"""Generic SCPI commands, allow sending and reading of raw data, helpers to parse information"""

# TODO: Everything

class scpi(object):
    """Sends commands to the transport and parses return values"""
    def __init__(self, transport, *args, **kwargs):
        self.transport = transport
        self.transport.set_message_callback(self.message_received)
    
    def message_received(self, message):
        print " *** Got message '%s' ***" % message
        # TODO: put the messages into stack for parsing
        pass

class scpi_device(object):
    """Implements nicer wrapper methods for the raw commands from the generic SCPI command set"""

    def __init__(self, transport, *args, **kwargs):
        """Initializes a device for the given transport"""
        super(scpi_device, self).__init__(transport, *args, **kwargs)
