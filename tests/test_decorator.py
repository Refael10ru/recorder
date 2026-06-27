"""Tests for @record name resolution (default vs explicit)."""

import pytest

from pytest_recorder.decorator import record
from pytest_recorder.targets import RecordTargets


@pytest.fixture
def recording_targets(tmp_path):
    import pytest_recorder.targets as _mod

    prev = _mod._TARGETS
    t = RecordTargets("record")
    t.begin_test("nodeid", tmp_path / "test_x.py")
    _mod._TARGETS = t
    yield t
    _mod._TARGETS = prev


def test_default_name_uses_function_name(recording_targets) -> None:
    @record()
    def pricing():
        return lambda a, b: a + b

    gen = pricing()
    proxy = next(gen)
    assert proxy(2, 3) == 5
    gen.close()
    assert recording_targets.current_store().events("pricing")


def test_explicit_name_overrides_function_name(recording_targets) -> None:
    @record("custom")
    def pricing():
        return lambda a, b: a + b

    gen = pricing()
    proxy = next(gen)
    assert proxy(7, 0) == 7
    gen.close()
    store = recording_targets.current_store()
    assert store.events("custom")
    assert not store.events("pricing")
