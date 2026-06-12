from pathlib import Path

from pytest_recorder.storage import resolve_recording_path


def test_resolve_path_sanitizes_nodeid():
    root = Path("/proj")
    p = resolve_recording_path("tests/mockproj/test_depth.py::test_add[1]", root)
    assert p == root / "recordings" / "tests__mockproj__test_depth_py__test_add_1_.json"
