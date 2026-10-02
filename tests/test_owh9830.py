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


@pytest.mark.asyncio
async def test_snapshot_mapping_and_cache() -> None:
    protocol = Mock(spec=SCPIProtocol, transport=Mock(spec=BaseTransport))
    protocol.ask = AsyncMock(side_effect=["OFF", "0.1s", "221.5,3.03,0.61,671,7", "OFF", "221.4,3.02,0.60,670,6"])
    hold_times: list[float] = []

    async def command(command: str, *args: object, **kwargs: object) -> None:
        if command.startswith(":HOLD "):
            hold_times.append(asyncio.get_running_loop().time())

    protocol.command = AsyncMock(side_effect=command)
    dev = OWH9830(cast(SCPIProtocol, protocol))
    dev._pace = AsyncMock()
    first, second = await asyncio.gather(dev.measure_snapshot(), dev.measure_snapshot("1a"))
    assert first == {
        "1A": {
            "voltage": Decimal("221.5"),
            "current": Decimal("3.03"),
            "phase_angle": Decimal("0.61"),
            "real_power": Decimal("671"),
            "reactive_power": Decimal("7"),
        }
    }
    assert second["1A"]["real_power"] == Decimal("670")
    assert hold_times[2] - hold_times[1] > 0.1  # Let a fresh frame update between HOLD cycles.
    assert [call.args[0] for call in protocol.command.await_args_list] == [
        ":NUM:NORM:ITEM 8ITEM",
        ":NUM:NORM:OPTION 1,U,1",
        ":NUM:NORM:OPTION 2,I,1",
        ":NUM:NORM:OPTION 3,pha,1",
        ":NUM:NORM:OPTION 4,P,1",
        ":NUM:NORM:OPTION 5,Q,1",
        ":NUM:NORM:NUM 5",
        ":HOLD ON",
        ":HOLD OFF",
        ":HOLD ON",
        ":HOLD OFF",
    ]
    protocol.command.reset_mock()
    all_reply = "221.5,3.03,0.61,671,7,0,0,----,----,----,0,0,----,----,----"
    protocol.ask.side_effect = ["OFF", "0.1s", all_reply]
    all_phases = await dev.measure_snapshot("1a-c")
    assert tuple(all_phases) == ("1A", "1B", "1C")
    assert all_phases["1B"]["voltage"] == Decimal("0")
    assert all_phases["1B"]["phase_angle"] is None
    assert all_phases["1C"]["reactive_power"] is None
    commands = [call.args[0] for call in protocol.command.await_args_list]
    assert commands[0] == ":NUM:NORM:ITEM 16ITEM"
    assert commands[6] == ":NUM:NORM:OPTION 6,U,2"
    assert commands[11] == ":NUM:NORM:OPTION 11,U,3"
    assert commands[-3] == ":NUM:NORM:NUM 15"
    protocol.command.reset_mock()
    protocol.ask.side_effect = ["ON", all_reply]
    assert await dev.measure_snapshot("1A-C") == all_phases
    protocol.command.assert_not_awaited()  # Existing HOLD ON stays ON.
    protocol.ask.side_effect = ["ON"]
    with pytest.raises(ValueError, match="Release HOLD"):
        await dev.measure_snapshot("1A")
    protocol.ask.side_effect = ["OFF", "0.1s", "221,3,0.6,670,0"]
    sigma = await dev.measure_snapshot("1SIGMA")
    assert tuple(sigma) == ("1sigma",)
    assert protocol.command.await_args_list[-4].args[0] == ":NUM:NORM:OPTION 5,Q,0"
    await dev.command(":NUM:NORM:OPTION 1,I,1")
    assert dev._snapshot_elements is None
    for invalid in ("1", "2", "1A-D", "1A;*RST"):
        with pytest.raises(ValueError, match="element must"):
            await dev.measure_snapshot(invalid)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["1,2", "1,2,NaN,4,5", "1,2,,4,5", TimeoutError(), asyncio.CancelledError()])
async def test_snapshot_releases_hold_on_failure(failure: str | BaseException) -> None:
    protocol = Mock(spec=SCPIProtocol, transport=Mock(spec=BaseTransport))
    protocol.ask = AsyncMock(side_effect=["OFF", "0.1s", failure])
    protocol.command = AsyncMock()
    dev = OWH9830(cast(SCPIProtocol, protocol))
    dev._pace = AsyncMock()
    error = ValueError if isinstance(failure, str) else type(failure)
    with pytest.raises(error):
        await dev.measure_snapshot()
    assert [call.args[0] for call in protocol.command.await_args_list[-2:]] == [":HOLD ON", ":HOLD OFF"]
    assert dev._snapshot_elements is None


