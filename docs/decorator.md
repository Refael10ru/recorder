# decorator.py — @record fixture decorator

Imports: `engine`, `plugin`.

## record(name=None)

A decorator factory that turns a regular fixture factory into a
recording/replay fixture.

```python
@pytest.fixture
@record("pricing")
def pricing():
    return PricingClient()
```

The inner `wrapper` is a **generator fixture** (`yield`). This is required
because pytest generator fixtures support teardown; a plain `return` fixture
cannot. The decorator works for any fixture scope.

### Behaviour by mode

| Mode | Real factory called? | Yields |
|---|---|---|
| `off` | Yes | real object |
| `record` | Yes | `RecordingProxy(real_obj, name, ctrl)` |
| `play` | **No** | `PlayerProxy(name, ctrl)` |

In play mode the real factory is intentionally not called — the whole point is
to avoid hitting the live system.

### Why pass ctrl, not ctrl.current_store()

Passing `ctrl` (the `Controller`) instead of `ctrl.current_store()` (a fixed
`RecordingStore`) means the proxy calls `current_store()` lazily on every
method invocation. This is required for non-function-scope fixtures: a
session-scoped fixture outlives many tests, and each test must route its calls
to its own recording file. Locking to a store at fixture-creation time would
break this. See [`docs/engine.md`](engine.md) (SCP-1).
