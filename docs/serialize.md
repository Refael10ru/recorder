# serialize.py

## Public API (used by engine)

```python
from pytest_recorder.serialize import encode, decode, encode_exception
```

| Symbol | Signature | Purpose |
|---|---|---|
| `encode` | `(obj: object) -> object` | Return a JSON-safe representation |
| `decode` | `(val: object) -> Any` | Reverse `encode`; returns original value |
| `encode_exception` | `(exc: BaseException) -> object` | Encode an exception; validates pickle round-trip |

## Internals

### Strategy

JSON-first: values that `json.dumps` accepts pass through unchanged, keeping
recordings human-readable. Anything rejected is wrapped as a pickle envelope:

```json
{"__pickle__": "<base64-encoded pickle bytes>"}
```

`_is_envelope(obj)` detects this wrapper (dict with exactly one key `"__pickle__"`).
A user-supplied dict that coincidentally has only a `"__pickle__"` key is forced
through pickle so it cannot be misread as an envelope on decode.

### encode_exception — FIN-1

Validates the pickle round-trip **at record time**:

1. Pickle the exception.
2. Unpickle immediately and compare `args`.
3. If either step fails, raise `RuntimeError` with a clear message.

Without this, a broken `__reduce__` (e.g. `super().__init__()` called with no
args so `self.args == ()`) stores a bad pickle that only surfaces at play time
as a confusing `TypeError`. FIN-1 moves this failure to the right moment.

### Why PlayerProxy compares encoded args

`PlayerProxy._consume` compares **encoded** (not decoded) call args. Decoded
numpy arrays / pandas objects raise `ValueError: truth value is ambiguous` when
compared with `==`. Encoded forms are plain dicts / strings / lists — `==` is
always safe.
