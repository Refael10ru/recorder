"""Record/replay engine: RecordingProxy and PlayerProxy over an explicit store."""

from pytest_recorder.serialize import encode


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
