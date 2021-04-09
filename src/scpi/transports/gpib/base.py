"""GPIB Related baseclasses"""
from __future__ import annotations
from typing import Optional, Tuple, Sequence, Union
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import logging

from ..baseclass import AbstractTransport, BaseTransport

LOGGER = logging.getLogger(__name__)

AddressTuple = Tuple[int, Optional[int]]


@dataclass
class GPIBDeviceTransport(AbstractTransport):
    """Device specific transport, handles addressing transparently"""

    lltransport: GPIBTransport = field()
    address: Union[AddressTuple, int] = field()

    def __post_init__(self) -> None:
        """Make sure address is always tuple"""
        if isinstance(self.address, int):
            self.address = (self.address, None)

    async def _set_ll_address(self) -> None:
        """Set the lowlevel transport address"""
        assert not isinstance(self.address, int)
        await self.lltransport.set_address(self.address[0], self.address[1])

    async def send_command(self, command: str) -> None:
        """Transparently set address when talking, see low-level transport method docs for more info"""
        await self._set_ll_address()
        await self.lltransport.send_command(command)

    async def get_response(self) -> str:
        """Transparently set address when talking, see low-level transport method docs for more info"""
        await self._set_ll_address()
        return await self.lltransport.get_response()

    async def abort_command(self) -> None:
        """Transparently set address when talking, see low-level transport method docs for more info"""
        await self._set_ll_address()
        return await self.lltransport.abort_command()

    async def send_scd(self) -> None:
        """Sends the Selected Device Clear (SDC) message to the device"""
        await self._set_ll_address()
        await self.lltransport.send_scd()

    async def send_llo(self) -> None:
        """Send LLO (disable front panel) to the device"""
        await self._set_ll_address()
        await self.lltransport.send_llo()

    async def send_loc(self) -> None:
        """Send LOC (enable front panel) to the device"""
        await self._set_ll_address()
        await self.lltransport.send_loc()


class GPIBTransport(BaseTransport, ABC):
    """Baseclass for GPIB transports"""

    @abstractmethod
    async def set_address(self, primary: int, secondary: Optional[int] = None) -> None:
        """Set the address we want to talk to"""
        raise NotImplementedError()

    @abstractmethod
    async def query_address(self) -> AddressTuple:
        """Query the address we are talking to, returns tuple with primary and secondary parts
        secondary is None if not set"""
        raise NotImplementedError()

    @abstractmethod
    async def scan_devices(self) -> Sequence[Tuple[int, str]]:
        """Scan for devices in the bus.
        Returns list of addresses and identifiers for found primary addresses (0-30)"""
        raise NotImplementedError()

    @abstractmethod
    async def send_scd(self) -> None:
        """Sends the Selected Device Clear (SDC) message to the currently specified GPIB address"""
        raise NotImplementedError()

    @abstractmethod
    async def send_ifc(self) -> None:
        """Asserts GPIB IFC signal"""
        raise NotImplementedError()

    @abstractmethod
    async def send_llo(self) -> None:
        """Send LLO (disable front panel) to currently specified address"""
        raise NotImplementedError()

    @abstractmethod
    async def send_loc(self) -> None:
        """Send LOC (enable front panel) to currently specified address"""
        raise NotImplementedError()

    @abstractmethod
    async def send_group_trig(self) -> None:
        """Send Group Execute Trigger to the bus"""
        raise NotImplementedError()

    @abstractmethod
    async def get_srq(self) -> int:
        """Get SRQ assertion status"""
        raise NotImplementedError()

    @abstractmethod
    async def poll(self) -> int:
        """Do serial poll on the selected device"""
        raise NotImplementedError()

    def get_device_transport(self, address: int, secondary: Optional[int] = None) -> GPIBDeviceTransport:
        """Gets a device-specific transport instance for given address"""
        return GPIBDeviceTransport(self, (address, secondary))
