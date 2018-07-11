#!/usr/bin/env python3
import atexit
import os
import sys

from scpi.devices import hp6632b
from scpi.wrapper import DeviceWrapper

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("run with python -i hp6632b.py /dev/ttyUSB0")
        sys.exit(1)
    # Then put to interactive mode
    os.environ['PYTHONINSPECT'] = '1'
    aiodev = hp6632b.rs232(sys.argv[1], rtscts=True)
    # dev = hp6632b.rs232(sys.argv[1], rtscts=False)
    dev = DeviceWrapper(aiodev)

    atexit.register(dev.quit)

    print(dev.identify())
