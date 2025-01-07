"""Generic SCPI commands, allow sending and reading of raw data, helpers to parse information"""

from typing import Any, Tuple, Sequence, Union, Optional, cast
import asyncio
import re
import logging
from dataclasses import dataclass, field

from .errors import CommandError
from .transports.baseclass import AbstractTransport, BaseTransport
from .transports.gpib import GPIBDeviceTransport, GPIBTransport


COMMAND_DEFAULT_TIMEOUT = 1.0
ERROR_RE = re.compile(r'([+-]?\d+),"(.*?)"')
LOGGER = logging.getLogger(__name__)


# FIXME rename to mixin and use as such
class BitEnum:  # pylint: disable=R0903
    """Baseclass for bit definitions of various status registers"""

    @classmethod
    def test_bit(cls, statusvalue: int, bitname: str) -> bool:
        """Test if the given status value has the given bit set"""
        bitval = cast(int, getattr(cls, bitname))
        return bool(bitval & statusvalue)


# FIXME use enum.IntEnum as baseclass (maybe, we can't do the docstrings the names if we do...)
class ESRBit(BitEnum):
    """Define meanings of the Event Status Register (ESR) bits"""

    @property
    def power_on(self) -> int:
        """Power-on. The power has cycled"""
        return 128

    @property
    def user_request(self) -> int:
        """User request. The instrument operator has issued a request,
        for instance turning a knob on the front panel."""
        return 64

    @property
    def command_error(self) -> int:
        """Command Error. A command error has occurred."""
        return 32

    @property
    def exec_error(self) -> int:
        """Execution error. The instrument was not able to execute a command for
        some reason. The reason can be that the supplied data is out of range but
        can also be an external event like a safety switch/knob or some hardware /
        software error."""
        return 16

    @property
    def device_error(self) -> int:
        """Device Specific Error."""
        return 8

    @property
    def query_error(self) -> int:
        """Query Error. Error occurred during query processing."""
        return 4

    @property
    def control_request(self) -> int:
        """Request Control. The instrument is requesting to become active controller."""
        return 2

    @property
    def operation_complete(self) -> int:
        """Operation Complete. The instrument has completed all operations.
        This bit is used for synchronisation purposes."""
        return 1


class STBBit(BitEnum):
    """Define meanings of the STatus Byte register (STB) bits"""

    @property
    def rqs_mss(self) -> int:
        """RQS, ReQuested Service. This bit is set when the instrument has requested
        service by means of the SeRvice Request (SRQ). When the controller reacts
        by performing a serial poll, the STatus Byte register (STB) is transmitted with
        this bit set. Afand cleared afterwards. It is only set again when a new event
        occurs that requires service.

        MSS, Master Summary Status. This bit is a summary of the STB and the
        SRE register bits 1..5 and 7. Thus it is not cleared when a serial poll occurs.
        It is cleared when the event which caused the setting of MSS is cleared or
        when the corresponding bits in the SRE register are cleared."""
        return 64

    @property
    def rqs(self) -> int:
        """alias for rqs_mss"""
        return self.rqs_mss

    @property
    def mss(self) -> int:
        """alias for rqs_mss"""
        return self.rqs_mss

    @property
    def esb(self) -> int:
        """ESB, Event Summary Bit. This is a summary bit of the standard status
        registers ESR and ESE"""
        return 32

    @property
    def event_summary(self) -> int:
        """Alias for esb"""
        return self.esb

    @property
    def mav(self) -> int:
        """MAV, Message AVailable. This bit is set when there is data in the output
        queue waiting to be read."""
        return 16

    @property
    def message_available(self) -> int:
        """Alias for mav"""
        return self.mav

    @property
    def eav(self) -> int:
        """EAV, Error AVailable. This bit is set when there is data in the output
        queue waiting to be read."""
        return 4

    @property
    def error_available(self) -> int:
        """Alias for eav"""
        return self.eav


