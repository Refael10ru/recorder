# Record-time load validation (`--recorder=validation`)

## Problem

The recorder stores each call's return value / exception via `encode()`
(JSON-native pass-through, else base64-pickle). Replay (`play`) reconstructs them
via `decode()`. Some real values — notably custom exceptions — `encode()` fine but
fail to `decode()`: e.g. `finnhub`'s `FinnhubAPIException` is raised with
`args == ()` while its `__init__` requires a positional arg, so
`pickle.loads` → `TypeError: __init__() missing 1 required positional argument`
at `serialize.py:42`.

The failure is **latent**: `record` succeeds and writes a recording that looks
fine; the breakage only surfaces later when someone runs `play`. See
[`../../known-issues.md`](../../known-issues.md) issue #1.

Solving exception reconstruction in general is out of scope (may not be possible).
Instead: catch unloadable recordings **at record time**, behind an opt-in mode.

## Goal

A new opt-in mode `--recorder=validation` that records exactly like `record` but,
for every stored call, immediately verifies the value **round-trips**:
`load(unload(x)) == x`. It fails loudly if the value can't be loaded back, or if
loading produces something different. Plain `record` stays fast and unvalidated.

### Robust equality

A naive `decode(stored) == original` is unreliable: many real returns
(numpy arrays, pandas frames, custom objects) have an `==` that returns a non-bool
or raises "truth value is ambiguous". So the check compares in **encoded space**
instead:

```
encode(decode(stored)) == stored
```

where `stored = encode(x)` is already in the event. Encoded forms are always
JSON-safe (scalars / strings / lists / dicts, or a `{"__pickle__": "<b64>"}`
envelope), so this equality is always well-defined — the same reason `PlayerProxy`
matches calls on encoded args (`engine.py:81`). This faithfully implements
`load(unload(x)) == x` and catches:
- decode failures (the finnhub exception case), and
- unstable round-trips where the reloaded value re-encodes differently.

Non-goals (deferred):
- Offline whole-file validation pass over existing recordings.
- Nicer encode-time (pickle.dumps) failure messaging.

## Design

### Mode

`--recorder` gains a fourth choice: `off | record | play | validation`.

`validation` behaves like `record` everywhere except it also load-checks:
- builds `RecordingProxy` wrappers (real deps are called — network happens),
- flushes recordings at teardown,
- additionally decodes each event as it is recorded and raises on failure.

### Components

**`errors.py`** — add:
```python
class RecordingValidationError(RecorderError):
    """Validation mode: a just-recorded value cannot be loaded back (decode failed)."""
```

**`validate.py`** (new, single purpose):
```python
def check_roundtrip(name: str, event: dict) -> None:
    """Verify load(unload(x)) == x for the event's return + raised.

    Raises RecordingValidationError if a stored value won't decode, won't
    re-encode, or re-encodes to something different.
    """
```
- For each present field (`event["return"]`, and `event["raised"]` if non-null),
  let `stored = event[field]`:
  - `reloaded = decode(stored)` — on exception → `RecordingValidationError`
    (`... cannot be loaded: <underlying>`).
  - `re = encode(reloaded)` — on exception → `RecordingValidationError`.
  - if `re != stored` → `RecordingValidationError` (`... does not round-trip`).
- Message names the proxy, the method, and which field failed.
- No network; pure round-trip in encoded space.

**`engine.py`** — `RecordingProxy`:
- `__init__(self, target, name, store, validate=False)` — store the flag.
- `_record(...)`: if `self._validate`, call `check_roundtrip(self._name, event)`
  **before** `self._store.append(...)`, so a non-round-tripping event never enters
  the store. On failure the raise propagates; the partial recording (good events
  so far) may still be flushed at teardown, which is fine — the run has failed
  loudly and will be re-recorded.
- Default `validate=False` keeps existing callers/behavior unchanged.

**`decorator.py`** (`@record`):
- Build a `RecordingProxy` when `ctrl.mode in ("record", "validation")`
  (currently only `"record"`).
- Pass `validate=(ctrl.mode == "validation")`.

**`targets.py`** (`record_targets`):
- `_make_shim`: in record/validation modes return
  `RecordingProxy(original(*args, **kwargs), key, store, validate=(mode == "validation"))`.
- Adjust the mode gate so the shim records in both `record` and `validation`.

**`plugin.py`** — `Controller`:
- `pytest_addoption`: add `"validation"` to `choices`.
- `current_store`: only `play` calls `store.load()` (unchanged).
- `end_test`: flush when `mode in ("record", "validation")`; assert players when
  `mode == "play"` (unchanged otherwise).

### Data flow (validation mode)

1. Test calls a recorded method on the `RecordingProxy`.
2. `_record` calls the real target, builds the event via `make_event` (encodes
   return/raised).
3. `check_roundtrip` verifies `encode(decode(stored)) == stored` for the event's
   return/raised.
   - round-trips → append to store; the real return is returned / real exception
     re-raised to the test as in `record`.
   - decode/encode raises or values differ → `RecordingValidationError`
     propagates, failing the test/run (event not appended).
4. At teardown, `record`/`validation` flush the recording to disk.

### Error handling

- The only new failure is `RecordingValidationError`, raised during a `validation`
  run when a stored value won't decode. It names the proxy, the method, and the
  underlying decode error.
- `record`, `play`, `off` behavior is unchanged.

## Testing (TDD)

Unit (`validate.check_roundtrip`):
- plain JSON-native event (dict return) → no raise.
- event whose `raised` is an encoded BoomError-style exception that won't
  `pickle.loads` → raises `RecordingValidationError` (load fails).
- event with a normal picklable object return → no raise (round-trips).
- event whose stored value re-encodes differently → raises
  `RecordingValidationError` (does not round-trip).

Integration (pytest with the plugin):
- A fixture returning a callable that raises a `BoomError` (custom exception,
  `args == ()`, required ctor arg):
  - `--recorder=record` → passes, writes recording (latent bug, no check).
  - `--recorder=validation` → raises `RecordingValidationError` at record time.
- A well-behaved fixture (JSON dict return):
  - `--recorder=validation` → passes and writes a recording identical to
    `--recorder=record`.
- `record_targets` path: same BoomError via inline construction →
  `validation` raises, `record` does not.

## Out of scope / future

- Offline file-scan validation (re-load existing recordings without re-running),
  encode-time (pickle.dumps) diagnostics (tracked separately if wanted).
