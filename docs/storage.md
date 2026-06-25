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

### `RecordingStore(path)` — extends `StoreSource`

In-memory `{fixture_name: [event, ...]}` dict backed by a JSON file.

| Method | Mode | Purpose |
|---|---|---|
| `append(name, event)` | record | Buffer one event |
| `events(name) -> list[dict]` | play | Return buffered events; empty list if absent |
| `load()` | play | Read `.json` from disk into `_data` |
| `flush()` | record | Write `_data` to disk; creates parent dirs |
| `current_store()` | — | Returns `self` (StoreSource contract) |
| `test_id()` | — | Returns `self` (StoreSource contract) |
| `register_player(player)` | — | No-op (StoreSource contract) |

## Internals

### Recording file location

Recordings live in `recordings/` **beside the test module**, not at the project
root. This means they travel with the test when it is moved or copied. All
non-alphanumeric characters in the key become `_` for filesystem safety.

### StoreSource implementation

`RecordingStore` inherits `StoreSource` and implements all three abstract methods:

- `current_store()` returns `self` — a plain store is its own source.
- `test_id()` returns `self` — object identity is stable for the store's lifetime,
  so `PlayerProxy._last_test_id == self` on every call after the first → no
  spurious reloads.
- `register_player()` is a no-op — plain-store callers call
  `player.assert_consumed()` themselves after the test.
