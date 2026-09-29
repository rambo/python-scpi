"""Blocking wrappers work without an implicit event loop."""

import asyncio

import pytest

from scpi.wrapper import AIOWrapper, DeviceWrapper


class Device:
    """Record the loop used by each operation without instrument hardware."""

    label = "instrument"

    def __init__(self) -> None:
        self.loops: list[asyncio.AbstractEventLoop] = []
        self.closed = False

    async def identify(self) -> str:
        self.loops.append(asyncio.get_running_loop())
        return self.label

    async def fail(self) -> None:
        raise ValueError("device failure")

    async def quit(self) -> None:
        self.loops.append(asyncio.get_running_loop())
        self.closed = True


@pytest.mark.parametrize("wrapper_type", [AIOWrapper, DeviceWrapper])
def test_wrapper_owns_loop(wrapper_type: type[AIOWrapper]) -> None:
    """Repeated calls and shutdown use one loop, including after asyncio.run()."""
    async def noop() -> None:
        pass

    asyncio.run(noop())
    device = Device()
    wrapper = wrapper_type(device)
    try:
        assert wrapper.label == "instrument"
        assert wrapper.identify() == "instrument"
        assert wrapper.identify() == "instrument"
        with pytest.raises(ValueError, match="device failure"):
            wrapper.fail()
    finally:
        wrapper.quit()
    assert device.closed
    assert all(loop is device.loops[0] for loop in device.loops)
    assert device.loops[0].is_closed()
    wrapper.quit()  # Safe when an atexit callback follows manual shutdown.


def test_shared_loop() -> None:
    """Device wrappers can share their controller's loop without closing it."""
    controller = AIOWrapper(Device())
    device = Device()
    wrapper = AIOWrapper(device, loop=controller.loop)
    try:
        wrapper.identify()
        wrapper.quit()
        assert not controller.loop.is_closed()
        assert device.loops == [controller.loop, controller.loop]
        assert controller.identify() == "instrument"
    finally:
        controller.quit()
