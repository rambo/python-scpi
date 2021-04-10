#!/usr/bin/env python3
"""Example/test script for use the with Prologix USB GPIB interface"""
import atexit
import os
import sys

from scpi import SCPIDevice
from scpi.transports.gpib import prologix
from scpi.wrapper import AIOWrapper

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"run with python -i {__file__} /dev/ttyUSB0")
        sys.exit(1)
    # Then put to interactive mode
    os.environ["PYTHONINSPECT"] = "1"
    # Get the low-level GPIB transport
    aiogpib = prologix.get(sys.argv[1])
    # And the mapper that handlers asyncio transparently
    gpib = AIOWrapper(aiogpib)
    atexit.register(gpib.quit)

    print("*** Scanning bus for devices ***")
    devlist = gpib.scan_devices()
    devdict = {}
    for addr, idstr in devlist:
        # Get device specific transport instance
        dtransport = aiogpib.get_device_transport(addr)
        # Get the device class with the transport
        aiodev = SCPIDevice(dtransport)
        # And get the mapper that handles asyncio transparently
        devdict[addr] = AIOWrapper(aiodev)
        print("Added {:s} as devdict[{:d}]".format(idstr, addr))
