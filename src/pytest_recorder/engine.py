"""Record/replay engine: RecordingProxy and PlayerProxy over an explicit store."""

from pytest_recorder.errors import (
    RecordingExhausted,
    RecordingMismatch,
    RecordingUnderused,
)
from pytest_recorder.serialize import decode, encode


def make_event(method, args, kwargs, ret, exc):
    """Build a serialized event dict for one recorded call."""
    return {
        "method": method,
        "args": [encode(a) for a in args],
        "kwargs": {k: encode(v) for k, v in kwargs.items()},
        "return": None if exc is not None else encode(ret),
        "raised": encode(exc) if exc is not None else None,
    }


class RecordingProxy:
    """Wrap a real target; record each call, then return/re-raise as normal."""

    def __init__(self, target, name, store):
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_store", store)

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
        target = object.__getattribute__(self, "_target")
        attr = getattr(target, item)
        if not callable(attr):
            msg = (
                f"recorder: attribute '{item}' on '{self._name}' is not callable; "
                "only method calls are recorded (pure-function assumption)"
            )
            raise AttributeError(msg)

        def wrapper(*args, **kwargs):
            return self._record(item, attr, args, kwargs)

        return wrapper


class PlayerProxy:
    """Replay recorded events in strict order; holds no real target."""

    def __init__(self, name, store):
        object.__setattr__(self, "_name", name)
        object.__setattr__(self, "_events", list(store.events(name)))
        object.__setattr__(self, "_pos", 0)

    def _consume(self, method, args, kwargs):
        if self._pos >= len(self._events):
            msg = f"recorder: '{self._name}.{method}' called but recording is exhausted"
            raise RecordingExhausted(msg)
        ev = self._events[self._pos]
        object.__setattr__(self, "_pos", self._pos + 1)
        # Match on ENCODED forms, not decoded values: encoded args are JSON-safe
        # (scalars/strings/{"__pickle__": b64}), so equality never evaluates the
        # truthiness of a live numpy array / pandas object (which would raise
        # "truth value is ambiguous"). The event already stores encoded args.
        live_args = [encode(a) for a in args]
        live_kwargs = {k: encode(v) for k, v in kwargs.items()}
        if (
            ev["method"] != method
            or ev["args"] != live_args
            or ev["kwargs"] != live_kwargs
        ):
            exp_m, exp_a, exp_k = ev["method"], ev["args"], ev["kwargs"]
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
