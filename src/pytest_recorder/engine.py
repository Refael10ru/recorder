"""Record/replay engine: RecordingProxy and PlayerProxy over an explicit store."""

from typing import Any, Protocol

from pytest_recorder.errors import (
    RecordingExhausted,
    RecordingMismatch,
    RecordingUnderused,
)
from pytest_recorder.serialize import decode, encode, encode_exception
from pytest_recorder.storage import RecordingStore

# WHY: _INIT sentinel marks "never loaded" — distinct from _UNSET (used when source
# has no _nodeid, i.e. a plain RecordingStore) so _maybe_reload triggers on first
# call regardless of source type. Two sentinels instead of one avoids the case where
# _last_nodeid == getattr(store, '_nodeid', _UNSET) at construction → no initial load.
_UNSET = object()
_INIT = object()


class _StoreSource(Protocol):
    """Duck-type contract shared by RecordingStore and Controller.

    WHY Protocol not ABC: engine must not import Controller (that creates a circular
    import via plugin → engine). Protocol lets mypy verify structural compatibility
    without a runtime dependency.
    """

    def current_store(self) -> RecordingStore: ...


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


def is_recorder_mock(obj: object) -> bool:
    """Return True if *obj* is a RecordingProxy or PlayerProxy, False otherwise."""
    fn = getattr(obj, "__is_recorder_mock__", None)
    return callable(fn) and fn()


class _RecorderMock:
    def __is_recorder_mock__(self) -> bool:
        return True


class RecordingProxy(_RecorderMock):
    """Wrap a real target; record each call, then return/re-raise as normal."""

    def __init__(self, target: Any, name: str, source: _StoreSource) -> None:
        self._target = target
        self._name = name
        # WHY: store the source (Controller or RecordingStore), not the store itself.
        # Calling source.current_store() per call means non-function-scoped fixtures
        # (session/module/class) automatically route each test's calls to the right
        # recording file as the Controller's current test changes between calls.
        # Alternative: lock to store at construction (old behaviour) — broken for any
        # scope wider than function: all calls land in the first test's recording.
        self._source = source

    def _record(self, method: str, bound: Any, args: tuple, kwargs: dict) -> Any:
        exc = None
        ret = None
        try:
            ret = bound(*args, **kwargs)
        except Exception as e:
            exc = e
        # WHY: .current_store() lookup per call — see __init__ comment.
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

        return wrapper


class PlayerProxy(_RecorderMock):
    """Replay recorded events in strict order; holds no real target."""

    def __init__(self, name: str, source: _StoreSource) -> None:
        self._name = name
        # WHY: same rationale as RecordingProxy — store the source, not the store, so
        # non-function-scope fixtures can reload events when the test changes.
        self._source = source
        self._last_nodeid: Any = _INIT  # _INIT != _UNSET → first _maybe_reload fires
        self._events: list[dict] = []
        self._pos = 0
        # WHY: eagerly load events and register for current test on construction
        self._maybe_reload()

    def _maybe_reload(self) -> None:
        # WHY: _nodeid is a Controller attribute; plain RecordingStore has none, so
        # getattr returns _UNSET. _UNSET != _INIT on first call → reload fires once.
        # Subsequent calls on a store → _UNSET == _UNSET → no reload (correct).
        # For Controller: nodeid changes per test → reload + re-register each time.
        current = getattr(self._source, "_nodeid", _UNSET)
        if current == self._last_nodeid:
            return
        self._events = list(self._source.current_store().events(self._name))
        self._pos = 0
        self._last_nodeid = current
        # WHY: re-register with the controller so assert_consumed is checked per test.
        # For plain RecordingStore, register_player doesn't exist → skip (caller must
        # call assert_consumed explicitly, as all existing direct-use tests do).
        register = getattr(self._source, "register_player", None)
        if register is not None:
            register(self)

    def _consume(self, method: str, args: tuple, kwargs: dict) -> Any:
        self._maybe_reload()  # WHY: cross test boundary before consuming if needed
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

        return wrapper
