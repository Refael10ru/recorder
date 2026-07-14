# proxy_tracking.py

## Public API (used by __init__, plugin, test code)

```python
from pytest_recorder.proxy_tracking import record_class, record_function  # re-exported by __init__
from pytest_recorder import record_class, record_function                 # user-facing import
from pytest_recorder.proxy_tracking import ProxyTracker, RecorderMode, get_tracker
```

| Symbol | Purpose |
|---|---|
| `record_class(*paths)` | Context manager / decorator; records method calls on constructed instances |
| `record_function(*paths)` | Context manager / decorator; records the call itself for plain callables |
| `ProxyTracker` | Session-global lifecycle: mode, per-test store, player registry |
| `RecorderMode` | `StrEnum`: `OFF` / `RECORD` / `PLAY` |
| `get_tracker()` | Return the active tracker; raises if the plugin is unconfigured |

Both `record_class` and `record_function` accept one or more import paths as
strings (e.g. `"mylib.api.Client"`) and work as context managers and decorators.

## Internals

### ProxyTracker

One instance per session, created by `pytest_configure` via `_set_tracker`.

- **`begin_test(nodeid, test_file)`** — called at `pytest_runtest_setup`.
  Resets the player list and eagerly builds (record) or loads (play) the
  `RecordingStore` for this test; raises `MissingRecording` in play mode when
  the `.json` file doesn't exist. In `off` mode the store stays `None`.
- **`current_store()`** — trivial getter for the store `begin_test` built;
  raises outside a running test. Passed (bound, uncalled) to proxies as their
  `get_store` callable.
- **`register_player(player)`** — track a player for the end-of-test assert.
- **`end_test()`** — called at `pytest_runtest_teardown`: flush the store
  (record) or `assert_consumed()` on every registered player (play). Asserting
  here — not at block `__exit__` — keeps fixture teardown calls inside the
  recording window.

### record_class

On `__enter__`:

1. Calls `get_tracker()`; short-circuits (no-op) if mode is `OFF`.
2. For each path: resolves module + attribute, replaces it with a
   `ctor_proxy`, saves the original for restoration.

On `__exit__`: restores all originals in reverse order (player consumption is
asserted later, at `ProxyTracker.end_test`).

**ctor_proxy behaviour:**

```
record mode → ctor_proxy(*args) → RecordingProxy(original(*args), key, tracker.current_store)
play mode   → ctor_proxy(*args) → PlayerProxy(key, tracker.current_store)   # registered
```

In record mode the **instance** is wrapped, not the class. Wrapping the class
via `__call__` would lose method recording on the returned object.

### record_function

Inherits `record_class`. Overrides two methods:

- `_make_replacement` — the proxy **is** the replacement (no ctor_proxy):
  - record: `RecordingProxy(original, path, tracker.current_store)` — calling it records the call, returns the real result.
  - play: `PlayerProxy(path, tracker.current_store)` — calling it consumes one `__call__` event, returns the recorded value.
  Mode is decided at patch time, not per call. The stream key is the bare
  `path` (human-readable), with no encoded call args.
- `__call__` (decorator form) — re-enters `record_function`, not `record_class`.

Use `record_function` for module-level functions (e.g. `wikipedia.search`); use
`record_class` for classes/factories where method calls on the returned instance
also need to be captured.

### Key disambiguation (record_class)

Each construction with the same path + args gets a unique stream key:
`"path(encoded_args)#0"`, `"path(encoded_args)#1"`, etc. The per-instance
`_counters` dict resets each time the context manager is entered.

### _resolve(path)

Splits `"pkg.mod.Name"` at the last `.` and imports the module via `importlib`.
Returns `(module, attr_name)`.

### _base_key(path, args, kwargs)

Stable identifier for one construction: import path + JSON-encoded constructor
args (`_encode_call` from serialize). Note: raw constructor args — including
secrets — land in this key; see [`known-issues.md`](known-issues.md) #2.
