# pytest-recorder — Record/Replay Fixture Mocking Library

Date: 2026-06-12

## Purpose

Optimization library for system tests. Mark fixtures/objects to **record** their
usage (inputs + outputs, serialized per test). In **play** mode, replace each
marked fixture with a player that replays the recording and asserts the test used
the object in the exact same way. Assumes recorded callables/objects are **pure
functions** (return value fully determined by args; no side effects, no hidden
state).

## Modes

Activated by pytest flag `--recorder=<mode>`:

| mode     | default            | behavior                                                              |
|----------|--------------------|-----------------------------------------------------------------------|
| `off`    | yes (flag absent)  | `@record` is passthrough, zero overhead                               |
| `record` |                    | fixture body runs; yielded value wrapped in `RecordingProxy`; events flushed at teardown |
| `play`   |                    | fixture body **skipped**; `PlayerProxy` returned from recording; strict-ordered replay |

In play, the proxy needs no real object, so the (potentially expensive) fixture
construction is avoided entirely — this is the optimization.

## Locked Decisions

- **Mechanism:** transparent proxy (not monkeypatch, not mock.autospec).
- **Record unit:** both plain callables and objects whose methods are wrapped.
- **Serialization:** JSON primary; pickle fallback for non-JSON-able values.
- **Match semantics:** strict ordered — exact call order, exact args; any deviation errors.
- **Marking API:** `@record('name')` decorator on a pytest fixture.
- **Storage:** one JSON file per test, keyed by pytest nodeid, committed beside tests.
- **Play construction:** fixture body skipped; player built from recording.

## Architecture

pytest plugin + proxy objects + serializer + storage.

### Layering (testability)

The engine is **pytest-agnostic and manually drivable**. Three layers, each
usable on its own:

1. **Engine** (`RecordingProxy` / `PlayerProxy`) — accept an explicit **store**
   (the file/handle they read/write) plus the fixture `name`. They know nothing
   about pytest, modes, or path resolution. A unit test can construct a
   `RecordingProxy` over any object with any store, drive calls, then construct a
   `PlayerProxy` over the same store and replay — no pytest involved.
2. **Storage** (`storage.py`) — pure path/IO functions, separate from the engine.
   `resolve_recording_path(nodeid) -> Path` and a small `RecordingStore` that
   loads/saves the per-test JSON file. Decoupled so the engine never hard-codes
   where recordings live.
3. **Wiring** (`@record` decorator + plugin) — thin selector only. Reads mode from
   the controller, resolves the store via storage, constructs the right engine
   object. No record/replay logic of its own.

### Components

- **`pytest_recorder/plugin.py`** — registers `--recorder` option; session-scoped
  controller exposes current mode + current test nodeid; on teardown flushes the
  store (record) or asserts full consumption (play). Holds no proxy logic.
- **`@record(name)`** decorator — **thin wrapper, selects off / record / play**:
  - `off`: yield the fixture's value untouched.
  - `record`: run fixture body, `yield RecordingProxy(value, name, store)`.
  - `play`: skip body, `yield PlayerProxy(name, store)`.
  - It only resolves `store = RecordingStore(resolve_recording_path(nodeid))` from
    the controller and picks a branch — nothing else.
- **`RecordingProxy(target, name, store)`** — `store` is the explicit file/handle
  it writes events to (injected, not discovered):
  - `__call__(*a, **k)` → records event for a direct callable (`method="__call__"`).
  - `__getattr__(m)` → returns a wrapper that invokes the real method, records
    `(name, m, args, kwargs, return | raised)`, appends to the ordered event list.
  - **Exceptions:** if the real call raises, the wrapper records the exception
    into the event's `raised` field (serialized, pickle path — exceptions are
    rarely JSON-able), leaves `return` null, then **re-raises** to the live test
    so record mode behaves identically to no recorder.
- **`PlayerProxy(name, store)`** — reads its events from the explicit `store`:
  - `__call__` / method access → pop next event, assert `(method, args, kwargs)`
    equal. If the event has `raised`, **re-raise the deserialized exception** at
    the matching call site (same type, args, and — best effort — traceback note);
    otherwise return the deserialized return value. Holds no real target.
- **`serialize.py`** — `dumps(obj)`: try JSON with a custom encoder; on `TypeError`
  fall back to `{"__pickle__": base64(pickle(obj))}`. `loads(env)` inverse.
- **`storage.py`** — `resolve_recording_path(nodeid) -> Path` (standalone, maps
  nodeid → `tests/recordings/<module>/<nodeid>.json`) and `RecordingStore`
  (load/save the per-test file). File shape: `{ "<fixture_name>": [event, ...], ... }`.

### Event model

```json
{ "method": "query", "args": [...], "kwargs": {...},
  "return": <serialized>, "raised": null }
```

`method = "__call__"` for a direct callable. Events ordered per fixture. Exactly
one of `return` / `raised` is non-null per event: a recorded raise sets `raised`
to the serialized exception and leaves `return` null. Exceptions are captured in
record (then re-raised live) and re-raised in play — a method that raises is a
fully recorded, replayable outcome, not an error in the recorder.

### Matching (strict ordered)

Events consumed sequentially. Live `(method, args, kwargs)` is serialized and
compared to the next recorded event. Mismatch → `RecordingMismatch` with an
expected-vs-got diff. Recorded exceptions are re-raised at the matching point.

## Error Handling (play)

- Missing recording file → clear error with regenerate hint.
- Live call beyond recorded events → `RecordingExhausted`.
- Unconsumed events at teardown → `RecordingUnderused`.
- method/args mismatch → `RecordingMismatch` + diff.
- Serialization fails even with pickle → error naming fixture + method.

## Object-Depth Coverage (primary near-term goal)

First deliverable is a **mock testbed project** that probes how deep the recorder
can capture object usage. The proxy intercepts calls on the marked object; the
open question is what happens when a method *returns another object* the test then
calls. The testbed climbs a depth ladder, built incrementally in this order:

1. **Pure callable** — standalone function, args in / serializable value out.
2. **Flat object** — methods returning scalars / dict / list (JSON-able).
3. **Pickle-only returns** — methods returning numpy / dataframe / custom objects,
   exercising the pickle fallback.
4. **Nested / chained object** — method returns another object that is then called
   (fluent / builder, e.g. `client.session().query()`). The hard case; the testbed
   measures exactly where capture breaks and whether nested proxying must move
   in-scope.

Each rung is a fixture in the mock project plus a system test that exercises it.
The recorder is validated against each rung under `record` then `play`. Every
rung also includes at least one call that **raises**, to validate exception
record/replay alongside return-value replay.

## Out of Scope (YAGNI, pending testbed findings)

- Automatic nested proxying — initially assume methods return serializable data;
  the testbed determines whether this assumption holds and whether to lift it.
- Non-determinism / side effects / stateful objects — pure functions only.
- Concurrency within a single test.

## Testing (TDD)

- **Unit (engine, no pytest):** construct `RecordingProxy(obj, name, store)` over a
  plain store, drive calls manually, then `PlayerProxy(name, store)` over the same
  store and replay — record→play round-trip with zero pytest. Covers match +
  every error type + exception replay.
- **Unit:** serializer roundtrip (JSON path + pickle path); `resolve_recording_path`
  nodeid → path mapping; `RecordingStore` load/save.
- **Integration:** the mock testbed run as a subprocess — `--recorder=record` then
  `--recorder=play`, assert pass; then mutate a test and assert `RecordingMismatch`.
- Depth ladder doubles as the integration matrix: every rung must round-trip.
