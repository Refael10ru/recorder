# errors.py

## Public API (used by engine, plugin)

```python
from pytest_recorder.errors import RecorderError
from pytest_recorder.errors import MissingRecording
from pytest_recorder.errors import RecordingExhausted
from pytest_recorder.errors import RecordingUnderused
from pytest_recorder.errors import RecordingMismatch
```

| Symbol | Raised by | When |
|---|---|---|
| `RecorderError` | — | Base; catch-all for any recorder failure |
| `MissingRecording` | plugin | Play mode: no `.json` file for this test |
| `RecordingExhausted` | engine | Play mode: more live calls than recorded events |
| `RecordingUnderused` | engine | Play mode: fewer live calls than recorded events |
| `RecordingMismatch` | engine | Play mode: `(method, args, kwargs)` don't match next event |

## Internals

No logic. All five classes are plain `Exception` subclasses with no custom
`__init__` — message is passed as the first positional arg to the base.

```
RecorderError (Exception)
├── MissingRecording
├── RecordingExhausted
├── RecordingUnderused
└── RecordingMismatch
```
