# decorator.py

## Public API (used by __init__, test code)

```python
from pytest_recorder.decorator import record   # re-exported by __init__
from pytest_recorder import record             # user-facing import
```

| Symbol | Signature | Purpose |
|---|---|---|
| `record` | `(name: str \| None = None)` | Decorator factory for pytest fixtures |

## Internals

### record(name=None)

Turns a fixture factory into a recording/replay fixture. The inner `wrapper` is
a **generator fixture** (`yield`) — required because pytest generator fixtures
support teardown; a plain `return` fixture cannot.

**Behaviour by mode:**

| Mode | Real factory called? | Yields |
|---|---|---|
| `off` | Yes | real object |
| `record` | Yes | `RecordingProxy(real_obj, name, ctrl)` |
| `play` | No | `PlayerProxy(name, ctrl)` |

In play mode the real factory is not called — the point is to avoid hitting the
live system.

### Why pass ctrl, not ctrl.current_store()

Passing `ctrl` (the Controller) instead of `ctrl.current_store()` (a fixed
`RecordingStore`) means the proxy resolves the store lazily per call. This is
required for non-function-scope fixtures: a session-scoped fixture outlives many
tests, and each test must route its calls to its own recording file. Locking to a
store at fixture-creation time breaks this (SCP-1). See [`docs/engine.md`](engine.md).

`PlayerProxy` self-registers with the controller via `_maybe_reload` on each
test boundary, so no explicit `register_player` call is needed in the decorator.
