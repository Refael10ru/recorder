"""Tests for record_class: monkeypatch-style record/replay by import path."""

import contextlib

import pytest

from pytest_recorder.targets import RecordTargets
from tests import _targetmod

TARGET = "tests._targetmod.Dependency"


@pytest.fixture
def install_targets(tmp_path):
    """Install a RecordTargets of a given mode sharing one recording path.

    Returns a context manager factory so a single test can record under one
    targets instance, then replay under another against the same recording file.
    """
    import pytest_recorder.targets as _mod

    rec_path = tmp_path / "test_x.py"

    @contextlib.contextmanager
    def factory(mode):
        prev = _mod._TARGETS
        t = RecordTargets(mode)
        t.begin_test("nodeid", rec_path)
        _mod._TARGETS = t
        try:
            yield t
            t.end_test()
        finally:
            # Restore before pytest_runtest_teardown runs so the plugin hook
            # calls end_test on the real session targets, not this test instance.
            _mod._TARGETS = prev

    return factory


def test_record_then_play_roundtrip(install_targets):
    from pytest_recorder import record_class

    with install_targets("record"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"

    with install_targets("play"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"


def test_play_does_not_build_real_object(install_targets, monkeypatch):
    from pytest_recorder import record_class

    with install_targets("record"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"

    # Break the real dependency: play must serve the recording, never call this.
    def boom(self, host):
        raise AssertionError("real Dependency must not be constructed in play")

    monkeypatch.setattr(_targetmod.Dependency, "__init__", boom)

    with install_targets("play"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"


def test_constructor_args_key_instances_independently(install_targets):
    from pytest_recorder import record_class

    with install_targets("record"), record_class(TARGET):
        assert _targetmod.run("alpha", "k") == "alpha:k"
        assert _targetmod.run("beta", "k") == "beta:k"

    # Replay in the opposite construction order: matched by ctor args, not order.
    with install_targets("play"), record_class(TARGET):
        assert _targetmod.run("beta", "k") == "beta:k"
        assert _targetmod.run("alpha", "k") == "alpha:k"


def test_off_mode_is_a_noop(install_targets):
    from pytest_recorder import record_class

    with install_targets("off"), record_class(TARGET):
        # real symbol untouched -> real Dependency runs, nothing recorded
        assert _targetmod.Dependency("x").fetch("y") == "x:y"


def test_decorator_form_wraps_body(install_targets):
    from pytest_recorder import record_class

    @record_class(TARGET)
    def body():
        return _targetmod.run("prod", "k1")

    with install_targets("record"):
        assert body() == "prod:k1"
    with install_targets("play"):
        assert body() == "prod:k1"


def test_symbols_restored_after_exception(install_targets):
    from pytest_recorder import record_class

    original = _targetmod.Dependency
    with (
        install_targets("record"),
        pytest.raises(RuntimeError),
        record_class(TARGET),
    ):
        assert _targetmod.Dependency is not original  # patched inside block
        raise RuntimeError("boom")
    assert _targetmod.Dependency is original  # restored despite the exception


def test_play_underuse_raises_at_test_end(install_targets):
    # Underuse is detected at end_test (not __exit__) so teardown method calls
    # are included in the recording window.
    from pytest_recorder import record_class
    from pytest_recorder.errors import RecordingUnderused

    with install_targets("record"), record_class(TARGET):
        assert _targetmod.run("prod", "k1") == "prod:k1"

    with (
        pytest.raises(RecordingUnderused),
        install_targets("play"),
        record_class(TARGET),
    ):
        # build the instance but never call the recorded fetch
        _targetmod.Dependency("prod")
    # install_targets.__exit__ calls t.end_test() which raises RecordingUnderused,
    # propagates up through record_class (which doesn't suppress it) to pytest.raises.
