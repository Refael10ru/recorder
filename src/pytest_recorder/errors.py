"""Exception types raised by the recorder during play."""


class RecorderError(Exception):
    """Base for all recorder errors."""


class MissingRecording(RecorderError):
    """Play mode: no recording file for this test."""


class RecordingExhausted(RecorderError):
    """Play mode: a live call occurred after the recording ran out."""


class RecordingUnderused(RecorderError):
    """Play mode: the test consumed fewer events than were recorded."""


class RecordingMismatch(RecorderError):
    """Play mode: live (method, args, kwargs) != next recorded event."""
