# targets.py — record_class / record_function

Imports: `engine`, `plugin`, `storage`.

## record_class

Context manager and decorator. On `__enter__`:

1. Calls `get_controller()` and short-circuits if mode is `"off"`.
2. For each import path (e.g. `"mylib.api.Client"`):
   - Resolves the module and attribute via `_resolve`.
   - Replaces the attribute with a shim (see below).
   - Saves the original for restoration in `__exit__`.

On `__exit__`: restores all originals in reverse order; if no exception, calls
`assert_consumed()` on every `PlayerProxy` that was created.

### Shim behaviour (record_class._make_replacement)

```
record mode → shim(*args) returns RecordingProxy(original(*args), key, store)
play mode   → shim(*args) returns PlayerProxy(key, store)
```

In record mode the **instance** is wrapped (not the class). Wrapping the class
via `__call__` would lose method recording.

### Key disambiguation (_next_key)

Each call to the same constructor with the same args gets a unique stream key:
`"path(encoded_args)#0"`, `"path(encoded_args)#1"`, etc. The counter is
per-instance and resets each time the context manager is entered.

## record_function

Inherits from `record_class`. Overrides:

- `_make_replacement` — wraps the **callable itself** (not the return value):
  - record: `RecordingProxy(original, key, store)(*args)` — records the call and returns the real result.
  - play: `PlayerProxy(key, store)(*args)` — consumes one `__call__` event and returns the recorded value.
- `__call__` (decorator form) — re-enters `record_function`, not `record_class`.

Use `record_function` for module-level functions like `wikipedia.search`; use
`record_class` for classes/factories where method calls on the returned instance
need to be captured.

## _resolve(path)

Splits `"pkg.mod.Name"` at the last `.` and imports the module. Returns
`(module, attr_name)`. Standard importlib; no caching.

## _base_key(path, args, kwargs)

Stable identifier for one construction: the import path plus the JSON-encoded
constructor args. Used as the base for `_next_key` before the `#N` suffix.
