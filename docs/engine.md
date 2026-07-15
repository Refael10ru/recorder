# engine.py

## Public API (used by plugin, decorator, proxy_tracking)

```python
from pytest_recorder.engine import RecordingProxy, PlayerProxy, is_recorder_mock, make_event
```

| Symbol | Used by | Purpose |
|---|---|---|
| `RecordingProxy(target, name, get_store)` | decorator, proxy_tracking | Wraps a real object; records every call |
| `PlayerProxy(name, get_store)` | decorator, proxy_tracking | Replays recorded events in strict order |
| `is_recorder_mock(obj)` | test code | `True` for either proxy, `False` for anything else |
| `make_event(method, args, kwargs, ret, exc)` | internal | Build one serialized `EncodedEvent` |

Both proxies take `get_store: Callable[[], RecordingStore]` — usually the bound
method `ProxyTracker.current_store` — and resolve the store lazily per call.

## Internals

### RecordingProxy

Wraps a real target. On every method call or `__call__`:

1. Calls the real method; captures return value or exception.
2. Serializes via `make_event` (`encode` / `encode_exception`).
3. Calls `get_store().append(name, event)`.
4. Re-raises the exception or returns the value unchanged.

Non-callable attribute access raises `AttributeError` immediately — only method
calls are recorded (pure-function assumption).

**Why hold `get_store`, not a fixed store (SCP-1):**
Non-function-scope fixtures (session/module/class) create one proxy shared across
multiple tests. Locking to a store at construction time sends all N tests' calls
to the first test's recording file. Calling `get_store()` per call routes each
test to the store `ProxyTracker.begin_test` built for it.

### PlayerProxy

Replays events in strict order. Holds no real target.

On every call:

1. `_maybe_reload()` — detect test boundary; reload events if needed.
2. Verify next event matches `(method, encoded-args, encoded-kwargs)`.
3. Decode and return, or re-raise the decoded exception.

`assert_consumed()` raises `RecordingUnderused` if fewer events were consumed
than exist in the recording. `ProxyTracker.end_test` calls it on every
registered player.

**`_maybe_reload` boundary detection:**
`ProxyTracker.begin_test` builds a fresh `RecordingStore` per test, so the
player compares `get_store()` by **identity** with the store it last loaded
from. A new reference means a new test: reload events, reset position. Same
reference means same test: no-op.

**Why matching compares encoded forms:**
`_consume` encodes the live args (`_encode_call`) and compares them to the
event's stored encoded args. Comparing decoded values breaks on numpy/pandas
(`==` returns arrays / raises "truth value is ambiguous"); encoded forms are
plain JSON values, where `==` is always safe.

### make_event

Builds the serialized `EncodedEvent` (see [`storage.md`](storage.md)):

```json
{"method": "add", "args": [2, 3], "kwargs": {}, "result": 5, "raised": null}
```

Exactly one of `result` / `raised` is non-null. Exceptions go through
`encode_exception`, which validates the pickle round-trip at record time
(FIN-1 — see [`serialize.md`](serialize.md)).