@dataclass
class SCPIProtocol:
    """Implements the SCPI protocol talks over the given transport"""

    transport: Union[BaseTransport, GPIBDeviceTransport, GPIBTransport] = field()
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _checking_error: bool = field(default=False)

    async def quit(self) -> None:
        """Shuts down any background threads that might be active"""
        await self.transport.quit()

    async def abort_command(self) -> None:
        """Shortcut to the transports abort_command call"""
        await self.transport.abort_command()

    async def get_error(self) -> Tuple[int, str]:
        """Asks for the error code and string"""
        if self._checking_error:
            raise RuntimeError("Recursion on get_error detected")
        try:
            self._checking_error = True
            response = await self.ask("SYST:ERR?", auto_check_error=False)
            match = ERROR_RE.search(response)
            if not match:
                # PONDER: Make our own exceptions ??
                raise ValueError("Response '{:s}' does not have correct error format".format(response))
            code = int(match.group(1))
            errstr = match.group(2)
            return (code, errstr)
        finally:
            self._checking_error = False

    async def check_error(self, prev_command: str = "") -> None:
        """Check for error and raise exception if present"""
        code, errstr = await self.get_error()
        if code != 0:
            raise CommandError(prev_command, code, errstr)

    async def command(
        self,
        command: str,
        cmd_timeout: float = COMMAND_DEFAULT_TIMEOUT,
        abort_on_timeout: bool = True,
        *,
        auto_check_error: bool = True,
    ) -> None:
        """Sends a command, does not wait for response"""
        try:

            async def _command(command: str) -> None:
                """Wrap the actual work"""
                nonlocal self
                async with self.lock:
                    await self.transport.send_command(command)

            await asyncio.wait_for(_command(command), timeout=cmd_timeout)
        except asyncio.TimeoutError as err:
            # check for the actual error if available
            if auto_check_error:
                await self.check_error(command)
            if abort_on_timeout:
                await self.abort_command()
            # re-raise the timeout if no other error found
            raise err
        except asyncio.CancelledError:
            LOGGER.info("Cancelled")
        # other errors are allowed to bubble-up as-is

    async def safe_command(self, command: str, *args: Any, **kwargs: Any) -> None:
        """See "command", this just auto-checks for errors each time"""
        await self.command(command, *args, **kwargs)
        await self.check_error(command)

    async def ask(
        self,
        command: str,
        cmd_timeout: float = COMMAND_DEFAULT_TIMEOUT,
        abort_on_timeout: bool = True,
        *,
        auto_check_error: bool = True,
    ) -> str:
        """Send a command and waits for response, returns the response"""
        try:

            async def _ask(command: str) -> str:
                """Wrap the actual work"""
                nonlocal self
                async with self.lock:
                    await self.transport.send_command(command)
                    return await self.transport.get_response()

            return await asyncio.wait_for(_ask(command), timeout=cmd_timeout)
        except asyncio.TimeoutError as err:
            # check for the actual error if available
            if auto_check_error:
                await self.check_error(command)
            if abort_on_timeout:
                await self.abort_command()
            # re-raise the timeout if no other error found
            raise err
        except asyncio.CancelledError:
            LOGGER.info("Cancelled")
            # gotta return something or raise an error
            raise
        # other errors are allowed to bubble-up as-is

    async def safe_ask(self, command: str, *args: Any, **kwargs: Any) -> str:
        """See "ask", this just autp-checks for errors each time"""
        response = await self.ask(command, *args, **kwargs)
        await self.check_error(command)
        return response


