# interfaces.py

## Public API (used by storage, engine, plugin)

```python
from pytest_recorder.interfaces import StoreSource
```

| Symbol | Purpose |
|---|---|
| `StoreSource` | ABC that both `RecordingStore` and `Controller` inherit from |

## Internals

### Why this module exists

`engine.py` needs to accept both `RecordingStore` (direct test usage) and
`Controller` (fixture usage) without importing either. Before this module,
engine used a duck-typed `Protocol` and `getattr` probes to detect optional
behaviour. The ABC approach is explicit: both classes inherit `StoreSource` and
implement all three methods. See `CLAUDE.md` "Hard types — no duck typing".

Extracting the ABC to its own module breaks the circular import: engine cannot
import plugin (plugin already imports engine), but both can import `interfaces`.

### StoreSource ABC

Three abstract methods:

**`current_store() -> RecordingStore`**  
Return the `RecordingStore` for the currently running test.

**`test_id() -> object`**  
Return a value that changes whenever the active test changes. Proxies compare
successive return values to detect test-boundary crossings and reload events.
Must be stable within one test and distinct across tests.

- `RecordingStore.test_id()` returns `self` — identity never changes, so no
  reload after the first.
- `Controller.test_id()` returns `self._nodeid` — changes on `begin_test`,
  triggering reload + re-register.

**`register_player(player) -> None`**  
Register a `PlayerProxy` so its consumption can be verified at test end.

- `RecordingStore.register_player()` is a no-op — callers using a plain store
  call `player.assert_consumed()` themselves.
- `Controller.register_player()` appends to `_players` for teardown assertion.
