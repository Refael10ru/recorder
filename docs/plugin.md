# plugin.py — Controller and pytest hooks

Imports: `engine`, `errors`, `storage`.

## Controller

One global instance per test session, created by `pytest_configure`.

Holds:
- `mode` — `"off"` / `"record"` / `"play"`
- Per-test state: `_nodeid`, `_test_file`, `_store`, `_players`

### begin_test(nodeid, path)

Called at `pytest_runtest_setup`. Resets per-test state; the old store and player
list are discarded.

### current_store()

Lazily creates (record) or loads (play) a `RecordingStore` for the current test.
Raises `MissingRecording` in play mode if the `.json` file doesn't exist.
Result is cached in `_store` for the duration of the test.

### register_player(player)

Called by `PlayerProxy._maybe_reload` when a player detects a test boundary.
Tracks players so `end_test` can assert full consumption.

### end_test()

- `record`: flushes `_store` to disk (if any events were captured).
- `play`: calls `assert_consumed()` on every registered player.

## Pytest hooks

| Hook | Action |
|---|---|
| `pytest_addoption` | Registers `--recorder=off\|record\|play` |
| `pytest_configure` | Creates the global `Controller` |
| `pytest_runtest_setup` | Calls `ctrl.begin_test(item.nodeid, item.path)` |
| `pytest_runtest_teardown` | Calls `ctrl.end_test()` |

## get_controller()

Module-level accessor used by `decorator.py` and `targets.py`. Raises
`RuntimeError` if called before `pytest_configure` (i.e. outside a pytest run).
