"""JSON-first value serialization with a base64-pickle fallback.

JSON-native values pass through unchanged. Anything ``json.dumps`` rejects is
wrapped as ``{"__pickle__": "<base64>"}`` so the result is always JSON-safe.
"""

import base64
import json
import pickle

_PICKLE_KEY = "__pickle__"


def encode(obj: object) -> object:
    """Return a JSON-safe representation of ``obj``.

    JSON-native values pass through unchanged. Anything ``json.dumps`` rejects
    is wrapped as ``{"__pickle__": "<base64>"}``.
    """
    try:
        json.dumps(obj)
    except (TypeError, ValueError):
        blob = base64.b64encode(pickle.dumps(obj)).decode("ascii")
        return {_PICKLE_KEY: blob}
    return obj


def decode(val: object) -> object:
    """Invert :func:`encode`, unwrapping the base64-pickle envelope if present."""
    if isinstance(val, dict) and set(val.keys()) == {_PICKLE_KEY}:
        return pickle.loads(base64.b64decode(val[_PICKLE_KEY]))
    return val
