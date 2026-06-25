# storage.py — Path resolution and event buffer

No recorder dependencies.

## resolve_recording_path

Pure function. Maps a pytest nodeid + test file path to a `.json` path inside a
`recordings/` directory next to the test module.

```
nodeid:    tests/mockproj/test_depth.py::test_flat_object
test_file: /proj/tests/mockproj/test_depth.py
→          /proj/tests/mockproj/recordings/test_depth__test_flat_object.json
```

All non-alphanumeric characters in the key become `_` so the filename is always
filesystem-safe. The `recordings/` dir is next to the test file (not a project
root dir) so recordings travel with the test when it's moved.

## RecordingStore

In-memory `{fixture_name: [event, ...]}` dict backed by a JSON file.

- `append(name, event)` — buffer one event (record mode).
- `events(name)` — return buffered events; empty list if name not found.
- `load()` — read from disk into `_data`.
- `flush()` — write `_data` to disk; creates parent dirs if needed.

### current_store() shim

`current_store()` returns `self`. It exists solely so `RecordingStore` satisfies
the `_StoreSource` Protocol defined in `engine.py` without needing to import the
engine. Both `RecordingStore` and `Controller` expose `current_store()`; engine
code calls it on whichever it holds without an `isinstance` branch.

Why not `isinstance`? Engine importing `Controller` from plugin would create a
circular import (`engine → plugin → engine`). The Protocol + shim pattern avoids
this entirely.
