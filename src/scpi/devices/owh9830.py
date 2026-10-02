"""OWON OWH9830 measurements (programming manual, chapters 4 and 7)."""

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, override

import serial as pyserial

from ..scpi import COMMAND_DEFAULT_TIMEOUT, SCPIDevice
from ..transports.rs232 import RS232Transport


class _SerialTransport(RS232Transport):
    """OWON serial replies end with LF."""

    _terminator: ClassVar[bytes] = b"\n"


@dataclass
class OWH9830(SCPIDevice):
    """RMS measurements using elements 1A, 1B, 1C and 1sigma.

    Commands are spaced by more than 100 ms as required by the manual.
    Generic SYST:ERR? checks are unsupported, including on timeouts.
    Use one instance per instrument; AIOWrapper supports blocking calls.
    """

    use_safe_variants: bool = field(default=False)
    _io_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _harmonic_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _last_command: float = field(default=float("-inf"), init=False, repr=False)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.use_safe_variants:
            raise ValueError("OWH9830 does not support generic SYST:ERR? checks")

    async def _pace(self) -> None:
        loop = asyncio.get_running_loop()
        await asyncio.sleep(max(0, self._last_command + 0.11 - loop.time()))
        self._last_command = loop.time()

    @override
    async def ask(
        self, command: str, cmd_timeout: float = COMMAND_DEFAULT_TIMEOUT, abort_on_timeout: bool = False
    ) -> str:
        """Pace queries without issuing unsupported error queries on timeout."""
        async with self._io_lock:
            await self._pace()
            return await self.protocol.ask(command, cmd_timeout, abort_on_timeout, auto_check_error=False)

    @override
    async def command(
        self, command: str, cmd_timeout: float = COMMAND_DEFAULT_TIMEOUT, abort_on_timeout: bool = False
    ) -> None:
        """Pace configuration commands; no serial BREAK is sent by default."""
        async with self._io_lock:
            await self._pace()
            await self.protocol.command(command, cmd_timeout, abort_on_timeout, auto_check_error=False)

    @staticmethod
    def _element(element: str, *, harmonics: bool = False) -> str:
        normalized = element.upper()
        if normalized not in ("1A", "1B", "1C", "1SIGMA"):
            raise ValueError("element must be 1A, 1B, 1C or 1sigma")
        if harmonics and normalized == "1SIGMA":
            raise ValueError("OWH9830 harmonics support 1A, 1B and 1C only")
        return normalized

    async def _values(self, command: str, count: int = 1) -> tuple[Decimal, ...]:
        return self._numbers(await self.ask(command), command, count)

    @staticmethod
    def _numbers(response: str, command: str, count: int = 1) -> tuple[Decimal, ...]:
        # Firmware V1.2.0 appends a comma to harmonic lists.
        fields = response.strip().removesuffix(",").split(",")
        try:
            values = tuple(Decimal(value.strip()) for value in fields)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid OWH9830 response to {command!r}: {response!r}; check meter LOCAL state") from exc
        if len(values) != count or not all(value.is_finite() for value in values):
            raise ValueError(f"Expected {count} finite values for {command!r}, got {response!r}")
        return values

    async def measure_voltage(self, element: str = "1A") -> Decimal:
        """Return RMS voltage in volts."""
        return (await self._values(f":MEAS:VOLT:ELEMENT{self._element(element)}?"))[0]

    async def measure_current(self, element: str = "1A") -> Decimal:
        """Return RMS current in amps."""
        return (await self._values(f":MEAS:CURR:ELEMENT{self._element(element)}?"))[0]

    async def measure_phase_angle(self, element: str = "1A") -> Decimal:
        """Return the voltage/current phase angle in degrees."""
        return (await self._values(f":MEAS:PHAS:ELEMENT{self._element(element)}?"))[0]

    async def measure_real_power(self, element: str = "1A") -> Decimal:
        """Return real (active) power in watts."""
        return (await self._values(f":MEAS:POW:REAL:ELEMENT{self._element(element)}?"))[0]

    async def measure_reactive_power(self, element: str = "1A") -> Decimal:
        """Return reactive power in var."""
        return (await self._values(f":MEAS:POW:REAC:ELEMENT{self._element(element)}?"))[0]

    async def measure_harmonics(self, element: str = "1A", max_order: int = 7) -> dict[str, tuple[Decimal | None, ...]]:
        """Return voltage (V) and current (A) RMS harmonics, orders 1..max_order.

        Index zero is the fundamental. max_order must be an integer 1..63.
        Enables harmonic measurement mode and leaves it enabled so data keeps
        updating. Scalar measurements also work in this mode. Sigma is unsupported.
        Updates the display order range. Reads are sequential, not an atomic snapshot.
        Above order 10, unavailable readings (----) are represented by None.
        """
        element = self._element(element, harmonics=True)
        if isinstance(max_order, bool) or not isinstance(max_order, int) or not 1 <= max_order <= 63:
            raise ValueError("max_order must be an integer from 1 to 63")
        async with self._harmonic_lock:
            mode = (await self.ask(":DISP:MOD?")).strip().upper()
            if mode in ("NORM", "0"):
                await self.command(":DISP:MOD HARMONIC")
            elif mode not in ("HARMONIC", "1"):
                raise ValueError(f"Unexpected OWH9830 measurement mode: {mode!r}")
            await self.command(f":HARM:ORD:ELEMENT{element} 1,{max_order}")
            if mode in ("NORM", "0") or max_order > 10:
                period = float((await self.ask(":RATE?")).strip().removesuffix("s"))
                if period not in (0.1, 0.2, 0.5, 1, 2, 5):
                    raise ValueError(f"Unexpected OWH9830 update period: {period!r}")
                await asyncio.sleep(period + 0.11)
            if max_order <= 10:
                return {
                    "voltage": await self._values(f":HARM:LIST:VAL:ELEMENT{element}? VOLT", max_order),
                    "current": await self._values(f":HARM:LIST:VAL:ELEMENT{element}? CURR", max_order),
                }
            result: dict[str, list[Decimal | None]] = {"voltage": [], "current": []}
            # V1.2.0 list replies truncate at 128 bytes and can omit separators.
            # ponytail: two queries per order above 10; batch when firmware lists are reliable.
            for order in range(1, max_order + 1):
                for name, quantity in (("voltage", "VOLT"), ("current", "CURR")):
                    command = f":MEAS:{quantity}:HARM:ORDER:ELEMENT{element}? {order}"
                    response = await self.ask(command)
                    result[name].append(None if response.strip() == "----" else self._numbers(response, command)[0])
        return {name: tuple(values) for name, values in result.items()}


def serial(serial_url: str, baudrate: int = 115200, **kwargs: Any) -> OWH9830:
    """Connect directly by RS-232 (SCPI, 8N1); baudrate must match the meter."""
    port = pyserial.serial_for_url(serial_url.strip(), baudrate=baudrate, **kwargs)
    return OWH9830(_SerialTransport(serialdevice=port))
