"""OWH9830 command mapping, firmware replies and request validation."""

import asyncio
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock, Mock

import pytest

from scpi.devices.owh9830 import OWH9830
from scpi.scpi import SCPIProtocol
from scpi.transports.baseclass import BaseTransport


@pytest.mark.asyncio
async def test_measurements() -> None:
    protocol = Mock(spec=SCPIProtocol, transport=Mock(spec=BaseTransport))
    protocol.ask = AsyncMock(return_value=" 1.25\r\n")
    protocol.command = AsyncMock()
    dev = OWH9830(cast(SCPIProtocol, protocol))
    dev._pace = AsyncMock()
    methods = (
        (dev.measure_voltage, "VOLT"),
        (dev.measure_current, "CURR"),
        (dev.measure_phase_angle, "PHAS"),
        (dev.measure_real_power, "POW:REAL"),
        (dev.measure_reactive_power, "POW:REAC"),
    )
    for method, command in methods:
        for element in ("1A", "1B", "1C", "1sigma"):
            assert await method(element) == Decimal("1.25")
            protocol.ask.assert_awaited_with(
                f":MEAS:{command}:ELEMENT{element.upper()}?", 1.0, False, auto_check_error=False
            )

    for bad_element in ("1", "2", "1D", "1A;*RST"):
        with pytest.raises(ValueError, match="element must"):
            await dev.measure_voltage(bad_element)
    for bad_order in (0, 64, True, 2.5):
        with pytest.raises(ValueError, match="max_order"):
            await dev.measure_harmonics(max_order=cast(int, bad_order))
    with pytest.raises(ValueError, match="harmonics support"):
        await dev.measure_harmonics("1sigma")
    assert protocol.ask.await_count == 20
    protocol.command.assert_not_awaited()

    for response in ("", "\n", "garbage", "1,,2", "NaN", "Infinity", "1,2"):
        protocol.ask.return_value = response
        with pytest.raises(ValueError):
            await dev.measure_voltage()

    # Two concurrent callers must not overwrite each other's harmonic range.
    protocol.ask.side_effect = ["HARMONIC", "230, 0.1, \n", "1.2, 0.001, \n", "HARMONIC", "230", "1.2"]
    harmonics, fundamental = await asyncio.gather(
        dev.measure_harmonics("1B", max_order=2), dev.measure_harmonics("1C", max_order=1)
    )
    assert harmonics == {"voltage": (Decimal("230"), Decimal("0.1")), "current": (Decimal("1.2"), Decimal("0.001"))}
    assert fundamental == {"voltage": (Decimal("230"),), "current": (Decimal("1.2"),)}
    assert [call.args[0] for call in protocol.command.await_args_list] == [
        ":HARM:ORD:ELEMENT1B 1,2",
        ":HARM:ORD:ELEMENT1C 1,1",
    ]
    assert [call.args[0] for call in protocol.ask.await_args_list[-6:]] == [
        ":DISP:MOD?",
        ":HARM:LIST:VAL:ELEMENT1B? VOLT",
        ":HARM:LIST:VAL:ELEMENT1B? CURR",
        ":DISP:MOD?",
        ":HARM:LIST:VAL:ELEMENT1C? VOLT",
        ":HARM:LIST:VAL:ELEMENT1C? CURR",
    ]
    protocol.command.reset_mock()
    protocol.ask.side_effect = ["HARMONIC", "0.1s"] + [
        " ----" if order == 25 else str(order) for order in range(1, 64) for _ in range(2)
    ]
    result = await dev.measure_harmonics(max_order=63)
    assert (
        result["voltage"]
        == result["current"]
        == tuple(None if order == 25 else Decimal(order) for order in range(1, 64))
    )
    assert protocol.ask.await_args_list[-1].args[0] == ":MEAS:CURR:HARM:ORDER:ELEMENT1A? 63"
    protocol.command.assert_awaited_once_with(":HARM:ORD:ELEMENT1A 1,63", 1.0, False, auto_check_error=False)
    protocol.ask.side_effect = None
    protocol.ask.side_effect = ["HARMONIC", "1,2,"]
    with pytest.raises(ValueError, match="Expected 3 finite"):
        await dev.measure_harmonics(max_order=3)
    protocol.ask.side_effect = TimeoutError
    with pytest.raises(TimeoutError):
        await dev.measure_voltage()
    protocol.ask.assert_awaited_with(":MEAS:VOLT:ELEMENT1A?", 1.0, False, auto_check_error=False)


@pytest.mark.asyncio
async def test_enable_harmonic_mode() -> None:
    protocol = Mock(spec=SCPIProtocol, transport=Mock(spec=BaseTransport))
    protocol.ask = AsyncMock(side_effect=["NORM", "0.1s", "230", "1.2"])
    protocol.command = AsyncMock()
    dev = OWH9830(cast(SCPIProtocol, protocol))
    dev._pace = AsyncMock()
    result = await dev.measure_harmonics(max_order=1)
    assert result == {"voltage": (Decimal("230"),), "current": (Decimal("1.2"),)}
    assert [call.args[0] for call in protocol.command.await_args_list] == [
        ":DISP:MOD HARMONIC",
        ":HARM:ORD:ELEMENT1A 1,1",
    ]


@pytest.mark.asyncio
async def test_command_spacing() -> None:
    times: list[float] = []

    async def reply(*args: object, **kwargs: object) -> str:
        times.append(asyncio.get_running_loop().time())
        return "1"

    protocol = Mock(spec=SCPIProtocol, transport=Mock(spec=BaseTransport))
    protocol.ask = AsyncMock(side_effect=reply)
    dev = OWH9830(cast(SCPIProtocol, protocol))
    await asyncio.gather(dev.measure_voltage(), dev.measure_current())
    assert times[1] - times[0] > 0.1
