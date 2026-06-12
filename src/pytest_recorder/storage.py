"""Recording file path resolution and per-test event store."""

import json
import re
from pathlib import Path


def resolve_recording_path(nodeid: str, root: Path) -> Path:
    """Map a pytest nodeid to its recording file under <root>/recordings/.

    Structural separators (``/`` between path segments and ``::`` between the
    module and test name) become ``__``; every other non-alphanumeric
    character becomes a single ``_``.
    """
    structural = nodeid.replace("/", "__").replace("::", "__")
    safe = re.sub(r"[^0-9A-Za-z_]", "_", structural)
    return Path(root) / "recordings" / f"{safe}.json"


class RecordingStore:
    """Holds {fixture_name: [event, ...]} for one test; loads/saves JSON."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._data: dict[str, list] = {}

    def append(self, name: str, event: dict) -> None:
        """Buffer one recorded event under a fixture name (record mode)."""
        self._data.setdefault(name, []).append(event)

    def events(self, name: str) -> list:
        """Return the recorded events for a fixture name (empty if none)."""
        return self._data.get(name, [])

    def load(self) -> None:
        """Read the recording file into memory."""
        with self.path.open() as fh:
            self._data = json.load(fh)

    def flush(self) -> None:
        """Write buffered events to the recording file as JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as fh:
            json.dump(self._data, fh, indent=2)
