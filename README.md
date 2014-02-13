python-scpi
===========

Since all the other wrappers either require VISA binary or are not generic (and do not implement the device I need)

Basic idea here is to make transport-independent command sender/parser and a device baseclass that implements the common SCPI commands

A device specific implementation can then add the device-specific commands.

## TODO

### Implement device-clear

"""
Using Device Clear
You can send a device clear at any time abort a SCPI command that may be hanging up the GPIB interface. The status registers, the error queue, and all configuration states are left unchanged when a device clear message is received. Device clear performs the following actions:
♦	The input and output buffers of the dc source are cleared. ♦	The dc source is prepared to accept a new command string.
The following statement shows how to send a device clear over the GPIB interface using Agilent BASIC: 
    CLEAR 705	IEEE-488 Device Clear
The following statement shows how to send a device clear over the GPIB interface using the GPIB command library for C or QuickBASIC: 
    IOCLEAR (705)
NOTE:	For RS-232 operation, sending a Break will perform the same operation as the IEE-488 device clear message."""

### Check Carrier-Detect for RS232 transport

Basically wait for it for X seconds and abort if not found

### Flow-control for RS232 transport

Figure out what is the problem
