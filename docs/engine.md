# engine.py

## Public API (used by plugin, decorator, targets)

```python
from pytest_recorder.engine import RecordingProxy, PlayerProxy  # decorator, targets, plugin
from pytest_recorder.engine import _encode_call                 # targets only
```

| Symbol | Used by | Purpose |
|---|---|---|
| `RecordingProxy(target, name, source)` | decorator, targets | Wraps a real object; records every call |
| `PlayerProxy(name, source)` | plugin, decorator, targets | Replays recorded events in strict order |
| `_encode_call(args, kwargs)` | targets | Encode positional + keyword args to JSON-safe forms |

Note: `_encode_call` has an underscore prefix but is imported cross-module by
`targets.py`. Treat it as part of engine's internal API for now.

## Internals

### _StoreSource Protocol

Structural type for anything with `current_store() -> RecordingStore`. Satisfied
by both `RecordingStore` (via its `current_store()` shim) and `Controller`
(real implementation). Using a Protocol instead of an ABC avoids the circular
import that would arise if engine imported `Controller` from plugin.

### RecordingProxy

Wraps a real target. On every method call or `__call__`:

1. Calls the real method; captures return value or exception.
2. Serializes via `encode` / `encode_exception`.
3. Calls `source.current_store().append(name, event)`.
4. Re-raises the exception or returns the value unchanged.

Non-callable attribute access raises `AttributeError` immediately — only method
calls are recorded (pure-function assumption).

**Why hold `source`, not a fixed store (SCP-1):**  
Non-function-scope fixtures (session/module/class) create one proxy shared across
multiple tests. Locking to a store at construction time sends all N tests' calls
to the first test's recording file. Calling `source.current_store()` per call
routes each test to the correct file as `Controller._nodeid` changes.

### PlayerProxy

Replays events in strict order. Holds no real target.

On every call:

1. `_maybe_reload()` — detect test boundary; reload events if needed.
2. Verify next event matches `(method, encoded-args, encoded-kwargs)`.
3. Decode and return or re-raise.

`assert_consumed()` raises `RecordingUnderused` if fewer events were consumed
than exist in the recording.

**`_maybe_reload` sentinel logic:**  
`_last_nodeid` starts as `_INIT`. On each call, `getattr(source, '_nodeid', _UNSET)` is compared to `_last_nodeid`.

Two sentinels are required:

- `_UNSET`: returned by `getattr` when source is a plain `RecordingStore` (no `_nodeid`).
- `_INIT`: the initial value — must differ from `_UNSET`.

If only one sentinel existed and `_last_nodeid` started as `_UNSET`: on the
first call against a plain store, `getattr` would return `_UNSET` → equal → no
initial load → broken. `_INIT ≠ _UNSET` ensures the first `_maybe_reload` always
fires; then `_UNSET == _UNSET` on subsequent calls to a plain store prevents
spurious reloads. For a Controller source, `_nodeid` changes per test → reload +
re-register on each test boundary.

### make_event / _encode_call

`make_event` builds the serialized event dict:

```json
{"method": "add", "args": [2, 3], "kwargs": {}, "return": 5, "raised": null}
```

Exactly one of `"return"` / `"raised"` is non-null.
`_encode_call` runs args and kwargs through `serialize.encode` before storing.
