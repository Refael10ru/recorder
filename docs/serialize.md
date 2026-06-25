# serialize.py — Value encoding

No recorder dependencies.

## Strategy

JSON-first with base64-pickle fallback. JSON-native values pass through
unchanged so recordings are human-readable for simple types. Anything
`json.dumps` rejects is wrapped as `{"__pickle__": "<base64>"}`.

```
encode(obj) → JSON-safe form
decode(val) → original value
```

`_is_envelope(obj)` detects the pickle wrapper: a dict with exactly one key,
`"__pickle__"`. A user-supplied dict that happens to look like an envelope is
forced through pickle so it cannot be misread on decode.

## Exception serialization — FIN-1

`encode_exception(exc)` validates the pickle round-trip **at record time**:

1. Pickle the exception.
2. Unpickle it immediately and compare `args`.
3. If either step fails, raise `RuntimeError` with a clear message.

Without this check a broken `__reduce__` (e.g. `super().__init__()` called with
no args) stores a bad pickle that only fails at play time with a confusing
`TypeError`. FIN-1 surfaces it at the right moment.

## Why encoded arg matching in PlayerProxy

`PlayerProxy._consume` compares **encoded** (not decoded) call args. Decoded
numpy arrays / pandas objects raise `ValueError: truth value is ambiguous` when
compared with `==`. Encoded forms are plain dicts / strings / lists where `==`
is always safe.
