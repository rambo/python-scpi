"""TCP based transport"""
from typing import Optional
import asyncio
from dataclasses import dataclass, field
import logging


from .baseclass import BaseTransport


LOGGER = logging.getLogger(__name__)


@dataclass
class TCPTransport(BaseTransport):
    """TCP based transport"""

    ipaddr: str = field()  # type: ignore # workaround nondefault cannot follow default
    port: int = field()  # type: ignore # workaround nondefault cannot follow default
    reader: Optional[asyncio.StreamReader] = field(default=None)
    writer: Optional[asyncio.StreamWriter] = field(default=None)

    async def open_connection(self, ipaddr: str, port: int) -> None:
        """Open a connection (also update the IP/port)"""
        self.reader, self.writer = await asyncio.open_connection(ipaddr, port, loop=asyncio.get_event_loop())
        self.ipaddr = ipaddr
        self.port = port

    def __post_init__(self) -> None:
        """Call open_connection in an eventloop"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.open_connection(self.ipaddr, self.port))

    async def send_command(self, command: str) -> None:
        """Write command to the stream"""
        if not self.writer:
            raise RuntimeError("Writer not set")
        async with self.lock:
            LOGGER.debug("sending command: {}".format(command))
            self.writer.write((command + "\r\n").encode())
            await asyncio.sleep(0.05)
            await self.writer.drain()

    async def get_response(self) -> str:
        """Get response from the stream"""
        if not self.reader:
            raise RuntimeError("Reader not set")
        async with self.lock:
            data = await self.reader.readline()
            res = data.decode()
            LOGGER.debug("Got response: {}".format(res.strip()))
            return res

    async def quit(self) -> None:
        """Closes the connection and background threads"""
        if not self.writer:
            raise RuntimeError("Writer not set")
        self.writer.close()
        await self.writer.wait_closed()

    async def abort_command(self) -> None:
        """This does not apply on TCP transport"""
        LOGGER.debug("TCP transport does not know what to do here")


def get(ipaddr: str, port: int) -> TCPTransport:
    """Shorthand for creating the port from ip and port and initializing the transport"""
    return TCPTransport(ipaddr=ipaddr, port=port)
