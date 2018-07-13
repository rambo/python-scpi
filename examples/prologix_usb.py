#!/usr/bin/env python3
import atexit
import os
import sys

from scpi import SCPIDevice, SCPIProtocol
from scpi.transports.gpib import GPIBDeviceTransport, prologix
from scpi.wrapper import DeviceWrapper

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("run with python -i hp6632b.py /dev/ttyUSB0")
        sys.exit(1)
    # Then put to interactive mode
    os.environ['PYTHONINSPECT'] = '1'
    aiogpib = prologix.get(sys.argv[1])
    gpib = DeviceWrapper(aiogpib)
    atexit.register(gpib.quit)

    print("*** Scanning bus for devices ***")
    devlist = gpib.scan_devices()
    devdict = {}
    for addr, idstr in devlist:
        dtransport = GPIBDeviceTransport(aiogpib, addr)
        dproto = SCPIProtocol(dtransport)
        aiodev = SCPIDevice(dproto)
        devdict[addr] = DeviceWrapper(aiodev)
        print("Added {:s} as devdict[{:d}]".format(idstr, addr))
