"""OWON OWH9830 measurements (programming manual, chapters 4 and 7)."""

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, Self, override

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
    _snapshot_elements: tuple[str, ...] | None = field(default=None, init=False, repr=False)
    _snapshot_period: float = field(default=0.5, init=False, repr=False)
    _snapshot_ready_at: float = field(default=0, init=False, repr=False)
    _streaming_snapshots: bool = field(default=False, init=False, repr=False)

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
            return await self._ask(command, cmd_timeout, abort_on_timeout)

    async def _ask(
        self, command: str, cmd_timeout: float = COMMAND_DEFAULT_TIMEOUT, abort_on_timeout: bool = False
    ) -> str:
        """Query while the caller owns _io_lock."""
        await self._pace()
        return await self.protocol.ask(command, cmd_timeout, abort_on_timeout, auto_check_error=False)

    @override
    async def command(
        self, command: str, cmd_timeout: float = COMMAND_DEFAULT_TIMEOUT, abort_on_timeout: bool = False
    ) -> None:
        """Pace configuration commands; no serial BREAK is sent by default."""
        async with self._io_lock:
            await self._command(command, cmd_timeout, abort_on_timeout)

    async def _command(
        self, command: str, cmd_timeout: float = COMMAND_DEFAULT_TIMEOUT, abort_on_timeout: bool = False
    ) -> None:
        """Configure while the caller owns _io_lock."""
        normalized = command.strip().upper().lstrip(":")
        if self._streaming_snapshots and normalized.startswith(("NUM", "RATE", "*RST", "DISP", "HARM", "HOLD")):
            raise RuntimeError(f"Cannot execute {command.strip()!r} while snapshot iterator is active")
        if normalized.startswith(("NUM", "RATE", "*RST")):
            self._snapshot_elements = None
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

    async def measure_snapshot(self, element: str = "1A") -> dict[str, dict[str, Decimal | None]]:
        """Read voltage/current/phase/real/reactive power for one element or 1A-C.

        Returns an element-keyed dictionary, with units V, A, degrees, W and var.
        Unavailable fields are None. Configures and owns the numeric display page;
        repeated calls with the same selection reuse its configuration.
        HOLD freezes reported values for the read and its previous state is restored.
        Allows one update period before freezing a new frame. Changing selection
        while HOLD is already ON raises ValueError; unchanged selections remain held.
        Measurement mode is preserved. This does not prove simultaneous ADC sampling.
        """
        if self._streaming_snapshots:
            raise RuntimeError("Cannot execute measure_snapshot while snapshot iterator is active")
        normalized = element.upper()
        if normalized == "1A-C":
            elements = ("1A", "1B", "1C")
        else:
            normalized = self._element(element)
            elements = ("1sigma" if normalized == "1SIGMA" else normalized,)
        fields = ("voltage", "current", "phase_angle", "real_power", "reactive_power")
        async with self._io_lock:
            hold = (await self._ask(":HOLD?")).strip().upper()
            if hold not in ("ON", "OFF", "1", "0"):
                raise ValueError(f"Unexpected OWH9830 HOLD state: {hold!r}")
            release_hold = hold in ("OFF", "0")
            if self._snapshot_elements != elements:
                if not release_hold:
                    raise ValueError("Release HOLD before changing snapshot selection")
                await self._configure_snapshot(elements)
            try:
                if release_hold:
                    await asyncio.sleep(max(0, self._snapshot_ready_at - asyncio.get_running_loop().time()))
                    await self._command(":HOLD ON")
                values = await self._snapshot_values(elements)
            except BaseException:
                self._snapshot_elements = None
                raise
            finally:
                if release_hold:
                    await self._command(":HOLD OFF")
                    self._snapshot_ready_at = asyncio.get_running_loop().time() + self._snapshot_period + 0.11
        return {
            selected: dict(zip(fields, values[index * len(fields) : (index + 1) * len(fields)], strict=True))
            for index, selected in enumerate(elements)
        }

    async def _configure_snapshot(self, elements: tuple[str, ...]) -> None:
        """Select numeric slots while the caller owns _io_lock and HOLD is OFF."""
        functions = ("U", "I", "pha", "P", "Q")
        channels = {"1A": 1, "1B": 2, "1C": 3, "1sigma": 0}
        await self._command(f":NUM:NORM:ITEM {16 if len(elements) == 3 else 8}ITEM")
        for index, selected in enumerate(elements):
            for offset, function in enumerate(functions, 1):
                slot = index * len(functions) + offset
                await self._command(f":NUM:NORM:OPTION {slot},{function},{channels[selected]}")
        await self._command(f":NUM:NORM:NUM {len(elements) * len(functions)}")
        period = float((await self._ask(":RATE?")).strip().removesuffix("s"))
        if period not in (0.1, 0.2, 0.5, 1, 2, 5):
            raise ValueError(f"Unexpected OWH9830 update period: {period!r}")
        self._snapshot_period = period
        self._snapshot_ready_at = asyncio.get_running_loop().time() + period + 0.11
        self._snapshot_elements = elements

    async def _snapshot_values(self, elements: tuple[str, ...]) -> list[Decimal | None]:
        """Read numeric slots while the caller owns _io_lock and HOLD is active."""
        count = len(elements) * 5
        command = ":NUM:NORM:VAL?"
        response = await self._ask(command)
        # V1.2.0 has a 128-byte output buffer, including LF.
        if len(response) >= 127:
            # Indexed NUM slot reads disagree with bulk data on this firmware.
            quantities = ("VOLT", "CURR", "PHAS", "POW:REAL", "POW:REAC")
            replies = [
                await self._ask(f":MEAS:{quantity}:ELEMENT{selected.upper()}?")
                for selected in elements
                for quantity in quantities
            ]
        else:
            replies = response.strip().removesuffix(",").split(",")
        if len(replies) != count:
            raise ValueError(f"Expected {count} snapshot values, got {response!r}")
        return [None if value.strip() == "----" else self._numbers(value, command)[0] for value in replies]

    async def measure_harmonics(self, element: str = "1A", max_order: int = 7) -> dict[str, tuple[Decimal | None, ...]]:
        """Return voltage (V) and current (A) RMS harmonics, orders 1..max_order.

        Index zero is the fundamental. max_order must be an integer 1..63.
        Enables harmonic measurement mode and leaves it enabled so data keeps
        updating. Scalar measurements also work in this mode. Sigma is unsupported.
        Updates the display order range. Reads are sequential, not an atomic snapshot.
        Above order 10, unavailable readings (----) are represented by None.
        """
        if self._streaming_snapshots:
            raise RuntimeError("Cannot measure harmonics while snapshot iterator is active")
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

    def measure_snapshots(self, element: str = "1A") -> "SnapshotStream":
        """Stream snapshots as fast as possible using an async iterator.

        Configures numeric display slots once and reuses them on every poll.
        Commands that change instrument setup refuse to execute while active.
        """
        normalized = element.upper()
        if normalized == "1A-C":
            elements = ("1A", "1B", "1C")
        else:
            normalized = self._element(element)
            elements = ("1sigma" if normalized == "1SIGMA" else normalized,)
        fields = ("voltage", "current", "phase_angle", "real_power", "reactive_power")
        return SnapshotStream(self, elements, fields)

    stream_snapshots = measure_snapshots
    snapshots = measure_snapshots


