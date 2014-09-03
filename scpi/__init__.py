"""SCPI module, the scpi class implements the base command set, devices may extend it. transports are separate from devices
(so you can use for example hp6632b with either serial port or GPIB)"""
from .scpi import scpi, scpi_device
from .errors import *
