python-scpi
===========

Since all the other wrappers either require VISA binary or are not generic (and do not implement the device I need)

Basic idea here is to make transport-independent command sender/parser and a device baseclass that implements the common SCPI commands

A device specific implementation can then add the device-specific commands.

Pro tip for thos wishing to work on the code <http://guide.python-distribute.org/pip.html#installing-from-a-vcs>

## TODO

### Check Carrier-Detect for RS232 transport

in the RS232 transport check getCD to make sure the device is present before doing anything.
CTS can also be checked even if hw flow control is not in use.

Basically wait for it for X seconds and abort if not found

### ZMQ/DBus signals and helpers

For remote-control and sharing access to the resource
