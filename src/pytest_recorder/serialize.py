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
    # WHY: encode() and encode_exception() both produce the same envelope; this
    # deduplicates the construction so a format change only touches one place.
    # Alt: inline the dict literal in both — rejected because the copies can silently
    # diverge if one is updated without the other.
    return {_PICKLE_KEY: base64.b64encode(blob).decode("ascii")}


def encode_exception(exc: BaseException) -> object:
    """Serialize an exception, failing loudly if it cannot survive a pickle round-trip.

    Validates at *record* time rather than letting the failure appear silently at
    *play* time (FIN-1). The alternative — store type+str and reconstruct
    defensively — was rejected because it loses the original args and produces a
    different exception on replay.
    """
    blob = pickle.dumps(exc)
    try:
        # FIN-1: validate round-trip eagerly; a silent loads() failure only surfaces
        # at play time as a confusing TypeError — surfacing it here is always better.
        rt: BaseException = pickle.loads(blob)
    except Exception as cause:
        raise RuntimeError(
            f"recorder: cannot record {type(exc).__qualname__!r} — "
            f"exception does not survive a pickle round-trip; "
            f"ensure __init__ passes its args to super().__init__(). "
            f"Underlying: {cause}"
        ) from cause
    # FIN-1: a broken __reduce__ can reconstruct without error but drop args;
    # compare here so decode() (unchanged) still replays the right exception.
    if rt.args != exc.args:
        raise RuntimeError(
            f"recorder: cannot record {type(exc).__qualname__!r} — "
            f"pickle round-trip changes args "
            f"(original={exc.args!r}, round-tripped={rt.args!r})"
        )
    return _wrap_blob(blob)  # WHY: reuse _wrap_blob instead of inlining the dict


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
    return _wrap_blob(pickle.dumps(obj))  # WHY: reuse _wrap_blob, not inline dict


def decode(val: object) -> Any:
    # WHY: return Any not object — pickle.loads is untyped (returns Any) and callers
    # like `raise decode(exc_blob)` require the type to be narrowable to BaseException.
    # object is not raiseable in mypy's [misc] check; Any is, without needing cast().
    if _is_envelope(val):
        return pickle.loads(base64.b64decode(val[_PICKLE_KEY]))
    return val
