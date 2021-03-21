""""Driver" for http://prologix.biz/gpib-usb-controller.html GPIB controller"""
import asyncio

import serial
import serial.threaded
from async_timeout import timeout

from ..rs232 import RS232SerialProtocol
from .base import GPIBTransport

SCAN_DEVICE_TIMEOUT = 0.5
READ_TIMEOUT = 1.0


class PrologixRS232SerialProtocol(RS232SerialProtocol):
    """Basically the same deal as with the stock RS232 PySerial "protocol" but different EOL"""

    TERMINATOR = b"\n"


class PrologixGPIBTransport(GPIBTransport):
    """Transport "driver" for the Prologix USB-GPIB controller (v6 protocol)"""

    serialhandler = None

    def __init__(self, serial_device, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serialhandler = serial.threaded.ReaderThread(serial_device, PrologixRS232SerialProtocol)
        self.serialhandler.start()
        self.serialhandler.protocol.handle_line = self.message_received
        self.initialize_controller()

    def initialize_controller(self):
        """Initializes the controller to known state"""
        # Set to controller mode
        self.serialhandler.protocol.write_line("++mode 1")
        # Disable automatic read after write
        self.serialhandler.protocol.write_line("++auto 0")
        # Auto-assert End Of Instruction after commands
        self.serialhandler.protocol.write_line("++eoi 1")
        # Append CRLF to device commands (EOI above *should* be enough but this is probably more compatible)
        self.serialhandler.protocol.write_line("++eos 0")
        # We do not have parsing support for the EOT character so disable it
        self.serialhandler.protocol.write_line("++eot_enable 0")
        # Set inter-character timeout for read commands
        self.serialhandler.protocol.write_line("++read_tmo_ms 500")
        # Assert IFC, make us Controller In Charge
        self.serialhandler.protocol.write_line("++ifc")

    async def send_command(self, command):
        """Wrapper for write_line on the protocol with some sanity checks"""
        if not self.serialhandler or not self.serialhandler.is_alive():
            raise RuntimeError("Serial handler not ready")
        async with self.lock:
            self.serialhandler.protocol.write_line(command)

    async def get_response(self):
        """Get device response"""
        return await self.send_and_read("++read eoi")

    async def send_and_read(self, send):
        """Send a line, read the response. NOTE: This is for talking with the controller, device responses
        need to use get_response as usual"""
        with timeout(READ_TIMEOUT):
            async with self.lock:
                response = None

                def set_response(message):
                    """Callback for setting the response"""
                    nonlocal response
                    response = message

                self.message_callback = set_response
                self.serialhandler.protocol.write_line(send)
                while response is None:
                    await asyncio.sleep(0)
                return response

    async def set_address(self, address, secondary=None):
        """Set the address we want to talk to"""
        if secondary is None:
            await self.send_command("++addr %d" % address)
        else:
            await self.send_command("++addr %d %d" % (address, secondary))
        # Wait for the address to actually be set
        while True:
            await asyncio.sleep(0)
            resp = await self.query_address()
            if resp == (address, secondary):
                break

    async def query_address(self):
        """Query the address we are talking to, returns tuple with primary and secondary parts
        secondary is None if not set"""
        resp = await self.send_and_read("++addr")
        parts = resp.split(" ")
        address = int(parts[0])
        secondary = None
        if len(parts) > 1:
            secondary = int(parts[1])
        return (address, secondary)

    async def send_scd(self):
        """Sends the Selected Device Clear (SDC) message to the currently specified GPIB address"""
        await self.send_command("++clr")

    async def send_ifc(self):
        """Asserts GPIB IFC signal"""
        await self.send_command("++ifc")

    async def send_llo(self):
        """Send LLO (disable front panel) to currently specified address"""
        await self.send_command("++llo")

    async def send_loc(self):
        """Send LOC (enable front panel) to currently specified address"""
        await self.send_command("++loc")

    async def get_srq(self):
        """Get SRQ assertion status"""
        resp = await self.send_and_read("++srq")
        return int(resp)

    async def poll(self):
        """Do serial poll on the selected device"""
        resp = await self.send_and_read("++spoll")
        return int(resp)

    async def send_group_trig(self, addresses=None):
        """Send trigger to listed addresses

        For some reason Prologix does not trigger the whole bus but only listed devices (if none listed then
        the currently selected device is used)"""
        if addresses is None:
            return await self.send_command("++trg")
        await self.send_command("++trg " + " ".join((str(x) for x in addresses)))

    async def scan_devices(self):
        """Scan for devices in the bus.
        Returns list of addresses and identifiers for found primary addresses (0-30)"""
        found_addresses = []
        # We do not lock on this level since the commands we use need to manipulate the lock
        prev_addr = await self.query_address()
        prev_read_tmo_ms = await self.send_and_read("++read_tmo_ms")
        self.serialhandler.protocol.write_line("++read_tmo_ms %d" % int((SCAN_DEVICE_TIMEOUT / 2) * 1000))
        for addr in range(0, 31):  # 0-30 inclusive
            with timeout(SCAN_DEVICE_TIMEOUT):
                try:
                    await self.set_address(addr)
                    await self.poll()
                    found_addresses.append(addr)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    pass
        self.serialhandler.protocol.write_line("++read_tmo_ms " + prev_read_tmo_ms)
        # Wait a moment for things to settle
        await asyncio.sleep(float(prev_read_tmo_ms) / 1000)
        # Get ids for the devices we found
        ret = []
        for addr in found_addresses:
            await self.set_address(addr)
            await self.send_command("*IDN?")
            idstr = await self.get_response()
            ret.append((addr, idstr))
        await self.set_address(*prev_addr)
        return ret

    async def quit(self):
        """Closes the port and background threads"""
        self.serialhandler.close()


def get(serial_url, **serial_kwargs):
    """Shorthand for creating the port from url and initializing the transport"""
    port = serial.serial_for_url(serial_url, **serial_kwargs)
    return PrologixGPIBTransport(port)
