# storage.py

## Public API (used by engine, plugin, targets)

```python
from pytest_recorder.storage import resolve_recording_path, RecordingStore
```

### `resolve_recording_path(nodeid, test_file) -> Path`

Maps a pytest nodeid + test file path to a `.json` recording path.

```
nodeid:    "tests/mockproj/test_depth.py::test_flat_object"
test_file: Path("/proj/tests/mockproj/test_depth.py")
→          Path("/proj/tests/mockproj/recordings/test_depth__test_flat_object.json")
```

### `RecordingStore(path)`

In-memory `{fixture_name: [event, ...]}` dict backed by a JSON file.

| Method | Mode | Purpose |
|---|---|---|
| `append(name, event)` | record | Buffer one event |
| `events(name) -> list[dict]` | play | Return buffered events; empty list if absent |
| `load()` | play | Read `.json` from disk into `_data` |
| `flush()` | record | Write `_data` to disk; creates parent dirs |
| `current_store() -> RecordingStore` | both | Returns `self` (see internals) |

## Internals

### Recording file location

Recordings live in `recordings/` **beside the test module**, not at the project
root. This means they travel with the test when it is moved or copied. All
non-alphanumeric characters in the key become `_` for filesystem safety.

### current_store() shim

`current_store()` returns `self`. It exists so `RecordingStore` satisfies the
`_StoreSource` Protocol defined in `engine.py` without importing the engine.
Both `RecordingStore` and `Controller` expose `current_store()`; engine proxies
call it on whichever they hold without an `isinstance` branch.

Why not `isinstance`? Engine importing `Controller` from plugin would create a
circular import (`engine → plugin → engine`). The Protocol + shim avoids this.
