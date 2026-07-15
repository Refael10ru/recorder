# pytest-recorder — Usage Guide

How to use the public API. For architecture and internals see
[project_map.md](project_map.md) and the per-layer docs in [`docs/`](docs/).

---

## Installation

The plugin registers itself with pytest via the `pytest11` entry point — no
`conftest.py` changes needed. Install the package into your test environment:

```bash
uv pip install -e .   # from a checkout
```

Requires Python ≥ 3.11 and pytest ≥ 8.

---

## Modes

Pick a mode with the `--recorder` flag (default: `off`):

```bash
pytest --recorder=record   # run against real dependencies, capture I/O to disk
pytest --recorder=play     # replay from disk: no network, strict-ordered checks
pytest                     # plugin off, real objects used as-is
```

| Mode | Real object built? | Behaviour |
|---|---|---|
| `off` | Yes | No-op; everything runs live. |
| `record` | Yes | Every call to a marked object is captured to a JSON file beside the test. |
| `play` | No | Marked objects are replaced by players that serve recorded results back, asserting every call matches in order. |

The workflow: run once with `--recorder=record` against the real dependency,
commit the generated recordings, then run with `--recorder=play` everywhere
else (CI, local dev). If your code starts using the dependency differently —
different args, different order, extra or missing calls — the replay fails
loudly instead of silently passing.

---

## Public API

All public names are importable from the package root:

```python
from pytest_recorder import record, record_class, record_function, is_recorder_mock
```

### `@record(name=None)` — fixture decorator

Wraps a fixture's return value in a recording/replay proxy. Apply it **between**
`@pytest.fixture` and the fixture function; both `@record()` and bare `@record`
work:

```python
import pytest
from pytest_recorder import record

@pytest.fixture
@record()
def pricing():
    return PricingClient(host="prod")   # real, slow, networked
```

- `name` keys the recording stream; it defaults to the fixture function's name
  (`"pricing"` above). Pass an explicit name if two fixtures share a name
  across modules: `@record("prod_pricing")`.
- In `record` mode the real factory runs and each method call on the yielded
  object is captured.
- In `play` mode **the factory is never called** — the fixture yields a player
  instead, so no network/DB connection is ever opened.
- Works with any fixture scope; a session-scoped fixture routes each test's
  calls to that test's own recording file.

### `record_class(*paths)` — patch constructors

Context manager / decorator. Patches one or more import paths so that
constructing the class returns a proxy that records/replays **method calls on
the instance**. Use it when the code under test builds the dependency itself:

```python
from pytest_recorder import record_class

def test_quote():
    with record_class("mylib.api.Client"):
        result = code_under_test()   # internally does Client(...).get_quote(...)

# or as a decorator:
@record_class("mylib.api.Client")
def test_quote():
    ...
```

Each distinct construction (same path + same constructor args) gets its own
recording stream, so multiple instances in one test are kept apart.

### `record_function(*paths)` — patch plain callables

Like `record_class`, but for module-level functions, builtins, and methods
where the **call itself** is the thing to record — the return value is captured
and served back directly:

```python
from pytest_recorder import record_function

def test_search():
    with record_function("wikipedia.search"):
        result = code_under_test()   # internally calls wikipedia.search(...)
```

Rule of thumb: patching a **class or factory** whose instance methods you care
about → `record_class`; patching a **function** whose return value you care
about → `record_function`.

### `is_recorder_mock(obj)` — proxy detection

Returns `True` if `obj` is a recorder proxy (recording or replaying), `False`
for real objects. Useful in test helpers that must branch on whether they got
the real thing:

```python
from pytest_recorder import is_recorder_mock

def test_smoke(pricing):
    if not is_recorder_mock(pricing):
        pricing.warm_up()   # only meaningful against the live system
```

---

## Exceptions

All raised in `play` mode; all inherit from `RecorderError`, so
`except RecorderError` catches any replay failure.

```python
from pytest_recorder.errors import (
    RecorderError,
    MissingRecording,
    RecordingExhausted,
    RecordingUnderused,
    RecordingMismatch,
)
```

| Exception | Meaning |
|---|---|
| `MissingRecording` | No recording file exists for this test — run it with `--recorder=record` first. |
| `RecordingMismatch` | A call's `(method, args, kwargs)` don't match the next recorded event — the code's usage of the dependency changed. |
| `RecordingExhausted` | The test made more calls than were recorded. |
| `RecordingUnderused` | The test made fewer calls than were recorded (checked at teardown). |

Each of these is a signal that the test's real behaviour drifted from the
recording: either fix the code, or re-record with `--recorder=record`.

---

## Recording files

Recordings are JSON files in a `recordings/` directory **beside the test
module**, named `<test_module>__<test_name>.json`:

```
tests/mockproj/test_depth.py::test_flat_object
  → tests/mockproj/recordings/test_depth__test_flat_object.json
```

Commit them with your tests — they are the contract the replay asserts
against. They travel with the test when it is moved or copied.

To re-record after an intentional behaviour change, run the affected tests
with `--recorder=record`; the files are overwritten.

---

## Assumptions and limitations

- **Pure-function dependencies.** Replay assumes output is determined by
  input. Dependencies with hidden state or time-dependent results will record
  fine but produce misleading replays.
- **Recording depth is one level.** Chained calls like
  `client.session().query()` are not replayed — only direct calls on the
  proxied object.
- **Secrets in `record_class` keys.** Constructor args (including API keys)
  are written verbatim into the recording's stream key. Prefer the `@record`
  fixture form for secret-bearing clients — it keys by fixture name, not
  constructor args. See [docs/known-issues.md](docs/known-issues.md) #2.
- **Non-picklable exception classes can't be recorded.** The pickle round-trip
  is validated at record time, so the record run fails loudly instead of
  writing a recording that breaks at play. See
  [docs/known-issues.md](docs/known-issues.md) #1.

The full defect list lives in [docs/known-issues.md](docs/known-issues.md).
