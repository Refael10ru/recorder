# engine.py — Record/replay proxies

Imports: `errors`, `serialize`, `storage`.

## _StoreSource Protocol

Structural type for anything with `current_store() → RecordingStore`. Satisfied
by both `RecordingStore` (via its shim) and `Controller` (real impl). Using a
Protocol instead of an ABC avoids the circular import that would arise if engine
imported `Controller` from plugin.

## RecordingProxy

Wraps a real target object. On every method call or `__call__`:

1. Calls the real method and captures the return value or exception.
2. Serializes via `encode` / `encode_exception`.
3. Calls `source.current_store().append(name, event)`.
4. Re-raises the exception or returns the value unchanged.

**Why hold `source`, not a fixed store?**  
Non-function-scope fixtures (session/module/class) create one proxy shared across
multiple tests. If the proxy locked to a store at construction time, all N tests'
calls would land in the first test's recording file. Calling
`source.current_store()` on each call routes each test to its own file as the
Controller's `_nodeid` changes between tests. (SCP-1)

**Non-callable attributes** raise `AttributeError` immediately — only method
calls are recorded (pure-function assumption).

## PlayerProxy

Replays recorded events in strict order. Holds no real target.

On every call:

1. `_maybe_reload()` — detect test boundary; reload events if needed.
2. Verify next event matches `(method, encoded-args, encoded-kwargs)`.
3. Decode and return the value or re-raise the exception.

`assert_consumed()` raises `RecordingUnderused` if the test consumed fewer
events than exist in the recording.

### _maybe_reload sentinel logic

`_last_nodeid` starts as `_INIT`. On each call, `getattr(source, '_nodeid', _UNSET)` is compared to `_last_nodeid`.

Two sentinels are needed:

- `_UNSET`: returned by `getattr` when `source` is a plain `RecordingStore` (no `_nodeid` attribute).
- `_INIT`: the initial value — must differ from `_UNSET`.

If only one sentinel existed and `_last_nodeid` started as `_UNSET`: on the
first call against a plain store, `getattr` returns `_UNSET` → equal → no
initial load → broken. `_INIT ≠ _UNSET` guarantees the first `_maybe_reload`
always fires, then `_UNSET == _UNSET` on subsequent calls to a plain store
prevents spurious reloads.

For a Controller source, `_nodeid` changes per test → reload + re-register each
time the test boundary is crossed.

## make_event / _encode_call

`make_event` builds the serialized event dict stored in the recording:

```json
{
  "method": "add",
  "args": [2, 3],
  "kwargs": {},
  "return": 5,
  "raised": null
}
```

Exactly one of `"return"` / `"raised"` is non-null. `_encode_call` encodes
positional and keyword args through `serialize.encode` before storing.
