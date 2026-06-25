"""Recording file path resolution, event types, and per-test event store."""

import json
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, TypedDict

EncodedEvent = TypedDict(
    "EncodedEvent",
    {
        "method": str,
        "args": list[Any],
        "kwargs": dict[str, Any],
        "return": Any,
        "raised": Any,
    },
)


class StoreSource(ABC):
    """Contract for objects that supply a per-test RecordingStore to engine proxies.

    Lives in storage (not engine or interfaces) so the dependency arrow is clean:
    engine and plugin import from storage; storage imports nothing from recorder.

    Design note — future split:
    The ABC currently mixes two concerns:
      - test_id(): a test-boundary sensor used only by proxies to detect reloads
      - current_store() / register_player(): the outward store accessor used per call

    A cleaner split would have two separate protocols: one for boundary detection
    (held by proxies) and one for store access (called per method call). This would
    remove the need for RecordingStore to implement current_store() / register_player()
    at all (they exist only to satisfy this ABC). Tracked in api-improvements.md.
    """

    @abstractmethod
    def current_store(self) -> "RecordingStore":
        """Return the RecordingStore for the currently running test."""

    @abstractmethod
    def test_id(self) -> str:
        """Return an opaque equality token that changes when the active test changes.

        Proxies compare successive values to detect test boundaries and reload events.
        Must be stable within one test and distinct across tests. Not used for paths.
        """

    @abstractmethod
    def register_player(self, player: Any) -> None:
        """Register a player so its consumption can be verified at test end.

        Design note: in a flat recording model (one file, known fixture names at
        record time) this registry could be eliminated by checking at play time
        that all recorded fixture streams were fully consumed. The registry exists
        because fixture teardown happens at unpredictable times in pytest's
        collection order. Tracked in api-improvements.md.
        """


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
        self._data: dict[str, list[EncodedEvent]] = {}

    def append(self, name: str, event: EncodedEvent) -> None:
        """Buffer one recorded event under a fixture name (record mode)."""
        self._data.setdefault(name, []).append(event)

    def events(self, name: str) -> list[EncodedEvent]:
        """Return the recorded events for a fixture name (empty if none)."""
        return self._data.get(name, [])

    def load(self) -> None:
        """Read the recording file into memory."""
        with self.path.open() as fh:
            self._data = json.load(fh)

    def current_store(self) -> "RecordingStore":
        return self

    def test_id(self) -> str:
        # Fixed empty string — RecordingStore always holds one test's events.
        return ""

    def register_player(self, player: Any) -> None:
        pass  # Direct-store callers call player.assert_consumed() themselves.

    def flush(self) -> None:
        """Write buffered events to the recording file as JSON."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as fh:
            json.dump(self._data, fh, indent=2)
