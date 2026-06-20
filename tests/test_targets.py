"""Tests for record_class: monkeypatch-style record/replay by import path."""

import contextlib

import pytest

from pytest_recorder import plugin
from tests import _targetmod

TARGET = "tests._targetmod.Dependency"


@pytest.fixture
def install_controller(tmp_path, monkeypatch):
    """Install a Controller of a given mode that shares one recording path.

    Returns a context manager factory so a single test can record under one
    controller, then replay under another against the same recording file.
    """
    rec_path = tmp_path / "test_x.py"

    @contextlib.contextmanager
    def factory(mode):
        ctrl = plugin.Controller(mode)
        ctrl.begin_test("nodeid", rec_path)
        monkeypatch.setattr(plugin, "_CONTROLLER", ctrl)
        yield ctrl
        ctrl.end_test()

    return factory


def test_record_then_play_roundtrip(install_controller):
    from pytest_recorder import record_class

    with install_controller("record"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"

    with install_controller("play"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"


def test_play_does_not_build_real_object(install_controller, monkeypatch):
    from pytest_recorder import record_class

    with install_controller("record"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"

    # Break the real dependency: play must serve the recording, never call this.
    def boom(self, host):
        raise AssertionError("real Dependency must not be constructed in play")

    monkeypatch.setattr(_targetmod.Dependency, "__init__", boom)

    with install_controller("play"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"


def test_constructor_args_key_instances_independently(install_controller):
    from pytest_recorder import record_class

    with install_controller("record"), record_class(TARGET):
        assert _targetmod.run("alpha", "k") == "alpha:k"
        assert _targetmod.run("beta", "k") == "beta:k"

    # Replay in the opposite construction order: matched by ctor args, not order.
    with install_controller("play"), record_class(TARGET):
        assert _targetmod.run("beta", "k") == "beta:k"
        assert _targetmod.run("alpha", "k") == "alpha:k"


def test_off_mode_is_a_noop(install_controller):
    from pytest_recorder import record_class

    with install_controller("off"), record_class(TARGET):
        # real symbol untouched -> real Dependency runs, nothing recorded
        assert _targetmod.Dependency("x").fetch("y") == "x:y"


def test_decorator_form_wraps_body(install_controller):
    from pytest_recorder import record_class

    @record_class(TARGET)
    def body():
        return _targetmod.run("prod", "k1")

    with install_controller("record"):
        assert body() == "prod:k1"
    with install_controller("play"):
        assert body() == "prod:k1"


def test_symbols_restored_after_exception(install_controller):
    from pytest_recorder import record_class

    original = _targetmod.Dependency
    with (
        install_controller("record"),
        pytest.raises(RuntimeError),
        record_class(TARGET),
    ):
        assert _targetmod.Dependency is not original  # patched inside block
        raise RuntimeError("boom")
    assert _targetmod.Dependency is original  # restored despite the exception


def test_play_underuse_raises_at_block_exit(install_controller):
    from pytest_recorder import record_class
    from pytest_recorder.errors import RecordingUnderused

    with install_controller("record"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"

    with (
        install_controller("play"),
        pytest.raises(RecordingUnderused),
        record_class(TARGET),
    ):
        # build the instance but never call the recorded fetch
        _targetmod.Dependency("prod")
