"""Record/replay engine: RecordingProxy and PlayerProxy over an explicit store."""

from typing import Any

from pytest_recorder.errors import (
    RecordingExhausted,
    RecordingMismatch,
    RecordingUnderused,
)
from pytest_recorder.interfaces import StoreSource
from pytest_recorder.serialize import decode, encode, encode_exception


def _encode_call(args, kwargs):
    """Encode a call's positional and keyword args to JSON-safe forms."""
    return [encode(a) for a in args], {k: encode(v) for k, v in kwargs.items()}


def make_event(method, args, kwargs, ret, exc):
    """Build a serialized event dict for one recorded call.

    Exactly one of ``return`` / ``raised`` is non-null.
    """
    enc_args, enc_kwargs = _encode_call(args, kwargs)
    if exc is not None:
        # FIN-1: encode_exception validates pickle round-trip; encode() would let
        # a bad pickle through silently, only failing at play time with TypeError.
        outcome = {"return": None, "raised": encode_exception(exc)}
    else:
        outcome = {"return": encode(ret), "raised": None}
    return {"method": method, "args": enc_args, "kwargs": enc_kwargs, **outcome}


class RecordingProxy:
    """Wrap a real target; record each call, then return/re-raise as normal."""

    def __init__(self, target: Any, name: str, source: StoreSource) -> None:
        self._target = target
        self._name = name
        # WHY: store source not store — source.current_store() per call means
        # non-function-scope fixtures route each test's calls to the right file
        # as the active test changes. Locking to a store at construction would
        # send all calls to the first test's recording (SCP-1 bug).
        self._source = source

    def _record(self, method: str, bound: Any, args: tuple, kwargs: dict) -> Any:
        exc = None
        ret = None
        try:
            ret = bound(*args, **kwargs)
        except Exception as e:
            exc = e
        self._source.current_store().append(
            self._name, make_event(method, args, kwargs, ret, exc)
        )
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

        # WHY: cache in __dict__ so repeated proxy.method lookups skip __getattr__.
        # Alt: functools.partial — rejected because _record takes (method, bound,
        # args, kwargs) not *args/**kwargs, so partial needs a calling-convention
        # change; __dict__ caching needs none.
        self.__dict__[item] = wrapper
        return wrapper


class PlayerProxy:
    """Replay recorded events in strict order; holds no real target."""

    def __init__(self, name: str, source: StoreSource) -> None:
        self._name = name
        # WHY: store source not store — same rationale as RecordingProxy.
        self._source = source
        # WHY: object() is unique per construction, never equal to any real
        # test_id() value, so _maybe_reload always fires on the first call.
        self._last_test_id: object = object()
        self._events: list[dict] = []
        self._pos = 0
        self._maybe_reload()

    def _maybe_reload(self) -> None:
        current = self._source.test_id()
        if current == self._last_test_id:
            return
        self._events = list(self._source.current_store().events(self._name))
        self._pos = 0
        self._last_test_id = current
        # WHY: no-op for RecordingStore; re-registers per test for Controller.
        self._source.register_player(self)

    def _consume(self, method: str, args: tuple, kwargs: dict) -> Any:
        self._maybe_reload()
        if self._pos >= len(self._events):
            msg = f"recorder: '{self._name}.{method}' called but recording is exhausted"
            raise RecordingExhausted(msg)
        ev = self._events[self._pos]
        self._pos += 1
        # Match on ENCODED forms, not decoded values: encoded args are JSON-safe
        # (scalars/strings/{"__pickle__": b64}), so equality never evaluates the
        # truthiness of a live numpy array / pandas object (which would raise
        # "truth value is ambiguous"). The event already stores encoded args.
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

        # WHY: same rationale as RecordingProxy.__getattr__ — cache to avoid a new
        # closure per access. Safe because _consume calls _maybe_reload on each call,
        # so the cached wrapper still picks up test-boundary reloads correctly.
        self.__dict__[item] = wrapper
        return wrapper
