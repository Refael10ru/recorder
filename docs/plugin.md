# plugin.py

## Public API (used by decorator, targets)

```python
from pytest_recorder.plugin import get_controller   # decorator, targets
from pytest_recorder.plugin import Controller        # test code (direct use in tests)
```

| Symbol | Purpose |
|---|---|
| `get_controller() -> Controller` | Return the active session Controller; raises if unconfigured |
| `Controller` | Holds mode + per-test state; used directly in engine tests |

## Internals

### Controller

One global instance per test session, created by `pytest_configure`.

**State:**
- `mode` — `"off"` / `"record"` / `"play"` (set once; never changes)
- `_nodeid` — current test's nodeid (changes each test)
- `_test_file` — current test's file path
- `_store` — lazily-created `RecordingStore` for the current test
- `_players` — `PlayerProxy` instances registered this test

**`begin_test(nodeid, path)`** — called at `pytest_runtest_setup`. Resets all
per-test state; previous store and players are discarded.

**`current_store()`** — lazily creates (record) or loads (play) the
`RecordingStore` for the running test. Raises `MissingRecording` in play mode
if the `.json` file doesn't exist. Result cached in `_store` for the test.

**`register_player(player)`** — called by `PlayerProxy._maybe_reload` on each
test boundary. Tracked so `end_test` can assert full consumption.

**`end_test()`**:
- `record`: flushes `_store` to disk (if any events were buffered).
- `play`: calls `player.assert_consumed()` on every registered player.

### Pytest hooks

| Hook | Action |
|---|---|
| `pytest_addoption` | Registers `--recorder=off\|record\|play` |
| `pytest_configure` | Creates the global `Controller` from chosen mode |
| `pytest_runtest_setup` | `ctrl.begin_test(item.nodeid, item.path)` |
| `pytest_runtest_teardown` | `ctrl.end_test()` |

### get_controller()

Module-level accessor. Raises `RuntimeError` if called before `pytest_configure`
(i.e. outside a pytest run). Used by `decorator.py` and `targets.py` to reach
the active Controller without importing it as a global.
