import pytest

from pytest_recorder.engine import RecordingProxy
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
