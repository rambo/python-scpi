#!/usr/bin/env python3
"""Example/test script for using the Generic multimeter via TCP"""
import atexit
import os
import sys

from scpi.transports import TCPTransport
from scpi.devices.generic import MultiMeter
from scpi.wrapper import AIOWrapper

# pylint: disable=R0801

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"run with python -i {__file__} IP PORT")
        sys.exit(1)
    # Then put to interactive mode
    os.environ["PYTHONINSPECT"] = "1"
    xport = TCPTransport(ipaddr=sys.argv[1], port=int(sys.argv[2]))
    aiodev = MultiMeter(xport)
    dev = AIOWrapper(aiodev)

    atexit.register(dev.quit)

    print(dev.identify())
