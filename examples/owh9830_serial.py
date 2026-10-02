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
    parser.add_argument("--element", choices=("1A", "1B", "1C", "1sigma"), default="1A")
    parser.add_argument("--max-order", type=int, choices=range(1, 64), default=7)
    args = parser.parse_args()
    dev = AIOWrapper(serial(args.port, baudrate=args.baudrate))
    atexit.register(dev.quit)
    print(dev.identify())
    print("Voltage (V):", dev.measure_voltage(args.element))
    print("Current (A):", dev.measure_current(args.element))
    print("Phase angle (degrees):", dev.measure_phase_angle(args.element))
    print("Real power (W):", dev.measure_real_power(args.element))
    print("Reactive power (var):", dev.measure_reactive_power(args.element))
    if args.element != "1sigma":
        print("Harmonics (orders 1..max_order, V/A):", dev.measure_harmonics(args.element, args.max_order))
    os.environ["PYTHONINSPECT"] = "1"
