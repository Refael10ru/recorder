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


def test_record_class_play_never_builds_real_object(tmp_path):
    mock = _copy_mock(tmp_path / "mockproj")
    assert _run(mock, "record").returncode == 0
    # Break the real class: play must serve recordings, never construct it.
    objects = mock / "objects.py"
    sabotaged = objects.read_text().replace(
        "class Calculator:",
        "class Calculator:\n"
        '    def __init__(self):\n'
        '        raise AssertionError("real Calculator built in play")',
    )
    objects.write_text(sabotaged)
    play = _run(mock, "play", "-k", "record_class")
    assert play.returncode == 0, play.stdout + play.stderr


def test_record_function_play_never_calls_real(tmp_path):
    mock = _copy_mock(tmp_path / "mockproj")
    assert _run(mock, "record").returncode == 0
    # Break the real function: play must serve the recorded return value.
    objects = mock / "objects.py"
    sabotaged = objects.read_text().replace(
        "def add(a, b):",
        'def add(a, b):\n    raise AssertionError("real add called in play")',
    )
    objects.write_text(sabotaged)
    play = _run(mock, "play", "-k", "record_function")
    assert play.returncode == 0, play.stdout + play.stderr


def test_removed_call_triggers_underused(tmp_path):
    mock = _copy_mock(tmp_path / "mockproj")
    assert _run(mock, "record").returncode == 0
    test_file = mock / "test_depth.py"
    mutated = test_file.read_text().replace("assert adder(10, 20) == 30", "pass")
    test_file.write_text(mutated)
    play = _run(mock, "play", "-k", "pure_callable_returns")
    assert play.returncode != 0, "missing call should fail in play"
    assert "RecordingUnderused" in (play.stdout + play.stderr)
