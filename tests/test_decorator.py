"""Tests for @record name resolution (default vs explicit)."""

import pytest

from pytest_recorder import plugin
from pytest_recorder.decorator import record


@pytest.fixture
def recording_controller(tmp_path, monkeypatch):
    ctrl = plugin.Controller("record")
    ctrl.begin_test("nodeid", tmp_path / "test_x.py")
    monkeypatch.setattr(plugin, "_CONTROLLER", ctrl)
    return ctrl


def test_default_name_uses_function_name(recording_controller) -> None:
    @record()
    def pricing():
        return lambda a, b: a + b

    gen = pricing()
    proxy = next(gen)
    assert proxy(2, 3) == 5
    gen.close()
    assert recording_controller.current_store().events("pricing")


def test_explicit_name_overrides_function_name(recording_controller) -> None:
    @record("custom")
    def pricing():
        return lambda a, b: a + b

    gen = pricing()
    proxy = next(gen)
    assert proxy(7, 0) == 7
    gen.close()
    store = recording_controller.current_store()
    assert store.events("custom")
    assert not store.events("pricing")
