# decorator.py

## Public API (used by __init__, test code)

```python
from pytest_recorder.decorator import record   # re-exported by __init__
from pytest_recorder import record             # user-facing import
```

| Symbol | Signature | Purpose |
|---|---|---|
| `record` | `(name: str \| Callable \| None = None)` | Decorator factory for pytest fixtures; also usable bare (`@record`) |

## Internals

### record(name=None)

Turns a fixture factory into a recording/replay fixture. The inner `wrapper` is
a **generator fixture** (`yield`) — required because pytest generator fixtures
support teardown; a plain `return` fixture cannot.

`name` defaults to the decorated function's `__name__`. Bare `@record` (no
parentheses) is detected by `callable(name)`: the sole argument is then the
factory itself, not a name.

**Behaviour by mode:**

| Mode | Real factory called? | Yields |
|---|---|---|
| `off` | Yes | real object |
| `record` | Yes | `RecordingProxy(real_obj, name, tracker.current_store)` |
| `play` | No | `PlayerProxy(name, tracker.current_store)` (registered on the tracker) |

In play mode the real factory is not called — the point is to avoid hitting the
live system.

### Why pass `tracker.current_store`, not a store

The proxies receive the **bound method** `tracker.current_store` (a
`Callable[[], RecordingStore]`), not a fixed `RecordingStore`. The proxy
resolves the store lazily per call. This is required for non-function-scope
fixtures: a session-scoped fixture outlives many tests, and each test must
route its calls to its own recording file. Locking to a store at
fixture-creation time breaks this (SCP-1). See [`docs/engine.md`](engine.md).
