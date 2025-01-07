"""Baseclass for all the transports, if common methods are needed they will be defined here

All transports must define certain basic methods (check all the raise NotImplementedError)
"""

from typing import Optional, Callable
import asyncio
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


LOGGER = logging.getLogger(__name__)


class AbstractTransport(ABC):  # pylint: disable=R0903
    """So that for example GPIBDeviceTransport can be identified as transport without inheriting
    the low-level transport methods"""


@dataclass
class BaseTransport(AbstractTransport, ABC):
    """Baseclass for SCPI tranport layers, abstracts away details, must be subclasses to implement"""

    message_callback: Optional[Callable[[str], None]] = field(default=None)
    unsolicited_message_callback: Optional[Callable[[str], None]] = field(default=None)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    aioevent: asyncio.Event = field(default_factory=asyncio.Event)
    blevent: threading.Event = field(default_factory=threading.Event)

    @abstractmethod
    async def quit(self) -> None:
        """Must shutdown all background threads (if any)"""
        raise NotImplementedError()

    @abstractmethod
    async def send_command(self, command: str) -> None:
        """Sends a complete command to the device, line termination, write timeouts etc are handled by the transport
        note: the transport probably should handle locking transparently using
        'with (await self.lock):' as context manager"""
        raise NotImplementedError()

    @abstractmethod
    async def get_response(self) -> str:
        """Tells the device send a response, reads and returns it"""
        raise NotImplementedError()

    def message_received(self, message: str) -> None:
        """Passes the message to the callback expecting it, or to the unsolicited callback"""
        if self.message_callback is not None:
            self.message_callback(message)
            self.message_callback = None
            return
        # Fall-through for unsolicited messages
        if self.unsolicited_message_callback is not None:
            self.unsolicited_message_callback(message)
            return
        LOGGER.info("Got unsolicited message but have no callback to send it to")

    @abstractmethod
    async def abort_command(self) -> None:
        """Send the "device clear" command to abort a running command
        note: the transport probably should handle locking transparently using
        'async with self.lock:' as context manager"""
        raise NotImplementedError()
