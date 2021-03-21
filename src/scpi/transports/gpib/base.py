"""GPIB Related baseclasses"""
from ..baseclass import AbstractTransport, BaseTransport


class GPIBTransport(BaseTransport):
    """Baseclass for GPIB transports"""

    async def set_address(self, address, secondary=None):
        """Set the address we want to talk to"""
        raise NotImplementedError()

    async def query_address(self):
        """Query the address we are talking to, returns tuple with primary and secondary parts
        secondary is None if not set"""
        raise NotImplementedError()

    async def scan_devices(self):
        """Scan for devices in the bus.
        Returns list of addresses and identifiers for found primary addresses (0-30)"""
        raise NotImplementedError()

    async def send_scd(self):
        """Sends the Selected Device Clear (SDC) message to the currently specified GPIB address"""
        raise NotImplementedError()

    async def send_ifc(self):
        """Asserts GPIB IFC signal"""
        raise NotImplementedError()

    async def send_llo(self):
        """Send LLO (disable front panel) to currently specified address"""
        raise NotImplementedError()

    async def send_loc(self):
        """Send LOC (enable front panel) to currently specified address"""
        raise NotImplementedError()

    async def send_group_trig(self):
        """Send Group Execute Trigger to the bus"""
        raise NotImplementedError()

    async def get_srq(self):
        """Get SRQ assertion status"""
        raise NotImplementedError()

    async def poll(self):
        """Do serial poll on the selected device"""
        raise NotImplementedError()

    def get_device_transport(self, address, secondary=None):
        """Gets a device-specific transport instance for given address"""
        return GPIBDeviceTransport(self, (address, secondary))


class GPIBDeviceTransport(AbstractTransport):
    """Device specific transport, handles addressing transparently"""

    my_address = None
    lltransport = None

    def __init__(self, lltransport, address, *args, **kwargs):
        """Takes the actual bus transport (low-level transport) and device address"""
        super().__init__(*args, **kwargs)
        self.my_address = address
        if len(address) == 1:
            self.my_address = (address, None)
        self.lltransport = lltransport
        self.my_address = address

    async def send_command(self, command):
        """Transparently set address when talking, see low-level transport method docs for more info"""
        await self.lltransport.set_address(*self.my_address)
        await self.lltransport.send_command(command)

    async def get_response(self):
        """Transparently set address when talking, see low-level transport method docs for more info"""
        await self.lltransport.set_address(*self.my_address)
        return await self.lltransport.get_response()

    async def abort_command(self):
        """Transparently set address when talking, see low-level transport method docs for more info"""
        await self.lltransport.set_address(*self.my_address)
        return await self.lltransport.abort_command()

    async def send_scd(self):
        """Sends the Selected Device Clear (SDC) message to the device"""
        await self.lltransport.set_address(*self.my_address)
        await self.lltransport.send_scd()

    async def send_llo(self):
        """Send LLO (disable front panel) to the device"""
        await self.lltransport.set_address(*self.my_address)
        await self.lltransport.send_llo()

    async def send_loc(self):
        """Send LOC (enable front panel) to the device"""
        await self.lltransport.set_address(*self.my_address)
        await self.lltransport.send_loc()
