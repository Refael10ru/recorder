"""Tests for the JSON-first serializer with base64-pickle fallback."""

import json

import numpy as np

from pytest_recorder.serialize import decode, encode


class P:
    """Module-level custom object so pickle can serialize it."""

    def __init__(self, x: object) -> None:
        """Store the wrapped value."""
        self.x = x

    def __eq__(self, o: object) -> bool:
        """Compare by wrapped value and type."""
        return isinstance(o, P) and o.x == self.x

    def __hash__(self) -> int:
        """Hash by wrapped value."""
        return hash(self.x)


def test_json_roundtrip_scalars_and_containers() -> None:
    """JSON-native values pass through encode/decode unchanged."""
    for obj in [1, "x", 3.5, True, None, [1, 2, {"a": 3}], {"k": [1, 2]}]:
        enc = encode(obj)
        # encoded value must be JSON-serializable as-is
        json.dumps(enc)
        assert decode(enc) == obj


def test_pickle_fallback_for_numpy() -> None:
    """Non-JSON values fall back to a JSON-safe base64-pickle envelope."""
    arr = np.array([1, 2, 3])
    enc = encode(arr)
    json.dumps(enc)  # must be JSON-safe
    assert isinstance(enc, dict)
    assert "__pickle__" in enc
    out = decode(enc)
    assert isinstance(out, np.ndarray)
    assert np.array_equal(out, arr)


def test_custom_object_roundtrip() -> None:
    """A custom object roundtrips via the pickle fallback."""
    enc = encode(P(5))
    assert decode(enc) == P(5)


def test_user_dict_colliding_with_pickle_sentinel_roundtrips() -> None:
    """A user dict that looks like an envelope is not misread on decode."""
    obj = {"__pickle__": "not really pickled"}
    enc = encode(obj)
    json.dumps(enc)  # still JSON-safe
    assert decode(enc) == obj


def test_nested_sentinel_dict_is_preserved() -> None:
    """A sentinel-shaped dict nested in a list is returned untouched."""
    obj = [{"__pickle__": "x"}, 1]
    assert decode(encode(obj)) == obj
