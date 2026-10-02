"""Helper class to allow using of device in traditional blocking style without having to deal with the ioloop"""

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from typing import Any, Self

LOGGER = logging.getLogger(__name__)


class _SyncAsyncIterator:
    """Synchronous iterator wrapping an asynchronous iterator or generator."""

    def __init__(
        self,
        async_iter: Any,
        loop: asyncio.AbstractEventLoop,
        is_closed: Callable[[], bool],
    ) -> None:
        self._async_iter = async_iter
        self._loop = loop
        self._is_closed = is_closed

    def __iter__(self) -> Self:
        return self

    def __next__(self) -> Any:
        if self._is_closed():
            raise RuntimeError("Wrapper is closed")
        try:
            return self._loop.run_until_complete(anext(self._async_iter))
        except StopAsyncIteration:
            raise StopIteration

    def close(self) -> None:
        if hasattr(self._async_iter, "aclose") and not self._loop.is_closed():
            self._loop.run_until_complete(self._async_iter.aclose())

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()


class AIOWrapper:
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
                    LOGGER.debug(f"Could not copy {attr}")

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """The loop to share with wrappers using the same transport."""
        return self._loop

    def __getattr__(self, item: str) -> Any:
        """Get a member, wrapping coroutines and async iterators for synchronous use."""
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
        if callable(orig):

            @functools.wraps(orig)
            def wrapped_call(*args: Any, **kwargs: Any) -> Any:
                nonlocal self
                if self._closed:
                    raise RuntimeError("Wrapper is closed")
                res = orig(*args, **kwargs)
                if hasattr(res, "__aiter__") and hasattr(res, "__anext__"):
                    return _SyncAsyncIterator(res, self._loop, lambda: self._closed)
                return res

            return wrapped_call
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


class DeviceWrapper(AIOWrapper):
    """Legacy name for the AsyncIO wrapper class for backwards compatibility"""
