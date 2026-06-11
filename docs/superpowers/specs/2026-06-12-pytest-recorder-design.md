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

### Components

- **`pytest_recorder/plugin.py`** — registers `--recorder` option; session-scoped
  controller holds current mode + current test nodeid; owns the per-test event
  store; on teardown flushes (record) or asserts full consumption (play).
- **`@record(name)`** decorator — wraps a fixture function:
  - `off`: yield the fixture's value untouched.
  - `record`: run fixture body, wrap value in `RecordingProxy(value, name, controller)`, yield proxy.
  - `play`: skip body, yield `PlayerProxy(events_for(name), name)`.
- **`RecordingProxy(target, name)`**
  - `__call__(*a, **k)` → records event for a direct callable (`method="__call__"`).
  - `__getattr__(m)` → returns a wrapper that invokes the real method, records
    `(name, m, args, kwargs, return | raised)`, appends to the ordered event list.
  - **Exceptions:** if the real call raises, the wrapper records the exception
    into the event's `raised` field (serialized, pickle path — exceptions are
    rarely JSON-able), leaves `return` null, then **re-raises** to the live test
    so record mode behaves identically to no recorder.
- **`PlayerProxy(events_iter, name)`**
  - `__call__` / method access → pop next event, assert `(method, args, kwargs)`
    equal. If the event has `raised`, **re-raise the deserialized exception** at
    the matching call site (same type, args, and — best effort — traceback note);
    otherwise return the deserialized return value. Holds no real target.
- **`serialize.py`** — `dumps(obj)`: try JSON with a custom encoder; on `TypeError`
  fall back to `{"__pickle__": base64(pickle(obj))}`. `loads(env)` inverse.
- **`storage.py`** — maps nodeid → `tests/recordings/<module>/<nodeid>.json`.
  File shape: `{ "<fixture_name>": [event, ...], ... }`.

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

- **Unit:** serializer roundtrip (JSON path + pickle path); `RecordingProxy`
  captures calls; `PlayerProxy` match + each error type; storage path mapping.
- **Integration:** the mock testbed run as a subprocess — `--recorder=record` then
  `--recorder=play`, assert pass; then mutate a test and assert `RecordingMismatch`.
- Depth ladder doubles as the integration matrix: every rung must round-trip.
