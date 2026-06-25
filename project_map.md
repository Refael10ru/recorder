# pytest-recorder — Project Map

> Public API reference and orientation guide.
> For internal design decisions see the per-layer docs in `docs/`.

---

## What this project is

A pytest plugin for **record/replay fixture mocking**. In `record` mode it
captures real I/O (network, DB, etc.) to JSON files; in `play` mode it replays
those captures without hitting live systems.

---

## Modes

Set via `--recorder=<mode>` (default: `off`).

| Mode | Effect |
|---|---|
| `off` | No-op. Real objects used as-is. |
| `record` | Wraps real objects; captures every call to a JSON file beside the test. |
| `play` | Replaces real objects with stubs that replay captured calls in strict order. |

---

## Public API

### `@record(name=None)`

Fixture decorator. Wraps the fixture's return value in a recording/replay proxy.

```python
from pytest_recorder import record

@pytest.fixture
@record("pricing")
def pricing():
    return PricingClient()
```

`name` keys the recording stream. Defaults to the decorated function's name.

---

### `record_class(*paths)`

Context manager / decorator. Patches one or more import paths so construction
returns a recording/replay proxy that intercepts **method calls on the instance**.

```python
from pytest_recorder import record_class

with record_class("mylib.api.Client"):
    result = code_under_test()

# or as a decorator:
@record_class("mylib.api.Client")
def test_something():
    ...
```

---

### `record_function(*paths)`

Like `record_class` but for **plain callables** (functions, builtins, methods).
Records/replays the call itself and returns the captured value directly.

```python
from pytest_recorder import record_function

with record_function("wikipedia.search"):
    result = code_under_test()
```

---

## Exceptions (public)

All inherit from `RecorderError`.

| Exception | When raised |
|---|---|
| `MissingRecording` | Play mode: no recording file found for this test |
| `RecordingExhausted` | Play mode: more live calls than recorded events |
| `RecordingUnderused` | Play mode: fewer live calls than recorded events |
| `RecordingMismatch` | Play mode: call args don't match the next recorded event |

---

## Recording file location

Recordings live in a `recordings/` directory **beside the test module**, named
after the test. They travel with the test when it is moved or copied.

```
tests/mockproj/test_depth.py::test_flat_object
  → tests/mockproj/recordings/test_depth__test_flat_object.json
```

---

## Internal docs (per layer)

| File | Covers |
|---|---|
| [`docs/errors.md`](docs/errors.md) | Exception hierarchy |
| [`docs/serialize.md`](docs/serialize.md) | JSON-first encode/decode with pickle fallback |
| [`docs/interfaces.md`](docs/interfaces.md) | `StoreSource` ABC — shared contract between storage and engine |
| [`docs/storage.md`](docs/storage.md) | Path resolution and per-test event buffer |
| [`docs/engine.md`](docs/engine.md) | `RecordingProxy`, `PlayerProxy` |
| [`docs/plugin.md`](docs/plugin.md) | `Controller`, pytest hooks |
| [`docs/decorator.md`](docs/decorator.md) | `@record` fixture decorator |
| [`docs/targets.md`](docs/targets.md) | `record_class` / `record_function` |