class SnapshotStream:
    """Async iterator for rapid OWH9830 snapshot measurement streaming."""

    def __init__(self, dev: OWH9830, elements: tuple[str, ...], fields: tuple[str, ...]) -> None:
        self._dev = dev
        self._elements = elements
        self._fields = fields
        self._closed = False
        self._configured = False

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> dict[str, dict[str, Decimal | None]]:
        if self._closed:
            raise StopAsyncIteration
        if not self._configured:
            if self._dev._streaming_snapshots:
                raise RuntimeError("Snapshot iterator is already active")
            try:
                async with self._dev._io_lock:
                    if self._dev._snapshot_elements != self._elements:
                        hold = (await self._dev._ask(":HOLD?")).strip().upper()
                        if hold not in ("OFF", "0"):
                            raise ValueError("Release HOLD before changing snapshot selection")
                        await self._dev._configure_snapshot(self._elements)
                self._dev._streaming_snapshots = True
            except BaseException:
                self._dev._streaming_snapshots = False
                self._closed = True
                raise
            self._configured = True

        async with self._dev._io_lock:
            try:
                values = await self._dev._snapshot_values(self._elements)
            except BaseException:
                self._dev._snapshot_elements = None
                await self.aclose()
                raise
        return {
            selected: dict(
                zip(self._fields, values[index * len(self._fields) : (index + 1) * len(self._fields)], strict=True)
            )
            for index, selected in enumerate(self._elements)
        }

    async def aclose(self) -> None:
        if not self._closed:
            self._closed = True
            if self._configured:
                self._dev._streaming_snapshots = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self.aclose()

    def __del__(self) -> None:
        if self._configured and not self._closed:
            self._dev._streaming_snapshots = False
            self._closed = True


def serial(serial_url: str, baudrate: int = 115200, **kwargs: Any) -> OWH9830:
    """Connect directly by RS-232 (SCPI, 8N1); baudrate must match the meter."""
    port = pyserial.serial_for_url(serial_url.strip(), baudrate=baudrate, **kwargs)
    return OWH9830(_SerialTransport(serialdevice=port))
