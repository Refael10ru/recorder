"""JSON-first value serialization with a base64-pickle fallback.

JSON-native values pass through unchanged. Anything ``json.dumps`` rejects is
wrapped as ``{"__pickle__": "<base64>"}`` so the result is always JSON-safe.
"""

import base64
import json
import pickle
from typing import TypeGuard

_PICKLE_KEY = "__pickle__"


def _is_envelope(obj: object) -> TypeGuard[dict]:
    """True if ``obj`` looks like a pickle envelope (sole ``__pickle__`` key)."""
    return isinstance(obj, dict) and set(obj.keys()) == {_PICKLE_KEY}


def encode(obj: object) -> object:
    """Return a JSON-safe representation of ``obj``.

    JSON-native values pass through unchanged. Anything ``json.dumps`` rejects
    is wrapped as ``{"__pickle__": "<base64>"}``. A user value that *itself*
    looks like an envelope (a sole-``__pickle__``-key dict) is forced down the
    pickle path so it does not get misread as an envelope on decode.
    """
    if not _is_envelope(obj):
        try:
            json.dumps(obj)
        except (TypeError, ValueError):
            pass
        else:
            return obj
    blob = base64.b64encode(pickle.dumps(obj)).decode("ascii")
    return {_PICKLE_KEY: blob}


def decode(val: object) -> object:
    """Invert :func:`encode`, unwrapping the base64-pickle envelope if present."""
    if _is_envelope(val):
        return pickle.loads(base64.b64decode(val[_PICKLE_KEY]))
    return val
