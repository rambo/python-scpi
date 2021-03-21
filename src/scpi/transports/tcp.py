"""
Created on febrary 21 2020

@author: qmor
"""
import asyncio
from .baseclass import BaseTransport


class TCPTransport(BaseTransport):
    async def openconnection(self, ip, port):
        self.reader, self.writer = await asyncio.open_connection(ip, port, loop=asyncio.get_event_loop())

    def __init__(self, ip, port, *args, **kwargs):
        super().__init__(*args, **kwargs)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.openconnection(ip, port))

    async def send_command(self, command):
        async with self.lock:
            print(command)
            self.writer.write((command + "\r\n").encode())
            await asyncio.sleep(0.05)
            await self.writer.drain()

    async def get_response(self):
        async with self.lock:
            data = await self.reader.readline()
            res = data.decode()
            print(res.strip())
        return res

    async def quit(self):
        """Closes the connection and background threads"""
        self.writer.close()
        await self.writer.wait_closed()


def get(ip, port):
    """Shorthand for creating the port from ip and port and initializing the transport"""
    return TCPTransport(ip, port)