@pytest.mark.asyncio
async def test_snapshot_long_reply_and_io_exclusion() -> None:
    commands: list[str] = []
    replies = iter(["OFF", "0.1s", "1,2,3,4," + "0" * 119, "11", "22", "----", "44", "55", "230"])

    async def ask(command: str, *args: object, **kwargs: object) -> str:
        commands.append(command)
        await asyncio.sleep(0)
        return next(replies)

    async def command(command: str, *args: object, **kwargs: object) -> None:
        commands.append(command)
        await asyncio.sleep(0)

    protocol = Mock(spec=SCPIProtocol, transport=Mock(spec=BaseTransport))
    protocol.ask = AsyncMock(side_effect=ask)
    protocol.command = AsyncMock(side_effect=command)
    dev = OWH9830(cast(SCPIProtocol, protocol))
    dev._pace = AsyncMock()
    snapshot, voltage = await asyncio.gather(dev.measure_snapshot(), dev.measure_voltage())
    assert snapshot["1A"]["voltage"] == Decimal("11")
    assert snapshot["1A"]["phase_angle"] is None
    assert snapshot["1A"]["reactive_power"] == Decimal("55")
    assert voltage == Decimal("230")
    assert commands[-7:] == [
        ":MEAS:VOLT:ELEMENT1A?",
        ":MEAS:CURR:ELEMENT1A?",
        ":MEAS:PHAS:ELEMENT1A?",
        ":MEAS:POW:REAL:ELEMENT1A?",
        ":MEAS:POW:REAC:ELEMENT1A?",
        ":HOLD OFF",
        ":MEAS:VOLT:ELEMENT1A?",
    ]


@pytest.mark.asyncio
async def test_measure_snapshots_stream() -> None:
    protocol = Mock(spec=SCPIProtocol, transport=Mock(spec=BaseTransport))
    protocol.ask = AsyncMock(
        side_effect=[
            "OFF",
            "0.1s",
            "220.0,3.00,0.60,660,10",
            "220.1,3.01,0.60,661,11",
            "220.2,3.02,0.60,662,12",
        ]
    )
    protocol.command = AsyncMock()
    dev = OWH9830(cast(SCPIProtocol, protocol))
    dev._pace = AsyncMock()

    # 1. Single-element streaming setup once and rapid reads
    stream = dev.measure_snapshots("1A")
    items = []
    async for s in stream:
        items.append(s)
        if len(items) == 3:
            break

    assert len(items) == 3
    assert items[0]["1A"]["voltage"] == Decimal("220.0")
    assert items[1]["1A"]["voltage"] == Decimal("220.1")
    assert items[2]["1A"]["voltage"] == Decimal("220.2")

    # Slot setup was called once only, then :NUM:NORM:VAL? queries
    assert [call.args[0] for call in protocol.command.await_args_list] == [
        ":NUM:NORM:ITEM 8ITEM",
        ":NUM:NORM:OPTION 1,U,1",
        ":NUM:NORM:OPTION 2,I,1",
        ":NUM:NORM:OPTION 3,pha,1",
        ":NUM:NORM:OPTION 4,P,1",
        ":NUM:NORM:OPTION 5,Q,1",
        ":NUM:NORM:NUM 5",
    ]
    assert [call.args[0] for call in protocol.ask.await_args_list] == [
        ":HOLD?",
        ":RATE?",
        ":NUM:NORM:VAL?",
        ":NUM:NORM:VAL?",
        ":NUM:NORM:VAL?",
    ]

    # Stream is still active, verify setup-changing commands are blocked
    with pytest.raises(RuntimeError, match="Cannot measure harmonics"):
        await dev.measure_harmonics()
    with pytest.raises(RuntimeError, match="Cannot execute measure_snapshot"):
        await dev.measure_snapshot()
    with pytest.raises(RuntimeError, match="while snapshot iterator is active"):
        await dev.command(":RATE 1s")
    with pytest.raises(RuntimeError, match="while snapshot iterator is active"):
        await dev.command(":NUM:NORM:NUM 10")
    with pytest.raises(RuntimeError, match="while snapshot iterator is active"):
        await dev.command("*RST")
    with pytest.raises(RuntimeError, match="while snapshot iterator is active"):
        await dev.command(":DISP:MOD NORM")
    with pytest.raises(RuntimeError, match="while snapshot iterator is active"):
        await dev.command(":HOLD ON")
    with pytest.raises(RuntimeError, match="while snapshot iterator is active"):
        await dev.command(":HARM:ORD:ELEMENT1A 1,7")

    # Concurrent iterator should be refused
    stream2 = dev.measure_snapshots("1B")
    with pytest.raises(RuntimeError, match="Snapshot iterator is already active"):
        await anext(stream2)

    # Non-setup modifying queries work
    protocol.ask.side_effect = ["220.5"]
    assert await dev.measure_voltage("1A") == Decimal("220.5")

    # Close the stream
    await stream.aclose()

    # After close, setup commands and measure_snapshot work again
    protocol.ask.side_effect = ["OFF", "220.0,3.00,0.60,660,10"]
    protocol.command.reset_mock()
    snap = await dev.measure_snapshot("1A")
    assert snap["1A"]["voltage"] == Decimal("220.0")

    # Context manager usage
    protocol.ask.side_effect = ["220.0,3.00,0.60,660,10"]
    async with dev.measure_snapshots("1A") as stream3:
        item = await anext(stream3)
        assert item["1A"]["voltage"] == Decimal("220.0")
        assert dev._streaming_snapshots is True
    assert dev._streaming_snapshots is False


