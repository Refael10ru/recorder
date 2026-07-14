# Known issues & limitations

Recorder defects and limitations found validating against real API clients
(see [`recorder-validation-targets.md`](recorder-validation-targets.md) for the
projects and [`../problems.md`](../problems.md) for the per-project runs).

Severity: 🟥 high · 🟧 med · 🟨 low.

---

## 1. 🟥 Recorded exceptions can fail to replay (latent: record passes, play breaks)

**Symptom.** A test that records a raised exception passes in `--recorder=record`
but fails in `--recorder=play` with e.g.:

```
TypeError: FinnhubAPIException.__init__() missing 1 required positional argument
  at src/pytest_recorder/serialize.py:42  (pickle.loads)
```

**Found in.** finnhub-python (`FinnhubAPIException`, 401 error path).

**Cause.** Exceptions are stored via `encode()` → `pickle.dumps`, and rebuilt via
`decode()` → `pickle.loads`. Many real exception classes are not cleanly
picklable: `FinnhubAPIException` is raised with `args == ()` while its `__init__`
requires a positional arg, so `BaseException.__reduce__` yields `cls()`, which
fails to reconstruct. `pickle.dumps` succeeds at record time; `pickle.loads`
fails only at replay — so the recording looks fine until someone plays it.

**Repro.**
```python
import pickle
from finnhub.exceptions import FinnhubAPIException
# raise as the client does -> ex.args == ()
b = pickle.dumps(ex)      # OK at record
pickle.loads(b)           # TypeError at play
```

**Fix direction.** Don't trust a clean pickle round-trip for exceptions:
- round-trip (encode→decode) the exception at **record** time and fail loudly then,
  so the defect can't reach a committed recording; and/or
- store exceptions structurally (type name + `str()` + encoded `args`) and rebuild
  defensively, falling back to re-raising a generic error that preserves the
  original type name and message when reconstruction isn't possible.

**Status.** Mitigated — `encode_exception` (serialize.py) now validates the
pickle round-trip at record time, so the record run fails loudly and a bad
recording can't be committed. Structural rebuild / defensive re-raise is not
implemented: non-picklable exceptions still can't be replayed, they just fail
at the right moment.

---

## 2. 🟥 Secrets written into recordings (`record_class`)

**Symptom.** Constructor arguments — including API keys/secrets — are written
verbatim into the recording. Confirmed stream key:

```
finnhub.Client([[], {"api_key": "DEMO_LEAK_KEY_12345"}])#0
```

**Found in.** finnhub-python (concrete leak); applies to every key-required client
constructed via `record_class` (python-binance, coinbase-advanced, alpha_vantage…).

**Cause.** `record_class` keys each construction by its arguments
(`_base_key` in `src/pytest_recorder/proxy_tracking.py` json-dumps the raw args). Secrets
passed to the constructor land in the key, which is persisted to disk and would be
committed alongside tests.

**Not affected.** The fixture `@record` path keys by the fixture *name*, not
constructor args — no leak there.

**Fix direction.** Redact/hash constructor args in the key, or add a per-target
arg-scrubber hook (cf. VCR's `filter_*` before-record hooks). Provide a documented
way to mark secret-bearing positions.

**Status.** Open.

---

## 3. 🟧 `record_targets` does not support plain functions *(historical name of `record_class`)*

**Symptom.** Pointing `record_targets` at a module-level function makes the test
receive a proxy *around the return value* instead of the value:

```
record_targets("wikipedia.search")  ->
TypeError: argument of type 'RecordingProxy' is not iterable
```
and nothing useful is recorded.

**Found in.** goldsmith/Wikipedia (`wikipedia.search`, `wikipedia.summary`).

**Cause.** The shim does `RecordingProxy(original(*args))` — it assumes the patched
symbol is a **factory/constructor** whose *return* is the object whose methods
should be recorded. For a plain function the symbol *itself* is the recordable
call, so its return value gets wrapped by mistake.

**Workaround.** Use the `@record` fixture form returning the function:
```python
@pytest.fixture
@record("search")
def search():
    return wikipedia.search
```
(`RecordingProxy.__call__` records the call and returns the real value.)

**Fix direction.** In `record_targets`, detect when the target is a plain function
(not a class/factory) and record the call directly (wrap the symbol as a callable
`RecordingProxy`, like the fixture path) rather than wrapping its return.

**Status.** Fixed — `record_function` records the call itself for plain
callables and passes the real return value through (see
[`proxy_tracking.md`](proxy_tracking.md) and USAGE.md); `record_targets` was
renamed `record_class` and remains the class/factory form.

---

## Non-recorder gotchas (environment / project, documented for completeness)

- **HTTP 403 on default User-Agent** (Wikipedia): set a real UA before recording.
- **Dead default host** (coinbasepro-python): legacy `api.pro.coinbase.com` is
  sunset; pass `api_url="https://api.exchange.coinbase.com"`.
- **Large payloads** make recordings heavy (coinbasepro `get_products()` ~824
  items): record is slow, but replay stays instant.
