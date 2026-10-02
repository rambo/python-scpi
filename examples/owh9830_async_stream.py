#!/usr/bin/env python3
"""Async streaming of OWH9830 snapshot measurements without AIOWrapper."""

import argparse
import asyncio
import sys

from scpi.devices.owh9830 import serial


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", help="serial port path or URL (e.g. /dev/tty.usbserial-A92TRYDJ)")
    parser.add_argument("--baudrate", type=int, default=115200, help="serial baudrate (default: 115200)")
    parser.add_argument(
        "--element", choices=("1A", "1B", "1C", "1sigma", "1A-C"), default="1A", help="element to stream"
    )
    parser.add_argument(
        "--count", type=int, default=0, help="number of snapshots to read (0 or negative for continuous)"
    )
    args = parser.parse_args()

    dev = serial(args.port, baudrate=args.baudrate)
    try:
        identity = await dev.identify()
        print(f"Connected to: {identity}")
        print(f"Streaming snapshots for {args.element} (Ctrl-C to stop)...")

        received = 0
        async for snapshot in dev.measure_snapshots(args.element):
            received += 1
            print(f"[{received}]", snapshot)
            if args.count > 0 and received >= args.count:
                break
    except KeyboardInterrupt:
        print("\nStreaming stopped by user.")
    finally:
        await dev.quit()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