@pytest.mark.asyncio
async def test_harmonic_snapshot_mapping_and_errors() -> None:
    protocol = Mock(spec=SCPIProtocol, transport=Mock(spec=BaseTransport))
    protocol.ask = AsyncMock(
        side_effect=[
            "OFF",
            "NORM",
            "0.1s",
            "220.0,3.00,0.60,660,10",
            "220.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9,",
            "3.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09,",
        ]
    )
    protocol.command = AsyncMock()
    dev = OWH9830(cast(SCPIProtocol, protocol))
    dev._pace = AsyncMock()

    snap = await dev.measure_harmonic_snapshot("1A", max_order=10)
    assert snap["1A"]["voltage"] == Decimal("220.0")
    assert snap["1A"]["real_power"] == Decimal("660")
    assert snap["1A"]["harmonics"]["voltage"] == tuple(
        Decimal(f"0.{i}") if i > 0 else Decimal("220.0") for i in range(10)
    )
    assert snap["1A"]["harmonics"]["current"] == tuple(
        Decimal(f"0.0{i}") if i > 0 else Decimal("3.0") for i in range(10)
    )

    assert [call.args[0] for call in protocol.command.await_args_list] == [
        ":DISP:MOD HARMONIC",
        ":HARM:ORD:ELEMENT1A 1,10",
        ":NUM:NORM:ITEM 8ITEM",
        ":NUM:NORM:OPTION 1,U,1",
        ":NUM:NORM:OPTION 2,I,1",
        ":NUM:NORM:OPTION 3,pha,1",
        ":NUM:NORM:OPTION 4,P,1",
        ":NUM:NORM:OPTION 5,Q,1",
        ":NUM:NORM:NUM 5",
        ":HOLD ON",
        ":HOLD OFF",
    ]

    # Error conditions
    for bad_order in (0, 11, True, "10", 2.5):
        with pytest.raises(ValueError, match="max_order must be an integer from 1 to 10"):
            await dev.measure_harmonic_snapshot("1A", max_order=cast(int, bad_order))

    with pytest.raises(ValueError, match="harmonics support 1A, 1B and 1C only"):
        await dev.measure_harmonic_snapshot("1sigma")


@pytest.mark.asyncio
async def test_harmonic_snapshots_stream() -> None:
    protocol = Mock(spec=SCPIProtocol, transport=Mock(spec=BaseTransport))
    protocol.ask = AsyncMock(
        side_effect=[
            "OFF",
            "HARMONIC",
            "0.1s",
            "220.0,3.00,0.60,660,10",
            "220.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6,",
            "3.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06,",
            "220.1,3.01,0.60,661,11",
            "220.1, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6,",
            "3.01, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06,",
        ]
    )
    protocol.command = AsyncMock()
    dev = OWH9830(cast(SCPIProtocol, protocol))
    dev._pace = AsyncMock()

    items = []
    async for s in dev.measure_harmonic_snapshots("1A", max_order=7):
        items.append(s)
        if len(items) == 2:
            break

    assert len(items) == 2
    assert items[0]["1A"]["voltage"] == Decimal("220.0")
    assert len(items[0]["1A"]["harmonics"]["voltage"]) == 7
    assert items[1]["1A"]["voltage"] == Decimal("220.1")
    assert len(items[1]["1A"]["harmonics"]["voltage"]) == 7

    assert [call.args[0] for call in protocol.command.await_args_list] == [
        ":HARM:ORD:ELEMENT1A 1,7",
        ":NUM:NORM:ITEM 8ITEM",
        ":NUM:NORM:OPTION 1,U,1",
        ":NUM:NORM:OPTION 2,I,1",
        ":NUM:NORM:OPTION 3,pha,1",
        ":NUM:NORM:OPTION 4,P,1",
        ":NUM:NORM:OPTION 5,Q,1",
        ":NUM:NORM:NUM 5",
    ]
