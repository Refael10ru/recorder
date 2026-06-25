# targets.py

## Public API (used by __init__, test code)

```python
from pytest_recorder.targets import record_class, record_function   # re-exported by __init__
from pytest_recorder import record_class, record_function           # user-facing import
```

| Symbol | Purpose |
|---|---|
| `record_class(*paths)` | Context manager / decorator; records method calls on constructed instances |
| `record_function(*paths)` | Context manager / decorator; records the call itself for plain callables |

Both accept one or more import paths as strings (e.g. `"mylib.api.Client"`).
Both work as context managers and as decorators.

## Internals

### record_class

On `__enter__`:

1. Calls `get_controller()`; short-circuits (no-op) if mode is `"off"`.
2. For each path: resolves module + attribute, replaces it with a shim, saves
   the original for restoration.

On `__exit__`: restores all originals in reverse order; on clean exit calls
`assert_consumed()` on every `PlayerProxy` created during the block.

**Shim behaviour:**

```
record mode → shim(*args) → RecordingProxy(original(*args), key, store)
play mode   → shim(*args) → PlayerProxy(key, store)
```

In record mode the **instance** is wrapped, not the class. Wrapping the class
via `__call__` would lose method recording on the returned object.

### record_function

Inherits `record_class`. Overrides two methods:

- `_make_replacement` — wraps the **callable itself**:
  - record: `RecordingProxy(original, key, store)(*args)` — records the call, returns real result.
  - play: `PlayerProxy(key, store)(*args)` — consumes one `__call__` event, returns recorded value.
- `__call__` (decorator form) — re-enters `record_function`, not `record_class`.

Use `record_function` for module-level functions (e.g. `wikipedia.search`); use
`record_class` for classes/factories where method calls on the returned instance
also need to be captured.

### Key disambiguation

Each call to the same constructor/function with the same args gets a unique
stream key: `"path(encoded_args)#0"`, `"path(encoded_args)#1"`, etc. The per-
instance `_counters` dict resets each time the context manager is entered.

### _resolve(path)

Splits `"pkg.mod.Name"` at the last `.` and imports the module via `importlib`.
Returns `(module, attr_name)`.

### _base_key(path, args, kwargs)

Stable identifier for one construction: import path + JSON-encoded constructor
args. `_encode_call` (imported from engine) is used for the encoding.
