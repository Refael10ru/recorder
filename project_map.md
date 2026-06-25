# pytest-recorder — Project Map

> Living document. Update when module responsibilities, APIs, or key design
> decisions change. Layers are listed bottom-up (fewest deps first).

---

## What this project is

A pytest plugin for **record/replay fixture mocking**. In `record` mode it
wraps real objects (network clients, DB connections, etc.) in proxies that
capture every call to JSON files. In `play` mode it replaces real objects with
stubs that replay the captured calls in strict order. This makes slow/flaky
system tests reproducible and offline-runnable.

Three modes: `off` (default, no-op), `record`, `play`. Set via `--recorder=<mode>`.

---

## Module map (bottom-up dependency order)

```
errors.py          ← exception types; no recorder deps
serialize.py       ← encode/decode values to JSON-safe form; no recorder deps
storage.py         ← file path resolution + per-test event buffer; no recorder deps
engine.py          ← RecordingProxy + PlayerProxy; imports errors, serialize, storage
plugin.py          ← Controller + pytest hooks; imports engine, errors, storage
decorator.py       ← @record fixture decorator; imports engine, plugin
targets.py         ← record_class / record_function; imports engine, plugin, storage
__init__.py        ← public API: re-exports record, record_class, record_function
```

No circular imports. The `_StoreSource` Protocol in `engine.py` exists specifically
to let the engine accept both `RecordingStore` and `Controller` without importing `plugin`.

---

## Layer-by-layer

### `errors.py`
Exception hierarchy. All recorder errors inherit from `RecorderError`.

| Exception | When raised |
|---|---|
| `MissingRecording` | Play mode, no `.json` file found |
| `RecordingExhausted` | Play mode, more calls than recorded |
| `RecordingUnderused` | Play mode, fewer calls than recorded |
| `RecordingMismatch` | Play mode, call args don't match recording |

---

### `serialize.py`
JSON-first encoding with base64-pickle fallback.

- `encode(obj)` → JSON-safe. Passes through JSON-native values unchanged.
  Wraps anything else as `{"__pickle__": "<base64>"}`.
- `decode(val)` → original value. Detects the envelope and unpickles.
- `encode_exception(exc)` → validates pickle round-trip **at record time**.
  If `exc` doesn't survive pickle (broken `__reduce__`, args lost), raises
  `RuntimeError` immediately rather than storing a time-bomb that blows up
  at play time with a confusing `TypeError`. (FIN-1)

**Why match on encoded args during play?**  
`PlayerProxy._consume` compares encoded (not decoded) args. This avoids
`ValueError: truth value of array is ambiguous` when args are numpy arrays
or pandas objects whose `==` returns an array, not a bool.

---

### `storage.py`
Two responsibilities: path resolution and the per-test event buffer.

**`resolve_recording_path(nodeid, test_file) → Path`**  
Maps a pytest nodeid to a `.json` file in a `recordings/` dir next to the
test module. Recordings travel with the test when it's moved/copied.

```
tests/mockproj/test_depth.py::test_flat_object
  → tests/mockproj/recordings/test_depth__test_flat_object.json
```

**`RecordingStore`**  
In-memory `{fixture_name: [event, ...]}` dict that loads from / flushes to JSON.

- `append(name, event)` — buffer one event (record mode)
- `events(name)` — return buffered events (play mode; empty list if missing)
- `load()` / `flush()` — read from / write to disk

**`current_store()` returns self** — duck-type shim. Both `RecordingStore` and
`Controller` expose `current_store()`. This lets the engine hold a `_StoreSource`
reference without needing to know which concrete type it has. For a plain store,
calling `current_store()` is a no-op identity.

---

### `engine.py`
The record/replay core.

**`_StoreSource` Protocol**  
Structural type for anything that has `current_store() → RecordingStore`.
Satisfied by both `RecordingStore` (via its shim) and `Controller`.
Using a Protocol (not ABC) avoids the engine→plugin circular import.

**`RecordingProxy(target, name, source)`**  
Wraps a real object. On every method call or `__call__`:
1. Calls the real method.
2. Serializes the outcome (return value or exception) via `encode`/`encode_exception`.
3. Calls `source.current_store().append(name, event)`.
4. Re-raises the exception or returns the value.

Holds `source` (not a fixed store) so non-function-scope fixtures always write
to the current test's file as the Controller's `_nodeid` changes between tests.

**`PlayerProxy(name, source)`**  
Replays events in strict order. On every call:
1. `_maybe_reload()` — if the source's `_nodeid` changed, reload events from
   the new test's recording and re-register with the Controller.
2. Consume next event: verify (method, encoded-args, encoded-kwargs) match.
3. Return decoded value or re-raise decoded exception.

**`_maybe_reload()` sentinel logic**  
`_last_nodeid` starts as `_INIT`. `_UNSET` is what `getattr(plain_store, '_nodeid', _UNSET)` returns when the source has no `_nodeid`. Two distinct sentinels are needed: `_INIT ≠ _UNSET` ensures the initial load fires even on a plain store; after that, `_UNSET == _UNSET` → no spurious reloads.

**`make_event` / `_encode_call`** — helpers to build the serialized event dict.

---

### `plugin.py`
Pytest integration. One global `Controller` instance per test session.

