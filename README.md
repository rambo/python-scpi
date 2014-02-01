python-scpi
===========

Since all the other wrappers either require VISA binary or are not generic (and do not implement the device I need)

Basic idea here is to make transport-independent command sender/parser and a device baseclass that implements the common SCPI commands

A device specific implementation can then add the device-specific commands.
