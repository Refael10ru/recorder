"""JSON-first value serialization with a base64-pickle fallback.

JSON-native values pass through unchanged. Anything ``json.dumps`` rejects is
wrapped as ``{"__pickle__": "<base64>"}`` so the result is always JSON-safe.
"""

import base64
import json
import pickle
from typing import Any, TypeGuard

_PICKLE_KEY = "__pickle__"


def _is_envelope(obj: object) -> TypeGuard[dict]:
    """True if ``obj`` looks like a pickle envelope (sole ``__pickle__`` key)."""
    return isinstance(obj, dict) and set(obj.keys()) == {_PICKLE_KEY}


def _wrap_blob(blob: bytes) -> dict:
    return {_PICKLE_KEY: base64.b64encode(blob).decode("ascii")}


def encode_exception(exc: BaseException) -> object:
    """Serialize an exception, failing loudly if it cannot survive a pickle round-trip.

    Validates at record time so a broken __reduce__ surfaces immediately rather
    than producing a confusing TypeError at play time (FIN-1).
    """
    blob = pickle.dumps(exc)
    try:
        rt: BaseException = pickle.loads(blob)
    except Exception as cause:
        raise RuntimeError(
            f"recorder: cannot record {type(exc).__qualname__!r} — "
            f"exception does not survive a pickle round-trip; "
            f"ensure __init__ passes its args to super().__init__(). "
            f"Underlying: {cause}"
        ) from cause
    if rt.args != exc.args:
        raise RuntimeError(
            f"recorder: cannot record {type(exc).__qualname__!r} — "
            f"pickle round-trip changes args "
            f"(original={exc.args!r}, round-tripped={rt.args!r})"
        )
    return _wrap_blob(blob)


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
    return _wrap_blob(pickle.dumps(obj))


def decode(val: object) -> Any:
    # WHY: return Any not object — pickle.loads is untyped and callers like
    # `raise decode(exc_blob)` need the type narrowable to BaseException.
    if _is_envelope(val):
        return pickle.loads(base64.b64decode(val[_PICKLE_KEY]))
    return val


def _encode_call(args: tuple, kwargs: dict) -> tuple[list, dict]:
    """Encode a call's positional and keyword args to JSON-safe forms."""
    return [encode(a) for a in args], {k: encode(v) for k, v in kwargs.items()}