**`Controller`**
- Holds `mode` + per-test state: `_nodeid`, `_test_file`, `_store`, `_players`.
- `begin_test(nodeid, path)` — called at test setup; resets per-test state.
- `current_store()` — lazily creates/loads `RecordingStore` for the current test.
- `register_player(player)` — tracks players so teardown can assert full consumption.
- `end_test()` — flushes (record) or asserts all players consumed (play).

**Pytest hooks**
- `pytest_addoption` — registers `--recorder` option.
- `pytest_configure` — creates the global Controller.
- `pytest_runtest_setup` → `begin_test`.
- `pytest_runtest_teardown` → `end_test`.

**`get_controller()`** — global accessor used by `decorator.py` and `targets.py`.

---

### `decorator.py`
`@record(name)` — the primary user-facing fixture decorator.

```python
@pytest.fixture
@record("pricing")
def pricing():
    return PricingClient()
```

A generator fixture that:
- In `off` mode: yields the real object.
- In `record` mode: yields `RecordingProxy(real_obj, name, ctrl)`.
- In `play` mode: yields `PlayerProxy(name, ctrl)` — real factory is **not called**.

Passes `ctrl` (not `ctrl.current_store()`) so the proxy routes each call to the
correct test's recording when the fixture outlives a single test.

---

### `targets.py`
`record_class` / `record_function` — context-manager / decorator for
monkeypatching by **import path** (no fixture needed).

```python
with record_class("mylib.api.Client"):
    result = code_under_test()

@record_function("wikipedia.search")
def test_wiki():
    ...
```

**`record_class`** patches the symbol so construction returns a `RecordingProxy`
(record) or `PlayerProxy` (play) that intercepts **method calls on the instance**.

**`record_function`** inherits `record_class` and overrides `_make_replacement`
so the **call itself** is recorded/replayed — not method calls on the return value.
Use for plain callables like `wikipedia.search` where you want to capture
the function's return value directly.

Both use a per-instance `_counters` dict to disambiguate multiple calls to the
same constructor/function in one block: `path(args)#0`, `path(args)#1`, etc.

---

## Data flow

### Record mode
```
pytest_configure → Controller("record")
pytest_runtest_setup → ctrl.begin_test(nodeid, path)

  @record fixture OR record_class context manager
    → RecordingProxy(real_obj, name, ctrl)

  test code calls proxy.method(args)
    → calls real method, captures return/exception
    → ctrl.current_store()  [lazy-creates RecordingStore for this test]
    → store.append(name, make_event(...))

pytest_runtest_teardown → ctrl.end_test()
  → store.flush() → writes recordings/<safe_name>.json
```

### Play mode
```
pytest_configure → Controller("play")
pytest_runtest_setup → ctrl.begin_test(nodeid, path)

  @record fixture OR record_class context manager
    → PlayerProxy(name, ctrl)
    → _maybe_reload() → ctrl.current_store() → store.load()
    → ctrl.register_player(self)

  test code calls proxy.method(args)
    → _maybe_reload() [no-op if same test]
    → _consume(): verify (method, encoded-args) match next event
    → decode and return / re-raise

pytest_runtest_teardown → ctrl.end_test()
  → player.assert_consumed() for each registered player
```

---

## Key non-obvious decisions

| Decision | Why |
|---|---|
| `_StoreSource` Protocol (not ABC) | ABC would require engine to import plugin → circular import |
| Hold `source` not `store` in proxies | Non-function-scope fixtures share one proxy across N tests; per-call `current_store()` routes each test to its own file |
| Two sentinels `_INIT` / `_UNSET` | `_INIT ≠ _UNSET` ensures first `_maybe_reload()` fires on plain stores (which have no `_nodeid`) |
| Match encoded args in play | Decoded numpy/pandas `==` raises "ambiguous truth value"; encoded forms are plain dicts/strings/lists, `==` is safe |
| `encode_exception` validates round-trip | FIN-1: surface broken pickle at record time (clear error) not play time (confusing `TypeError`) |
| `RecordingStore.current_store()` shim | Duck-type parity with Controller so engine's `_StoreSource` Protocol is satisfied by plain stores in direct-use tests |
| `record_function` inherits `record_class` | Shares `__enter__`/`__exit__`, `_next_key`, `_counters`; overrides only `_make_replacement` and `__call__` |

---

## Known limitations / open issues

- **Nested chain replay** (e.g. `client.session().query(...)`) — outer object records fine, but inner (session) is itself a proxy, not a real object. Replay skips this test in play mode (`test_nested_chain_records_outer_only` is marked `skipif` in play). See `docs/superpowers/notes/2026-06-12-depth-findings.md`.
- Non-function-scope fixtures: fixed (SCP-1). Session/module/class-scoped fixtures now correctly route to each test's recording.
- Exception replay: fixed (FIN-1). Non-picklable exceptions now fail loudly at record time.

---

## Test layout

| File | What it tests |
|---|---|
| `test_storage.py` | `resolve_recording_path`, `RecordingStore` load/flush |
| `test_serialize.py` | `encode`, `decode`, `encode_exception` |
| `test_engine.py` | `RecordingProxy`, `PlayerProxy`, SCP-1 + FIN-1 regressions |
| `test_decorator.py` | `@record` fixture decorator |
| `test_targets.py` | `record_class`, `record_function` |
| `test_integration.py` | E2E subprocess runs against `tests/mockproj/` |
| `test_wiki1.py` | WIKI-1 regression: `record_function` with `wikipedia.search` |
| `tests/mockproj/` | Testbed project with real fixtures for E2E tests |
