# storage.py

## Public API (used by engine, plugin, targets)

```python
from pytest_recorder.storage import (
    EncodedEvent,
    RecordingStore,
    StoreSource,
    resolve_recording_path,
)
```

### `EncodedEvent` (TypedDict)

Shape of one recorded call, stored in JSON:

```python
{
    "method":  str,           # "__call__" or method name
    "args":    list[Any],     # positional args, JSON-safe (pickle-fallback encoded)
    "kwargs":  dict[str, Any],
    "return":  Any | None,    # exactly one of return/raised is non-null
    "raised":  Any | None,
}
```

Uses TypedDict functional syntax because `"return"` is a Python keyword and
cannot be a dataclass field name without renaming the JSON key on disk.

### `StoreSource` (ABC)

Contract that proxies (`RecordingProxy`, `PlayerProxy`) depend on to get the
per-test store and detect test boundaries. Implemented by `Controller` (plugin)
and `RecordingStore` (direct use in tests).

```python
source.current_store() -> RecordingStore  # store for the running test
source.test_id() -> str                   # changes when the test changes
source.register_player(player)            # track for end-of-test assertion
```

See *Design note* below.

### `resolve_recording_path(nodeid, test_file) -> Path`

Maps a pytest nodeid + test file path to a `.json` recording path.

```
nodeid:    "tests/mockproj/test_depth.py::test_flat_object"
test_file: Path("/proj/tests/mockproj/test_depth.py")
→          Path("/proj/tests/mockproj/recordings/test_depth__test_flat_object.json")
```

### `RecordingStore(path)`

In-memory `{fixture_name: [EncodedEvent, ...]}` dict backed by a JSON file.
Also implements `StoreSource` so it can be passed directly to proxies in tests
(without a full `Controller`).

| Method | Mode | Purpose |
|---|---|---|
| `append(name, event)` | record | Buffer one event |
| `events(name) -> list[EncodedEvent]` | play | Return buffered events; empty list if absent |
| `load()` | play | Read `.json` from disk into `_data` |
| `flush()` | record | Write `_data` to disk; creates parent dirs |

## Internals

### Recording file location

Recordings live in `recordings/` **beside the test module**, not at the project
root. This means they travel with the test when it is moved or copied. All
non-alphanumeric characters in the key become `_` for filesystem safety.

### StoreSource — design note

`StoreSource` currently mixes two concerns:

1. **Boundary detection** — `test_id()` returns an opaque string that proxies
   compare across calls to detect when the test changed and events should be
   reloaded. Not used for file paths.
2. **Store access** — `current_store()` and `register_player()` are called per
   method call on a proxy.

`RecordingStore` implements both because it extends the ABC, but `current_store()`
(returns `self`) and `register_player()` (no-op) are noise — they exist only for
structural compatibility. A future PR will split the ABC into two protocols so
`RecordingStore` is only the thing *returned by* `current_store()`, not a
`StoreSource` itself. See `api-improvements.md` item 5.
