#!/usr/bin/env python
import os,sys
# Add the parent dir to search paths
libs_dir = os.path.join(os.path.dirname( os.path.realpath( __file__ ) ),  '..',)
if os.path.isdir(libs_dir):                                       
    sys.path.append(libs_dir)

from devices import hp6632b


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "run with python -i hp6632b.py /dev/ttyUSB0"
        sys.exit(1)
    dev = hp6632b.serial(sys.argv[1])
