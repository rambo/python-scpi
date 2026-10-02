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


def test_wrapper_async_iterator() -> None:
    """Async iterators can be used synchronously via the wrapper."""

    class StreamDevice(Device):
        def stream(self):
            class AsyncIter:
                def __init__(self, dev: Device) -> None:
                    self.dev = dev
                    self.count = 0
                    self.closed = False

                def __aiter__(self):
                    return self

                async def __anext__(self):
                    if self.closed or self.count >= 3:
                        raise StopAsyncIteration
                    self.dev.loops.append(asyncio.get_running_loop())
                    self.count += 1
                    return self.count

                async def aclose(self):
                    self.closed = True

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args: object):
                    await self.aclose()

            return AsyncIter(self)

    device = StreamDevice()
    wrapper = AIOWrapper(device)
    try:
        results = []
        for item in wrapper.stream():
            results.append(item)
        assert results == [1, 2, 3]

        # Context manager and close
        with wrapper.stream() as it:
            assert next(it) == 1
    finally:
        wrapper.quit()
