#!/usr/bin/env python3
"""Example/test script for using the HP 6632B power supply via serial interface"""
import atexit
import os
import sys

from scpi.devices import hp6632b
from scpi.wrapper import AIOWrapper

# pylint: disable=R0801

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"run with python -i {__file__} /dev/ttyUSB0")
        sys.exit(1)
    # Then put to interactive mode
    os.environ["PYTHONINSPECT"] = "1"
    aiodev = hp6632b.rs232(sys.argv[1], rtscts=True, baudrate=9600)
    dev = AIOWrapper(aiodev)

    atexit.register(dev.quit)

    print(dev.identify())
