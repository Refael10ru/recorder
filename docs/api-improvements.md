# Planned API improvements

Items identified during code review. Each should become its own PR in a future
simplification cycle.

---

## 1. Remove `current_store()` shim from RecordingStore

**Current:** `RecordingStore.current_store()` returns `self` purely to satisfy
the `_StoreSource` Protocol / `StoreSource` ABC without importing engine.

**Problem:** A method whose only implementation is `return self` is noise; it
exists for structural compatibility, not for domain logic. Anyone reading
`RecordingStore` has to understand why this no-op exists.

**Direction:** Once the ABC contract is fully settled, explore whether
`current_store()` can be removed from `RecordingStore`'s public surface, or
whether it can be renamed to something that makes the structural role
self-evident (e.g. `as_store_source()`).

---

## 2. Add `EncodedRecording` dataclass for the event dict

**Current:** Events are stored as untyped `dict` throughout:

```python
_data: dict[str, list[dict]]
append(name: str, event: dict)
events(name: str) -> list[dict]
```

The actual shape is:
```python
{"method": str, "args": list, "kwargs": dict, "return": object | None, "raised": object | None}
```

but nothing enforces this at the type level.

**Direction:** Introduce a typed `EncodedEvent` (TypedDict or dataclass) that
captures the shape. `RecordingStore` would then export `list[EncodedEvent]`
instead of `list[dict]`. `engine.make_event` would produce an `EncodedEvent`.

**Note:** `"return"` is a Python keyword, so a TypedDict needs functional syntax:
```python
EncodedEvent = TypedDict("EncodedEvent", {
    "method": str,
    "args": list[object],
    "kwargs": dict[str, object],
    "return": object | None,
    "raised": object | None,
})
```

The definition should live in `storage.py` (closest to where events are stored)
or a shared types module if more types accumulate.

---

## 3. Make storage.py fully independent (no recorder imports)

**Current:** `storage.py` imports `StoreSource` from `interfaces.py`:

```python
from pytest_recorder.interfaces import StoreSource
```

This means storage — intended to be the lowest layer — depends on interfaces,
which in turn has TYPE_CHECKING imports back to storage and engine, creating a
conceptual cycle even if not a runtime one.

**Direction:** Storage should have zero recorder imports. Options:

- Move `StoreSource` into `storage.py` directly (engine and plugin import it
  from storage). Storage is already the natural home — it defines `RecordingStore`,
  which is what `StoreSource` abstracts.
- Or keep `interfaces.py` but remove storage's inheritance from it; use
  `register()` / duck typing at plugin level instead.

The preferred direction is to move the ABC into storage so the dependency arrow
is: `engine/plugin → storage` (clean, bottom-up) rather than
`storage → interfaces ← engine/plugin` (sideways).

---

## 4. Move `_encode_call` out of engine's public surface

**Current:** `targets.py` imports `_encode_call` from `engine.py` (underscore-
prefixed but used cross-module) to compute stable stream keys:

```python
enc_args, enc_kwargs = _encode_call(args, kwargs)
sig = json.dumps([enc_args, enc_kwargs], sort_keys=True)
```

`_encode_call` is just `serialize.encode` applied to each arg:
```python
def _encode_call(args, kwargs):
    return [encode(a) for a in args], {k: encode(v) for k, v in kwargs.items()}
```

**Problem:** An underscore-prefixed internal helper leaks across the module
boundary. Targets could call `serialize.encode` directly and do the list/dict
mapping itself.

**Direction:** Move `_encode_call` to `serialize.py` (or inline it in targets)
and remove the cross-module import. Either way, engine's public surface becomes
`RecordingProxy` and `PlayerProxy` only.
