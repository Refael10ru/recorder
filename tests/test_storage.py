from pathlib import Path

from pytest_recorder.storage import RecordingStore, resolve_recording_path


def test_resolve_path_sanitizes_nodeid():
    root = Path("/proj")
    p = resolve_recording_path("tests/mockproj/test_depth.py::test_add[1]", root)
    assert p == root / "recordings" / "tests__mockproj__test_depth_py__test_add_1_.json"


def test_store_append_flush_load(tmp_path):
    path = tmp_path / "rec.json"
    s = RecordingStore(path)
    s.append(
        "calc",
        {"method": "add", "args": [1, 2], "kwargs": {}, "return": 3, "raised": None},
    )
    s.flush()
    assert path.exists()

    s2 = RecordingStore(path)
    s2.load()
    assert s2.events("calc")[0]["return"] == 3
    assert s2.events("missing") == []
