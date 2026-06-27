"""Recording file path resolution, event types, and per-test event store."""

import dataclasses
import json
import re
from pathlib import Path
from typing import Any


@dataclasses.dataclass(slots=True)
class EncodedEvent:
    """One recorded call in its serialized (JSON-safe) form.

    ``result`` holds the encoded return value; ``raised`` holds an encoded
    exception envelope. Exactly one is non-None per event.

    Named ``result`` (not ``return``) because ``return`` is a Python keyword
    and cannot be a dataclass field name.
    """

    method: str
    args: list[Any]
    kwargs: dict[str, Any]
    result: Any
    raised: Any


def resolve_recording_path(nodeid: str, test_file: Path) -> Path:
    """Map a pytest nodeid to its recording file beside the test module.

    Recordings live in a ``recordings/`` directory next to the test file, so
    they travel with the test when it is copied or moved. The filename keys on
    the module stem plus the test portion of the nodeid (everything after
    ``::``); every non-alphanumeric character becomes a single ``_``.
    """
    test_file = Path(test_file)
    _, _, test_part = nodeid.partition("::")
    key = f"{test_file.stem}__{test_part}" if test_part else nodeid
    safe = re.sub(r"[^0-9A-Za-z_]", "_", key)
    return test_file.parent / "recordings" / f"{safe}.json"


class RecordingStore:
    """Holds {stream_name: [EncodedEvent, ...]} for one test; loads/saves JSON."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._data: dict[str, list[EncodedEvent]] = {}

    def append(self, name: str, event: EncodedEvent) -> None:
        """Buffer one recorded event under a stream name (record mode)."""
        self._data.setdefault(name, []).append(event)

    def events(self, name: str) -> list[EncodedEvent]:
        """Return the recorded events for a stream name (empty if none)."""
        return self._data.get(name, [])

    def load(self) -> None:
        """Read the recording file into memory."""
        with self.path.open() as fh:
            raw: dict[str, list[dict[str, Any]]] = json.load(fh)
        self._data = {
            name: [EncodedEvent(**ev) for ev in evs]
            for name, evs in raw.items()
        }

    def flush(self) -> None:
        """Write buffered events to the recording file as JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {
            name: [dataclasses.asdict(ev) for ev in evs]
            for name, evs in self._data.items()
        }
        with self.path.open("w") as fh:
            json.dump(raw, fh, indent=2)
