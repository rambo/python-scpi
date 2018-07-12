"""GPIB Related baseclasses"""
from ..baseclass import BaseTransport


class GPIBTransport(BaseTransport):
    """Baseclass for GPIB transports"""

    async def set_address(self, addr):
        """Set the address we want to talk to"""
        raise NotImplemented()

    async def query_address(self):
        """Query the address we are talking to"""
        raise NotImplemented()

    async def scan_devices(self):
        """Scan for devices in the bus"""
        raise NotImplemented()

    async def send_scd(self):
        """Sends the Selected Device Clear (SDC) message to the currently specified GPIB address"""
        raise NotImplemented()

    async def send_ifc(self):
        """Asserts GPIB IFC signal"""
        raise NotImplemented()

    async def send_llo(self):
        """Send LLO (disable front panel) to currently specified address"""
        raise NotImplemented()

    async def send_loc(self):
        """Send LOC (enable front panel) to currently specified address"""
        raise NotImplemented()

    async def send_trig(self, addresses):
        """Send Group Execute Trigger GPIB to the listed addresses"""
        raise NotImplemented()

    async def get_srq(self):
        """Get SRQ assertion status"""
        raise NotImplemented()

    async def poll(self):
        """Do serial poll on the selected device"""
        raise NotImplemented()


class GPIBDeviceTransport(object):
    """Device specific transport, handles addressing transparently"""
    my_address = None
    lltransport = None

    def __init__(self, lltransport, address):
        """Takes the actual bus transport (low-level transport) and device address"""
        self.lltransport = lltransport
        self.my_address = address

    async def send_command(self, command):
        """Transparently set address when talking, see low-level transport method docs for more info"""
        await self.lltransport.set_address(self.my_address)
        await self.lltransport.send_command(command)

    async def get_response(self):
        """Transparently set address when talking, see low-level transport method docs for more info"""
        await self.lltransport.set_address(self.my_address)
        return await self.lltransport.get_response()

    async def abort_command(self):
        """Transparently set address when talking, see low-level transport method docs for more info"""
        await self.lltransport.set_address(self.my_address)
        return await self.lltransport.abort_command()
