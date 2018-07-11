python-scpi
===========

**New [asyncio][asyncio] version. Only for Python 3.5 and above**

Since all the other wrappers either require VISA binary or are not generic (and do not implement the device I need)

Basic idea here is to make transport-independent command sender/parser and a device baseclass that implements the common SCPI commands

A device specific implementation can then add the device-specific commands.

Pro tip for thos wishing to work on the code <http://guide.python-distribute.org/pip.html#installing-from-a-vcs>

## Usage

  - Instatiate a transport
  - Instatiate `SCPIProtocol` with the transport
  - Instantiate `SCPIDevice` with the protocol
  - Use the asyncio eventloop to run the device methods (all of which are coroutines)

Or if you're just playing around in the REPL use `DeviceWrapper` to hide the eventloop handling
for traditional non-concurrent approach.

See <https://github.com/rambo/python-scpi/tree/master/examples> for more.

## TODO

### Check Carrier-Detect for RS232 transport

in the RS232 transport check getCD to make sure the device is present before doing anything.
CTS can also be checked even if hw flow control is not in use.

Basically wait for it for X seconds and abort if not found


[asyncio]: https://docs.python.org/3/library/asyncio.html