@dataclass
class SCPIDevice:  # pylint: disable=R0904
    """Implements nicer wrapper methods for the raw commands from the generic SCPI command set

    See also devices.mixins for mixin classes with more features"""

    instancefrom: Union[BaseTransport, "SCPIDevice", SCPIProtocol, GPIBDeviceTransport, GPIBTransport]
    use_safe_variants: bool = field(default=True)
    protocol: SCPIProtocol = field(init=False)
    transport: AbstractTransport = field(init=False)
    _can_poll: bool = field(default=False)

    def __post_init__(self) -> None:
        """Set protocol and transport based on what we're instancing from"""
        protocol: Optional[SCPIProtocol] = None
        if isinstance(self.instancefrom, SCPIProtocol):
            protocol = self.instancefrom
        if isinstance(self.instancefrom, (BaseTransport, GPIBDeviceTransport, GPIBTransport)):
            protocol = SCPIProtocol(self.instancefrom)
        if isinstance(self.instancefrom, SCPIDevice):
            protocol = self.instancefrom.protocol
        if not protocol:
            raise RuntimeError("Could not resolve protocol/transport")
        self.protocol = protocol
        self.transport = self.protocol.transport
        # Check if transport poll method exists
        # TODO: the transport class should have a marker property for this we should use
        try:
            _ = self.transport.poll  # type: ignore
            self._can_poll = True
        except AttributeError:
            pass

    async def command(
        self, command: str, cmd_timeout: float = COMMAND_DEFAULT_TIMEOUT, abort_on_timeout: bool = True
    ) -> None:
        """Wrap the protocol command (using safe version if requested)"""
        if self.use_safe_variants:
            return await self.protocol.safe_command(command, cmd_timeout, abort_on_timeout)
        return await self.protocol.command(command, cmd_timeout, abort_on_timeout)

    async def ask(
        self, command: str, cmd_timeout: float = COMMAND_DEFAULT_TIMEOUT, abort_on_timeout: bool = True
    ) -> str:
        """Wrap the protocol ask (using safe version if requested)"""
        if self.use_safe_variants:
            return await self.protocol.safe_ask(command, cmd_timeout, abort_on_timeout)
        return await self.protocol.ask(command, cmd_timeout, abort_on_timeout)

    async def quit(self) -> None:
        """Shuts down any background threads that might be active"""
        await self.protocol.quit()

    async def abort(self) -> None:
        """Tells the protocol layer to issue "Device clear" to abort the command currently hanging"""
        await self.protocol.abort_command()

    async def get_error(self) -> Tuple[int, str]:
        """Shorthand for procotols method of the same name"""
        return await self.protocol.get_error()

    async def reset(self) -> None:
        """Resets the device to known state (with *RST) and clears the error log"""
        return await self.protocol.command("*RST;*CLS")

    async def wait_for_complete(self, wait_timeout: float) -> bool:
        """Wait for all queued operations to complete (up-to defined timeout)"""
        resp = await self.ask("*WAI;*OPC?", cmd_timeout=wait_timeout)
        return bool(int(resp))

    async def identify(self) -> Sequence[str]:
        """Returns the identification data, standard order is:
        Manufacturer, Model no, Serial no (or 0), Firmware version"""
        resp = await self.ask("*IDN?")
        return resp.split(",")

    async def query_esr(self) -> int:
        """Queries the event status register (ESR) NOTE: The register is cleared when read!
        returns int instead of Decimal like the other number queries since we need to be able
        to do bitwise comparisons"""
        resp = await self.ask("*ESR?")
        return int(resp)

    async def query_ese(self) -> int:
        """Queries the event status enable (ESE).
        returns int instead of Decimal like the other number queries since we need to be able
        to do bitwise comparisons"""
        resp = await self.ask("*ESE?")
        return int(resp)

    async def set_ese(self, state: int) -> None:
        """Sets ESE to given value.
        Construct the value with bitwise OR operations using ESRBit properties, for example to enable OPC and exec_error
        error bits in the status flag use: set_ese(ESRBit.operation_complete | ESRBit.exec_error)"""
        await self.command(f"*ESE {state:d}")

    async def query_sre(self) -> int:
        """Queries the service request enable (SRE).
        returns int instead of Decimal like the other number queries since we need to be able
        to do bitwise comparisons"""
        resp = await self.ask("*SRE?")
        return int(resp)

    async def set_sre(self, state: int) -> None:
        """Sets SRE to given value.
        Construct the value with bitwise OR operations using STBBit properties, for example to enable SRQ generation
        on any error or message  use: set_sre(STBBit.mav | STBBit.eav)"""
        await self.command(f"*SRE {state:d}")

    async def query_stb(self) -> int:
        """Queries the status byte (STB).
        returns int instead of Decimal like the other number queries since we need to be able
        to do bitwise comparisons

        If transport implements "serial poll", will use that instead of SCPI query to get the value"""
        if self._can_poll:
            resp = await self.transport.poll()  # type: ignore
        else:
            resp = await self.ask("*STB?")
        return int(resp)

    async def trigger(self) -> None:
        """Send the TRiGger command via SCPI.
        NOTE: For GPIB devices the Group Execute Trigger is way better, use it when possible
        however we do not do it transparently here since it triggers all devices on the bus"""
        await self.command("*TRG")

    async def clear_status(self) -> None:
        """
        Sends a clear status command.
        """
        await self.command("*CLS")

    async def operation_complete(self) -> None:
        """
        Sends an Operation Complete command.
        """
        await self.command("*OPC")

    async def query_options(self) -> str:
        """
        Queries the model's options.
        """
        return await self.ask("*OPT?")

    async def set_power_on_status_clear(self, setting: str) -> None:
        """
        Set the Power-On Status Clear setting.
        """
        await self.command(f"*PSC {setting}")

    async def save_state(self, state: int) -> None:
        """
        The SAV command saves all applied configuration settings.
        """
        state = int(state)
        await self.command("*SAV {state:d}")

    async def restore_state(self, state: int) -> None:
        """
        Restores the power supply to a state previously stored in memory by *SAV command.
        """
        state = int(state)
        await self.command(f"*RCL {state:d}")

    async def power_on_state(self, setting: str) -> None:
        """
        Set the power-on behavior of the system
        """
        setting = str(setting).upper()
        await self.command(f"*OUTP:PON {setting}")
