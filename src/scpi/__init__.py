"""SCPI module, the scpi class implements the base command set, devices may extend it.
transports are separate from devices (so you can use for example hp6632b with either serial port or GPIB)"""

__version__ = "2.5.1"  # NOTE Use `uv run --locked bump-my-version bump patch` to bump versions correctly
from .errors import CommandError
from .scpi import SCPIDevice, SCPIProtocol

__all__ = ["SCPIProtocol", "CommandError", "SCPIDevice"]
