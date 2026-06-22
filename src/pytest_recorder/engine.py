"""Record/replay engine: RecordingProxy and PlayerProxy over an explicit store."""

from pytest_recorder.errors import (
    RecordingExhausted,
    RecordingMismatch,
    RecordingUnderused,
)
from pytest_recorder.serialize import decode, encode


def _encode_call(args, kwargs):
    """Encode a call's positional and keyword args to JSON-safe forms."""
    return [encode(a) for a in args], {k: encode(v) for k, v in kwargs.items()}


def make_event(method, args, kwargs, ret, exc):
    """Build a serialized event dict for one recorded call.

    Exactly one of ``return`` / ``raised`` is non-null.
    """
    enc_args, enc_kwargs = _encode_call(args, kwargs)
    if exc is not None:
        outcome = {"return": None, "raised": encode(exc)}
    else:
        outcome = {"return": encode(ret), "raised": None}
    return {"method": method, "args": enc_args, "kwargs": enc_kwargs, **outcome}


def is_recorder_mock(obj: object) -> bool:
    """Return True if *obj* is a RecordingProxy or PlayerProxy, False otherwise."""
    fn = getattr(obj, "__is_recorder_mock__", None)
    return callable(fn) and fn()


class _RecorderMock:
    def __is_recorder_mock__(self) -> bool:
        return True


class RecordingProxy(_RecorderMock):
    """Wrap a real target; record each call, then return/re-raise as normal."""

    def __init__(self, target, name, store):
        self._target = target
        self._name = name
        self._store = store

    def _record(self, method, bound, args, kwargs):
        exc = None
        ret = None
        try:
            ret = bound(*args, **kwargs)
        except Exception as e:
            exc = e
        self._store.append(self._name, make_event(method, args, kwargs, ret, exc))
        if exc is not None:
            raise exc
        return ret

    def __call__(self, *args, **kwargs):
        return self._record("__call__", self._target, args, kwargs)

    def __getattr__(self, item):
        attr = getattr(self._target, item)
        if not callable(attr):
            msg = (
                f"recorder: attribute '{item}' on '{self._name}' is not callable; "
                "only method calls are recorded (pure-function assumption)"
            )
            raise AttributeError(msg)

        def wrapper(*args, **kwargs):
            return self._record(item, attr, args, kwargs)

        return wrapper


class PlayerProxy(_RecorderMock):
    """Replay recorded events in strict order; holds no real target."""

    def __init__(self, name, store):
        self._name = name
        self._events = list(store.events(name))
        self._pos = 0

    def _consume(self, method, args, kwargs):
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

    def assert_consumed(self):
        """Raise if the test used fewer recorded events than exist."""
        if self._pos != len(self._events):
            msg = (
                f"recorder: '{self._name}' used {self._pos} of "
                f"{len(self._events)} recorded calls"
            )
            raise RecordingUnderused(msg)

    def __call__(self, *args, **kwargs):
        return self._consume("__call__", args, kwargs)

    def __getattr__(self, item):
        def wrapper(*args, **kwargs):
            return self._consume(item, args, kwargs)

        return wrapper
