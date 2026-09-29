"""Helper class to allow using of device in traditional blocking style without having to deal with the ioloop"""

from typing import Any
import asyncio
import functools
import inspect
import logging


LOGGER = logging.getLogger(__name__)


class AIOWrapper:  # pylint: disable=R0903
    """Wraps all coroutine methods into asyncio run_until_complete calls"""

    def __init__(self, to_be_wrapped: Any, *, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Init wrapper for device"""
        self._device = to_be_wrapped
        self._loop = loop if loop is not None else asyncio.new_event_loop()
        self._owns_loop = loop is None
        self._closed = False
        for attr in functools.WRAPPER_ASSIGNMENTS:
            try:
                setattr(self, attr, getattr(self._device, attr))
            except AttributeError:
                try:
                    setattr(self.__class__, attr, getattr(self._device.__class__, attr))
                except AttributeError:
                    LOGGER.debug("Could not copy {}".format(attr))

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """The loop to share with wrappers using the same transport."""
        return self._loop

    def __getattr__(self, item: str) -> Any:
        """Get a memeber, if it's a coroutine autowrap it to eventloop run"""
        orig = getattr(self._device, item)
        if inspect.iscoroutinefunction(orig):

            @functools.wraps(orig)
            def wrapped(*args: Any, **kwargs: Any) -> Any:
                """Gets the waitable and tells the event loop to run it"""
                nonlocal self
                if self._closed:
                    raise RuntimeError("Wrapper is closed")
                waitable = orig(*args, **kwargs)
                return self._loop.run_until_complete(waitable)

            return wrapped
        return orig

    def __dir__(self) -> Any:
        """Proxy the dir on the device"""
        return dir(self._device)

    def quit(self) -> None:
        """Calls the device.quit via loop and closes the loop"""
        if self._closed:
            return
        try:
            self._loop.run_until_complete(self._device.quit())
        finally:
            self._closed = True
            if self._owns_loop:
                self._loop.close()


class DeviceWrapper(AIOWrapper):  # pylint: disable=R0903
    """Legacy name for the AsyncIO wrapper class for backwards compatibility"""
