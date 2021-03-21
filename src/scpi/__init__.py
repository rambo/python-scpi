"""SCPI module, the scpi class implements the base command set, devices may extend it.
transports are separate from devices (so you can use for example hp6632b with either serial port or GPIB)"""
__version__ = "2.2.0"  # NOTE Use `bump2version --config-file patch` to bump versions correctly
from .scpi import SCPIProtocol, SCPIDevice
from .errors import CommandError
