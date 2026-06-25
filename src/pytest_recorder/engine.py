"""Record/replay engine: RecordingProxy and PlayerProxy over a StoreSource."""

from typing import Any

from pytest_recorder.errors import (
    RecordingExhausted,
    RecordingMismatch,
    RecordingUnderused,
)
from pytest_recorder.serialize import _encode_call, decode, encode, encode_exception
from pytest_recorder.storage import EncodedEvent, StoreSource


def make_event(
    method: str, args: tuple, kwargs: dict, ret: Any, exc: BaseException | None
) -> EncodedEvent:
    """Build a serialized EncodedEvent for one recorded call."""
    enc_args, enc_kwargs = _encode_call(args, kwargs)
    if exc is not None:
        # FIN-1: encode_exception validates pickle round-trip at record time.
        return {
            "method": method, "args": enc_args, "kwargs": enc_kwargs,
            "return": None, "raised": encode_exception(exc),
        }
    return {
        "method": method, "args": enc_args, "kwargs": enc_kwargs,
        "return": encode(ret), "raised": None,
    }


def is_recorder_mock(obj: object) -> bool:
    """Return True if *obj* is a RecordingProxy or PlayerProxy, False otherwise."""
    fn = getattr(obj, "__is_recorder_mock__", None)
    return bool(callable(fn) and fn())


class _RecorderMock:
    def __is_recorder_mock__(self) -> bool:
        return True


class RecordingProxy(_RecorderMock):
    """Wrap a real target; record each call, then return/re-raise as normal."""

    def __init__(self, target: Any, name: str, source: StoreSource) -> None:
        self._target = target
        self._name = name
        # WHY: hold source not a fixed store — source.current_store() per call
        # routes non-function-scope fixtures to the right test's file (SCP-1).
        self._source = source

    def _record(self, method: str, bound: Any, args: tuple, kwargs: dict) -> Any:
        exc = None
        ret = None
        try:
            ret = bound(*args, **kwargs)
        except Exception as e:
            exc = e
        # make_event may raise RuntimeError for unpicklable exceptions (FIN-1).
        event = make_event(method, args, kwargs, ret, exc)
        self._source.current_store().append(self._name, event)
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

    def __init__(self, name: str, source: StoreSource) -> None:
        self._name = name
        # WHY: hold source not a fixed store — same rationale as RecordingProxy.
        self._source = source
        # WHY: object() is unique per construction, never equal to any real
        # test_id() return, so _maybe_reload always fires on the first call.
        self._last_test_id: object = object()
        self._events: list[EncodedEvent] = []
        self._pos = 0
        self._maybe_reload()

    def _maybe_reload(self) -> None:
        current = self._source.test_id()
        if current == self._last_test_id:
            return
        self._events = list(self._source.current_store().events(self._name))
        self._pos = 0
        self._last_test_id = current
        self._source.register_player(self)

    def _consume(self, method: str, args: tuple, kwargs: dict) -> Any:
        self._maybe_reload()
        if self._pos >= len(self._events):
            msg = f"recorder: '{self._name}.{method}' called but recording is exhausted"
            raise RecordingExhausted(msg)
        ev = self._events[self._pos]
        self._pos += 1
        # Match on ENCODED forms — decoded numpy/pandas raises "truth value ambiguous".
        live_args, live_kwargs = _encode_call(args, kwargs)
        expected = (ev["method"], ev["args"], ev["kwargs"])
        actual = (method, live_args, live_kwargs)
        if expected != actual:
            exp_m, exp_a, exp_k = expected
            msg = (
                f"recorder: '{self._name}' call mismatch\n"
                f"  expected: {exp_m}(args={exp_a}, kwargs={exp_k})\n"
                f"  got:      {method}(args={live_args}, kwargs={live_kwargs})"
            )
            raise RecordingMismatch(msg)
        if ev["raised"] is not None:
            raise decode(ev["raised"])
        return decode(ev["return"])

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
