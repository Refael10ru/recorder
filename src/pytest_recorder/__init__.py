"""pytest-recorder: record/replay fixture mocking for system tests."""

from pytest_recorder.decorator import record
from pytest_recorder.targets import record_targets

__all__ = ["record", "record_targets"]
