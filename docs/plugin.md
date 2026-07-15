# plugin.py

Thin pytest adapter: registers the `--recorder` option and wires the test
lifecycle hooks to the session-global [`ProxyTracker`](proxy_tracking.md). No
recorder logic of its own.

## Pytest hooks

| Hook | Action |
|---|---|
| `pytest_addoption` | Registers `--recorder=off\|record\|play` (default `off`) |
| `pytest_configure` | Creates the global `ProxyTracker` via `_set_tracker(ProxyTracker(RecorderMode(...)))` |
| `pytest_runtest_setup` | `get_tracker().begin_test(item.nodeid, item.path)` |
| `pytest_runtest_teardown` | `get_tracker().end_test()` |

The tracker itself (mode, per-test store, player registry, `get_tracker()`
accessor) lives in `proxy_tracking.py` — see
[`proxy_tracking.md`](proxy_tracking.md).
