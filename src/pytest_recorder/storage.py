"""Recording file path resolution and per-test event store."""

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from pytest_recorder.interfaces import StoreSource

if TYPE_CHECKING:
    from pytest_recorder.engine import PlayerProxy


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


class RecordingStore(StoreSource):
    """Holds {fixture_name: [event, ...]} for one test; loads/saves JSON."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._data: dict[str, list[dict]] = {}

    def append(self, name: str, event: dict) -> None:
        """Buffer one recorded event under a fixture name (record mode)."""
        self._data.setdefault(name, []).append(event)

    def events(self, name: str) -> list[dict]:
        """Return the recorded events for a fixture name (empty if none)."""
        return self._data.get(name, [])

    def load(self) -> None:
        """Read the recording file into memory."""
        with self.path.open() as fh:
            self._data = json.load(fh)

    def current_store(self) -> "RecordingStore":
        return self

    def test_id(self) -> object:
        # WHY: return self so the proxy's _last_test_id stays equal across calls
        # (same store object → same identity) → no spurious reload after the first.
        return self

    def register_player(self, player: "PlayerProxy") -> None:
        pass  # WHY: no-op — RecordingStore has no per-test lifecycle; callers that
        # use RecordingStore directly call player.assert_consumed() themselves.

    def flush(self) -> None:
        """Write buffered events to the recording file as JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as fh:
            json.dump(self._data, fh, indent=2)
