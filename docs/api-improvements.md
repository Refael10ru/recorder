# Planned API improvements

Items identified during code review. Each should become its own PR.

Items 1–4 were the original plan; 5–6 emerged from the storage-refactor CR.

---

## ~~1. Remove `current_store()` shim from RecordingStore~~ *(done in proxy-tracking refactor)*

Done. `StoreSource` was removed outright (see item 5), so the shim methods on
`RecordingStore` are gone.

---

## ~~2. Add `EncodedEvent` TypedDict~~ *(done in storage-refactor)*

Implemented. `"return"` is a Python keyword so a dataclass is not viable —
dataclass field names must be valid Python identifiers. TypedDict's functional
syntax `TypedDict("EncodedEvent", {"return": ...})` is the only clean option
without renaming the JSON key on disk.

---

## ~~3. Make storage.py fully independent~~ *(done in storage-refactor)*

`StoreSource` ABC now lives in `storage.py`; engine and plugin import from
storage. storage imports nothing from recorder.

---

## ~~4. Move `_encode_call` to serialize.py~~ *(done in storage-refactor)*

Done. `engine.py`'s public surface is now `RecordingProxy`, `PlayerProxy`,
`is_recorder_mock`, `make_event`.

---

## ~~5. Split `StoreSource` ABC into two protocols~~ *(superseded: ABC removed)*

Resolved differently in the proxy-tracking refactor: instead of two protocols,
`StoreSource` was deleted. Proxies now take a plain
`get_store: Callable[[], RecordingStore]` and detect test boundaries by store
identity (`ProxyTracker.begin_test` builds a fresh store per test). The
original analysis kept below for context.

**Current:** `StoreSource` mixes two concerns in one ABC:
- `test_id()` — a test-boundary sensor, used only by proxies to detect when to
  reload events
- `current_store()` / `register_player()` — the outward store accessor, called
  per method call

**Problem:** `RecordingStore` has to implement `current_store()` (returns `self`)
and `register_player()` (no-op) purely to satisfy the ABC. These are noise.

**Direction:** Split into two protocols:
1. A boundary sensor (has `test_id()`), held by proxies for reload detection
2. A store accessor (has `current_store()` / `register_player()`), called per
   method call

With this split, `RecordingStore` would not extend either protocol — it is the
thing that gets returned by `current_store()`, not the thing that provides it.
`Controller` would implement both protocols. `_BlockSource` in targets.py would
disappear or simplify.

---

## ~~6. Redesign targets.py as its own isolated layer~~ *(done: proxy_tracking.py)*

Done in the proxy-tracking refactor: `targets.py` became `proxy_tracking.py`,
`_BlockSource` was removed, and `ProxyTracker` owns the player lifecycle for
`@record`, `record_class`, and `record_function` alike (consumption asserted at
`end_test`). The original analysis kept below for context.

**Current:** `targets.py` uses `_BlockSource` (a `StoreSource` shim) to intercept
`register_player` so `record_class` can assert at block exit rather than at
teardown. This is awkward — `_BlockSource`/`StoreSource` are separate types that
can't be used together cleanly.

**Direction (from CR):** Make targets.py its own layer that:
- Manages all recorder/player stream IDs (human-readable)
- Accesses files by passing IDs to storage.py (storage is just the I/O layer)
- Monkeypatches `__init__` (or the callable) to create proxies
- Registers one player per fixture it encapsulates (instead of per construction)

This removes the need for `_BlockSource` entirely and makes `record_class` and
`record_function` symmetric: both manage their own player lifecycle without
depending on the controller's player registry.

**Note on multiple `_make_replacement` methods:** `record_class` wraps the
constructed **instance** (method calls on the instance are events), while
`record_function` wraps the **callable** (the call itself is the event). The
redesign should make this distinction explicit in the layer's public API.
