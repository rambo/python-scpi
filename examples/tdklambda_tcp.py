'''
Created on febrary 21 2020.

@author: qmor
'''

import atexit
import os
import time

from scpi.devices import TDKLambdaZPlus
from scpi.wrapper import AIOWrapper

if __name__ == '__main__':
    # Then put to interactive mode
    os.environ['PYTHONINSPECT'] = '1'
    aiodev = TDKLambdaZPlus.tcp('192.168.3.34', 8003)
    dev = AIOWrapper(aiodev)
    atexit.register(dev.quit)
    dev.identify()
    while True:
        dev.query_voltage()
        dev.query_current()
        dev.query_output()
        time.sleep(1)
    