# engine.py

## Public API (used by plugin, decorator, targets)

```python
from pytest_recorder.engine import RecordingProxy, PlayerProxy   # decorator, targets, plugin
from pytest_recorder.engine import _encode_call                  # targets only
```

| Symbol | Used by | Purpose |
|---|---|---|
| `RecordingProxy(target, name, source)` | decorator, targets | Wraps a real object; records every call |
| `PlayerProxy(name, source)` | plugin, decorator, targets | Replays recorded events in strict order |
| `_encode_call(args, kwargs)` | targets | Encode positional + keyword args to JSON-safe forms |

Note: `_encode_call` has an underscore prefix but is imported cross-module by
`targets.py`. It is part of engine's de-facto interface for that layer.

## Internals

### RecordingProxy

Wraps a real target. On every method call or `__call__`:

1. Calls the real method; captures return value or exception.
2. Serializes via `encode` / `encode_exception`.
3. Calls `source.current_store().append(name, event)`.
4. Re-raises the exception or returns the value unchanged.

Non-callable attribute access raises `AttributeError` immediately — only method
calls are recorded (pure-function assumption).

`__getattr__` caches the generated wrapper in `self.__dict__[item]` so repeated
attribute lookups on the same proxy skip `__getattr__` entirely after the first
access. `functools.partial` was rejected as an alternative because `_record`'s
signature `(method, bound, args, kwargs)` would require a calling-convention
change to fit `partial`.

**Why hold `source`, not a fixed store (SCP-1):**  
Non-function-scope fixtures (session/module/class) share one proxy across
multiple tests. Locking to a store at construction sends all N tests' calls to
the first test's recording file. Calling `source.current_store()` per call
routes each test to the correct file as `Controller._nodeid` changes between
tests.

### PlayerProxy

Replays events in strict order. Holds no real target.

On every call:

1. `_maybe_reload()` — detect test boundary; reload events if needed.
2. Verify next event matches `(method, encoded-args, encoded-kwargs)`.
3. Decode and return or re-raise.

`assert_consumed()` raises `RecordingUnderused` if fewer events were consumed
than exist in the recording.

`__getattr__` caching: same rationale as `RecordingProxy`. The cached wrapper
still detects test-boundary crossings correctly because every call goes through
`_consume`, which calls `_maybe_reload`.

**`_maybe_reload` sentinel:**  
`_last_test_id` starts as a fresh `object()` instance — unique, never equal to
any real `test_id()` return value, so `_maybe_reload` always fires on the first
call. After that, equality is governed by whatever `source.test_id()` returns:

- Plain `RecordingStore`: `test_id()` returns `self` — identity is stable →
  no further reloads.
- `Controller`: `test_id()` returns `_nodeid` — changes on `begin_test` →
  reload + re-register each time the test boundary is crossed.

### make_event / _encode_call

`make_event` builds the serialized event dict:

```json
{"method": "add", "args": [2, 3], "kwargs": {}, "return": 5, "raised": null}
```

Exactly one of `"return"` / `"raised"` is non-null.
`_encode_call` runs args and kwargs through `serialize.encode` before storing.
