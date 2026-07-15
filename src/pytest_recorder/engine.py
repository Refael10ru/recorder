"""Record/replay engine: RecordingProxy and PlayerProxy over a store callable."""

from collections.abc import Callable
from typing import Any

from pytest_recorder.errors import (
    RecordingExhausted,
    RecordingMismatch,
    RecordingUnderused,
)
from pytest_recorder.serialize import _encode_call, decode, encode, encode_exception
from pytest_recorder.storage import EncodedEvent, RecordingStore


def make_event(
    method: str, args: tuple, kwargs: dict, ret: Any, exc: BaseException | None
) -> EncodedEvent:
    """Build a serialized EncodedEvent for one recorded call."""
    enc_args, enc_kwargs = _encode_call(args, kwargs)
    if exc is not None:
        # FIN-1: encode_exception validates pickle round-trip at record time.
        return EncodedEvent(
            method=method, args=enc_args, kwargs=enc_kwargs,
            result=None, raised=encode_exception(exc),
        )
    return EncodedEvent(
        method=method, args=enc_args, kwargs=enc_kwargs,
        result=encode(ret), raised=None,
    )


def is_recorder_mock(obj: object) -> bool:
    """Return True if *obj* is a RecordingProxy or PlayerProxy, False otherwise."""
    fn = getattr(obj, "__is_recorder_mock__", None)
    return bool(callable(fn) and fn())


class _RecorderMock:
    def __is_recorder_mock__(self) -> bool:
        return True


class RecordingProxy(_RecorderMock):
    """Wrap a real target; record each call, then return/re-raise as normal."""

    def __init__(
        self, target: Any, name: str, get_store: Callable[[], RecordingStore]
    ) -> None:
        self._target = target
        self._name = name
        self._get_store = get_store

    def _record(self, method: str, bound: Any, args: tuple, kwargs: dict) -> Any:
        exc = None
        ret = None
        try:
            ret = bound(*args, **kwargs)
        except Exception as e:
            exc = e
        # make_event may raise RuntimeError for unpicklable exceptions (FIN-1).
        event = make_event(method, args, kwargs, ret, exc)
        self._get_store().append(self._name, event)
        if exc is not None:
            raise exc
        return ret

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._record("__call__", self._target, args, kwargs)

    def __getattr__(self, item: str) -> Any:
        attr = getattr(self._target, item)
        if not callable(attr):
            msg = (
                f"recorder: attribute '{item}' on '{self._name}' is not callable; "
                "only method calls are recorded (pure-function assumption)"
            )
            raise AttributeError(msg)

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self._record(item, attr, args, kwargs)

        self.__dict__[item] = wrapper
        return wrapper


class PlayerProxy(_RecorderMock):
    """Replay recorded events in strict order; holds no real target."""

    def __init__(self, name: str, get_store: Callable[[], RecordingStore]) -> None:
        self._name = name
        self._get_store = get_store
        self._store: RecordingStore | None = None
        self._events: list[EncodedEvent] = []
        self._pos = 0
        self._maybe_reload()

    def _maybe_reload(self) -> None:
        # WHY: compare store identity not test_id — ProxyTracker.begin_test creates
        # a fresh RecordingStore per test, so reference change = test boundary.
        store = self._get_store()
        if store is self._store:
            return
        self._store = store
        self._events = list(store.events(self._name))
        self._pos = 0

    def _consume(self, method: str, args: tuple, kwargs: dict) -> Any:
        self._maybe_reload()
        if self._pos >= len(self._events):
            msg = f"recorder: '{self._name}.{method}' called but recording is exhausted"
            raise RecordingExhausted(msg)
        ev = self._events[self._pos]
        self._pos += 1
        # Match on ENCODED forms — decoded numpy/pandas raises "truth value ambiguous".
        live_args, live_kwargs = _encode_call(args, kwargs)
        expected = (ev.method, ev.args, ev.kwargs)
        actual = (method, live_args, live_kwargs)
        if expected != actual:
            exp_m, exp_a, exp_k = expected
            msg = (
                f"recorder: '{self._name}' call mismatch\n"
                f"  expected: {exp_m}(args={exp_a}, kwargs={exp_k})\n"
                f"  got:      {method}(args={live_args}, kwargs={live_kwargs})"
            )
            raise RecordingMismatch(msg)
        if ev.raised is not None:
            raise decode(ev.raised)
        return decode(ev.result)

    def assert_consumed(self) -> None:
        """Raise if the test used fewer recorded events than exist."""
        if self._pos != len(self._events):
            msg = (
                f"recorder: '{self._name}' used {self._pos} of "
                f"{len(self._events)} recorded calls"
            )
            raise RecordingUnderused(msg)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._consume("__call__", args, kwargs)

    def __getattr__(self, item: str) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self._consume(item, args, kwargs)

        self.__dict__[item] = wrapper
        return wrapper
