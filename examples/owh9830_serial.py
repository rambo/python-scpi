#!/usr/bin/env python3
"""Interactive OWH9830 over direct RS-232, e.g. /dev/tty.usbserial-A92TRYDJ."""

import argparse
import atexit
import os

from scpi.devices.owh9830 import serial
from scpi.wrapper import AIOWrapper

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--element", choices=("1A", "1B", "1C", "1sigma", "1A-C"), default="1A")
    parser.add_argument("--max-order", type=int, choices=range(1, 64), default=7)
    args = parser.parse_args()
    dev = AIOWrapper(serial(args.port, baudrate=args.baudrate))
    atexit.register(dev.quit)
    print(dev.identify())
    print("Snapshot (V/A/degrees/W/var):", dev.measure_snapshot(args.element))
    if args.element in ("1A", "1B", "1C"):
        print("Harmonics (orders 1..max_order, V/A):", dev.measure_harmonics(args.element, args.max_order))
    os.environ["PYTHONINSPECT"] = "1"
