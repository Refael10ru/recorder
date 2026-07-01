"""Tests for @record name resolution (default vs explicit)."""

import pytest

import pytest_recorder.proxy_tracking as _mod
from pytest_recorder.decorator import record
from pytest_recorder.proxy_tracking import ProxyTracker, RecorderMode


@pytest.fixture
def recording_targets(tmp_path):
    prev = _mod._TRACKER
    t = ProxyTracker(RecorderMode.RECORD)
    t.begin_test("nodeid", tmp_path / "test_x.py")
    _mod._TRACKER = t
    yield t
    _mod._TRACKER = prev


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
