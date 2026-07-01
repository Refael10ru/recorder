from pathlib import Path

from pytest_recorder.storage import (
    EncodedEvent,
    RecordingStore,
    resolve_recording_path,
)


def test_resolve_path_is_beside_test_file():
    test_file = Path("/proj/tests/mockproj/test_depth.py")
    p = resolve_recording_path("tests/mockproj/test_depth.py::test_add[1]", test_file)
    assert p == test_file.parent / "recordings" / "test_depth__test_add_1_.json"


def test_encoded_event_is_dataclass() -> None:
    ev = EncodedEvent(method="add", args=[1], kwargs={}, result=1, raised=None)
    assert ev.method == "add"
    assert ev.result == 1


def test_store_append_flush_load(tmp_path):
    path = tmp_path / "rec.json"
    s = RecordingStore(path)
    s.append(
        "calc",
        EncodedEvent(method="add", args=[1, 2], kwargs={}, result=3, raised=None),
    )
    s.flush()
    assert path.exists()

    s2 = RecordingStore(path)
    s2.load()
    assert s2.events("calc")[0].result == 3
    assert s2.events("missing") == []
