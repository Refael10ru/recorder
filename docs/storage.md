# storage.py

## Public API (used by engine, proxy_tracking)

```python
from pytest_recorder.storage import (
    EncodedEvent,
    RecordingStore,
    resolve_recording_path,
)
```

### `EncodedEvent` (dataclass, `slots=True`)

Shape of one recorded call, stored in JSON:

```python
@dataclasses.dataclass(slots=True)
class EncodedEvent:
    method: str            # "__call__" or method name
    args: list[Any]        # positional args, JSON-safe (pickle-fallback encoded)
    kwargs: dict[str, Any]
    result: Any            # exactly one of result/raised is non-None
    raised: Any
```

The field is named `result` (not `return`) because `return` is a Python keyword
and cannot be a dataclass field name; the JSON key on disk is `result` too.

### `resolve_recording_path(nodeid, test_file) -> Path`

Maps a pytest nodeid + test file path to a `.json` recording path.

```
nodeid:    "tests/mockproj/test_depth.py::test_flat_object"
test_file: Path("/proj/tests/mockproj/test_depth.py")
→          Path("/proj/tests/mockproj/recordings/test_depth__test_flat_object.json")
```

### `RecordingStore(path)`

In-memory `{stream_name: [EncodedEvent, ...]}` dict backed by a JSON file.
`ProxyTracker.begin_test` builds (record) or loads (play) one per test;
proxies reach it via their `get_store` callable.

| Method | Mode | Purpose |
|---|---|---|
| `append(name, event)` | record | Buffer one event |
| `events(name) -> list[EncodedEvent]` | play | Return buffered events; empty list if absent |
| `load()` | play | Read `.json` from disk into `EncodedEvent`s |
| `flush()` | record | Write buffered events to disk; creates parent dirs |

## Internals

### Recording file location

Recordings live in `recordings/` **beside the test module**, not at the project
root. This means they travel with the test when it is moved or copied. All
non-alphanumeric characters in the key become `_` for filesystem safety.

### History

`storage.py` once defined a `StoreSource` ABC that mixed boundary detection and
store access; it was removed in the storage refactor. Proxies now take a plain
`get_store` callable and detect test boundaries by store identity — see
[`engine.md`](engine.md).
