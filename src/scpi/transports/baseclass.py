"""Baseclass for all the transports, if common methods are needed they will be defined here

All transports must define certain basic methods (check all the raise NotImplementedError)
"""
import asyncio
import logging

logger = logging.getLogger(__name__)


class AbstractTransport(object):
    """So that for example GPIBDeviceTransport can be identified as transport without inheriting
    the low-level transport methods"""


class BaseTransport(AbstractTransport):
    """Baseclass for SCPI tranport layers, abstracts away details, must be subclasses to implement"""

    message_callback = None
    unsolicited_message_callback = None
    lock = asyncio.Lock()

    async def quit(self):
        """Must shutdown all background threads (if any)"""
        raise NotImplementedError()

    async def send_command(self, command):
        """Sends a complete command to the device, line termination, write timeouts etc are handled by the transport
        note: the transport probably should handle locking transparently using
        'with (await self.lock):' as context manager"""
        raise NotImplementedError()

    async def get_response(self):
        """Tells the device send a response, reads and returns it"""
        raise NotImplementedError()

    def message_received(self, message):
        """Passes the message to the callback expecting it, or to the unsolicited callback"""
        if self.message_callback is not None:
            self.message_callback(message)
            self.message_callback = None
            return
        # Fall-through for unsolicited messages
        if self.unsolicited_message_callback is not None:
            self.unsolicited_message_callback(message)
            return
        logger.info("Got unsolicited message but have no callback to send it to")

    async def abort_command(self):
        """Send the "device clear" command to abort a running command
        note: the transport probably should handle locking transparently using
        'with (await self.lock):' as context manager"""
        raise NotImplementedError()
