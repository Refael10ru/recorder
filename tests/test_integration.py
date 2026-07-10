"""End-to-end record/play of the testbed via subprocess pytest runs."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOCK = REPO / "tests" / "mockproj"


def _copy_mock(dst: Path) -> Path:
    shutil.copytree(MOCK, dst)
    rec = dst / "recordings"
    if rec.exists():
        shutil.rmtree(rec)
    return dst


def _run(target: Path, mode: str, *extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "RECORDER_MODE": mode}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            str(target),
            f"--recorder={mode}",
            "-q",
            *extra,
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO,
        check=False,
    )


def test_record_then_play_passes(tmp_path):
    mock = _copy_mock(tmp_path / "mockproj")
    rec = _run(mock, "record")
    assert rec.returncode == 0, rec.stdout + rec.stderr
    # recordings were generated beside the copied test file
    assert (mock / "recordings").is_dir()
    assert list((mock / "recordings").glob("*.json"))
    play = _run(mock, "play")
    assert play.returncode == 0, play.stdout + play.stderr


def test_xdist_record_then_play(tmp_path):
    # Multi-worker support: recordings are one file per test, so parallel
    # workers never contend on the same file.
    mock = _copy_mock(tmp_path / "mockproj")
    rec = _run(mock, "record", "-n", "2")
    assert rec.returncode == 0, rec.stdout + rec.stderr
    assert list((mock / "recordings").glob("*.json"))
    play = _run(mock, "play", "-n", "2")
    assert play.returncode == 0, play.stdout + play.stderr


def test_mutation_triggers_mismatch(tmp_path):
    mock = _copy_mock(tmp_path / "mockproj")
    assert _run(mock, "record").returncode == 0
    test_file = mock / "test_depth.py"
    mutated = test_file.read_text().replace("adder(2, 3) == 5", "adder(2, 4) == 6")
    test_file.write_text(mutated)
    play = _run(mock, "play", "-k", "pure_callable_returns")
    assert play.returncode != 0, "mutated call should fail in play"
    assert "RecordingMismatch" in (play.stdout + play.stderr)


def test_off_mode_runs_real_objects_and_records_nothing(tmp_path):
    mock = _copy_mock(tmp_path / "mockproj")
    res = _run(mock, "off")
    assert res.returncode == 0, res.stdout + res.stderr
    assert not (mock / "recordings").exists()


def test_play_without_recording_raises_missing(tmp_path):
    mock = _copy_mock(tmp_path / "mockproj")  # recordings stripped by _copy_mock
    play = _run(mock, "play", "-k", "flat_object")
    assert play.returncode != 0, "play with no recording should fail"
    assert "MissingRecording" in (play.stdout + play.stderr)


def test_extra_call_triggers_exhausted(tmp_path):
    mock = _copy_mock(tmp_path / "mockproj")
    assert _run(mock, "record").returncode == 0
    test_file = mock / "test_depth.py"
    mutated = test_file.read_text().replace(
        "assert adder(10, 20) == 30",
        "assert adder(10, 20) == 30\n    assert adder(1, 1) == 2",
    )
    test_file.write_text(mutated)
    play = _run(mock, "play", "-k", "pure_callable_returns")
    assert play.returncode != 0, "extra call should fail in play"
    assert "RecordingExhausted" in (play.stdout + play.stderr)


def test_removed_call_triggers_underused(tmp_path):
    mock = _copy_mock(tmp_path / "mockproj")
    assert _run(mock, "record").returncode == 0
    test_file = mock / "test_depth.py"
    mutated = test_file.read_text().replace("assert adder(10, 20) == 30", "pass")
    test_file.write_text(mutated)
    play = _run(mock, "play", "-k", "pure_callable_returns")
    assert play.returncode != 0, "missing call should fail in play"
    assert "RecordingUnderused" in (play.stdout + play.stderr)
