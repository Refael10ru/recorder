import pytest

from pytest_recorder.engine import PlayerProxy, RecordingProxy
from pytest_recorder.errors import (
    RecordingExhausted,
    RecordingMismatch,
    RecordingUnderused,
)
from pytest_recorder.storage import RecordingStore


class Calc:
    def add(self, a, b):
        return a + b

    def boom(self):
        raise ValueError("nope")


def test_recording_proxy_records_method_call(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(Calc(), "calc", store)
    assert proxy.add(2, 3) == 5
    ev = store.events("calc")[0]
    assert ev["method"] == "add"
    assert ev["args"] == [2, 3]
    assert ev["return"] == 5
    assert ev["raised"] is None


def test_recording_proxy_records_callable(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(lambda x: x * 2, "double", store)
    assert proxy(4) == 8
    assert store.events("double")[0]["method"] == "__call__"


def test_recording_proxy_records_and_reraises_exception(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(Calc(), "calc", store)
    with pytest.raises(ValueError):
        proxy.boom()
    ev = store.events("calc")[0]
    assert ev["return"] is None
    assert ev["raised"] is not None


def _recorded_store(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    proxy = RecordingProxy(Calc(), "calc", store)
    proxy.add(2, 3)
    store.flush()
    loaded = RecordingStore(tmp_path / "r.json")
    loaded.load()
    return loaded


def test_player_replays_return(tmp_path):
    store = _recorded_store(tmp_path)
    player = PlayerProxy("calc", store)
    assert player.add(2, 3) == 5
    player.assert_consumed()


def test_player_mismatch_on_wrong_args(tmp_path):
    store = _recorded_store(tmp_path)
    player = PlayerProxy("calc", store)
    with pytest.raises(RecordingMismatch):
        player.add(9, 9)


def test_player_exhausted_on_extra_call(tmp_path):
    store = _recorded_store(tmp_path)
    player = PlayerProxy("calc", store)
    player.add(2, 3)
    with pytest.raises(RecordingExhausted):
        player.add(2, 3)


def test_player_underused_when_events_left(tmp_path):
    store = _recorded_store(tmp_path)
    player = PlayerProxy("calc", store)
    with pytest.raises(RecordingUnderused):
        player.assert_consumed()


def test_player_replays_exception(tmp_path):
    store = RecordingStore(tmp_path / "r.json")
    rec = RecordingProxy(Calc(), "calc", store)
    with pytest.raises(ValueError):
        rec.boom()
    store.flush()
    loaded = RecordingStore(tmp_path / "r.json")
    loaded.load()
    player = PlayerProxy("calc", loaded)
    with pytest.raises(ValueError):
        player.boom()
