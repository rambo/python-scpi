====
scpi
====

New asyncio_ version. Only for Python 3.6 and above

Since all the other wrappers either require VISA binary or are not generic (and do not implement the device I need)

Basic idea here is to make transport-independent command sender/parser and a device baseclass that implements the common SCPI commands

A device specific implementation can then add the device-specific commands.

Pro tip for thos wishing to work on the code https://python-poetry.org/

.. _asyncio: https://docs.python.org/3/library/asyncio.html


## Usage

Install the package to your virtualenv with poetry or from pip

  - Instatiate a transport (for GPIB you will need `GPIBDeviceTransport` to be able to use the device helper class)
  - Instatiate `SCPIProtocol` with the transport (optional, see below)
  - Instantiate `SCPIDevice` with the protocol (or as a shorthand: with the transport directly)
  - Use the asyncio eventloop to run the device methods (all of which are coroutines)

Or if you're just playing around in the REPL use `AIOWrapper` to hide the eventloop handling
for traditional non-concurrent approach.

See the examples directory for more.

TODO
----

Check Carrier-Detect for RS232 transport
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

in the RS232 transport check getCD to make sure the device is present before doing anything.
CTS can also be checked even if hw flow control is not in use.

Basically wait for it for X seconds and abort if not found
