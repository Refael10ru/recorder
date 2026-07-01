import numpy as np
import pytest

from pytest_recorder.engine import PlayerProxy, RecordingProxy, is_recorder_mock
from pytest_recorder.errors import (
    RecordingExhausted,
    RecordingMismatch,
    RecordingUnderused,
)
from pytest_recorder.proxy_tracking import ProxyTracker, RecorderMode
from pytest_recorder.storage import RecordingStore, resolve_recording_path


class _BadPickleError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__()
        self.code = code


_FAKE_FILE = "fake_test.py"


class Calc:
    def add(self, a, b):
        return a + b

    def boom(self):
        raise ValueError("nope")

    def bad_boom(self) -> None:
        raise _BadPickleError(401)

    def first(self, arr):
        return int(arr[0])


def test_recording_proxy_records_method_call(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(Calc(), "calc", lambda: store)
    assert proxy.add(2, 3) == 5
    ev = store.events("calc")[0]
    assert ev.method == "add"
    assert ev.args == [2, 3]
    assert ev.result == 5
    assert ev.raised is None


def test_recording_proxy_records_callable(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(lambda x: x * 2, "double", lambda: store)
    assert proxy(4) == 8
    assert store.events("double")[0].method == "__call__"


def test_recording_proxy_records_and_reraises_exception(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(Calc(), "calc", lambda: store)
    with pytest.raises(ValueError):
        proxy.boom()
    ev = store.events("calc")[0]
    assert ev.result is None
    assert ev.raised is not None


def _recorded_store(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(Calc(), "calc", lambda: store)
    proxy.add(2, 3)
    store.flush()
    loaded = RecordingStore(tmp_path / "r.json")
    loaded.load()
    return loaded


def test_player_replays_return(tmp_path):
    store = _recorded_store(tmp_path)
    player = PlayerProxy("calc", lambda: store)
    assert player.add(2, 3) == 5
    player.assert_consumed()


def test_player_mismatch_on_wrong_args(tmp_path):
    store = _recorded_store(tmp_path)
    player = PlayerProxy("calc", lambda: store)
    with pytest.raises(RecordingMismatch):
        player.add(9, 9)


def test_player_exhausted_on_extra_call(tmp_path):
    store = _recorded_store(tmp_path)
    player = PlayerProxy("calc", lambda: store)
    player.add(2, 3)
    with pytest.raises(RecordingExhausted):
        player.add(2, 3)


def test_player_underused_when_events_left(tmp_path):
    store = _recorded_store(tmp_path)
    player = PlayerProxy("calc", lambda: store)
    with pytest.raises(RecordingUnderused):
        player.assert_consumed()


def test_player_matches_numpy_array_arg(tmp_path):
    # Regression: a pickle-fallback arg (numpy array) must match in play without
    # raising "truth value of an array is ambiguous".
    store = RecordingStore(tmp_path / "r.json")
    rec = RecordingProxy(Calc(), "calc", lambda: store)
    rec.first(np.array([10, 20, 30]))
    store.flush()
    loaded = RecordingStore(tmp_path / "r.json")
    loaded.load()
    player = PlayerProxy("calc", lambda: loaded)
    assert player.first(np.array([10, 20, 30])) == 10
    player.assert_consumed()


def test_player_mismatch_on_different_numpy_arg(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    rec = RecordingProxy(Calc(), "calc", lambda: store)
    rec.first(np.array([10, 20, 30]))
    store.flush()
    loaded = RecordingStore(tmp_path / "r.json")
    loaded.load()
    player = PlayerProxy("calc", lambda: loaded)
    with pytest.raises(RecordingMismatch):
        player.first(np.array([99, 20, 30]))


def test_is_recorder_mock_recording_proxy(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(Calc(), "calc", lambda: store)
    assert proxy.__is_recorder_mock__() is True
    assert is_recorder_mock(proxy) is True


def test_is_recorder_mock_player_proxy(tmp_path):
    store = _recorded_store(tmp_path)
    player = PlayerProxy("calc", lambda: store)
    assert player.__is_recorder_mock__() is True
    assert is_recorder_mock(player) is True


def test_is_recorder_mock_plain_object():
    assert is_recorder_mock(Calc()) is False
    assert is_recorder_mock(object()) is False
    assert is_recorder_mock(42) is False


def test_recording_fails_loudly_for_non_picklable_exception(tmp_path):
    # FIN-1: record must raise RuntimeError immediately, not store a bad pickle.
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(Calc(), "calc", lambda: store)
    with pytest.raises(RuntimeError, match="cannot record"):
        proxy.bad_boom()


def test_recording_proxy_routes_each_test_to_its_own_store(tmp_path):
    # SCP-1 record: proxy must write to the current test's store on each call.
    targets = ProxyTracker(RecorderMode.RECORD)
    fp = tmp_path / _FAKE_FILE

    targets.begin_test(f"{_FAKE_FILE}::test_one", fp)
    proxy = RecordingProxy(Calc(), "calc", targets.current_store)
    proxy.add(1, 2)
    targets.end_test()

    targets.begin_test(f"{_FAKE_FILE}::test_two", fp)
    proxy.add(3, 4)
    targets.end_test()

    p1 = resolve_recording_path(f"{_FAKE_FILE}::test_one", fp)
    p2 = resolve_recording_path(f"{_FAKE_FILE}::test_two", fp)
    s1, s2 = RecordingStore(p1), RecordingStore(p2)
    s1.load()
    s2.load()
    assert [e.args for e in s1.events("calc")] == [[1, 2]]
    assert [e.args for e in s2.events("calc")] == [[3, 4]]


def test_player_proxy_reloads_events_on_test_boundary(tmp_path):
    # SCP-1 play: same player instance must serve correct events per test.
    fp = tmp_path / _FAKE_FILE
    cases = [(f"{_FAKE_FILE}::test_one", 1, 2), (f"{_FAKE_FILE}::test_two", 3, 4)]
    for nodeid, a, b in cases:
        s = RecordingStore(resolve_recording_path(nodeid, fp))
        rec = RecordingProxy(Calc(), "calc", lambda _s=s: _s)
        rec.add(a, b)
        s.flush()

    targets = ProxyTracker(RecorderMode.PLAY)
    targets.begin_test(f"{_FAKE_FILE}::test_one", fp)
    player = PlayerProxy("calc", targets.current_store)
    assert player.add(1, 2) == 3
    player.assert_consumed()
    targets.end_test()

    targets.begin_test(f"{_FAKE_FILE}::test_two", fp)
    assert player.add(3, 4) == 7
    player.assert_consumed()
    targets.end_test()


def test_player_replays_exception(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    rec = RecordingProxy(Calc(), "calc", lambda: store)
    with pytest.raises(ValueError):
        rec.boom()
    store.flush()
    loaded = RecordingStore(tmp_path / "r.json")
    loaded.load()
    player = PlayerProxy("calc", lambda: loaded)
    with pytest.raises(ValueError):
        player.boom()
