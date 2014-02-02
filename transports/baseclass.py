"""Baseclass for all the transports, if common methods are needed they will be defined here

All transports must define certain basic methods
"""

from exceptions import NotImplementedError
from exceptions import RuntimeError


class transports_base(object):
    def __init__(self):
        """Initializes a transport"""
        pass
    
    def set_message_callback(self, callback):
        self.message_received = callback

    def send_command(self, command):
        """Sends a complete command to the device, line termination etc is handled by the transport"""
        raise NotImplementedError()

    def message_received(self, message):
        """Default message callback raises error"""
        raise RuntimeError("Message callback not set")
