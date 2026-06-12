"""pytest plugin: --recorder option, per-test controller, lifecycle hooks."""

from pytest_recorder.errors import MissingRecording
from pytest_recorder.storage import RecordingStore, resolve_recording_path

_CONTROLLER = None


def get_controller() -> "Controller":
    """Return the active Controller, or raise if the plugin is unconfigured."""
    if _CONTROLLER is None:
        msg = "recorder: plugin not configured"
        raise RuntimeError(msg)
    return _CONTROLLER


class Controller:
    """Holds recorder mode + per-test store; flushes/asserts at teardown."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self._nodeid = None
        self._test_file = None
        self._store = None
        self._players = []

    def begin_test(self, nodeid, test_file) -> None:
        """Reset per-test state at the start of each test."""
        self._nodeid = nodeid
        self._test_file = test_file
        self._store = None
        self._players = []

    def current_store(self) -> RecordingStore:
        """Lazily build (record) or load (play) this test's recording store."""
        if self._store is None:
            path = resolve_recording_path(self._nodeid, self._test_file)
            if self.mode == "play" and not path.exists():
                msg = (
                    f"recorder: no recording at {path}; "
                    "re-run with --recorder=record"
                )
                raise MissingRecording(msg)
            store = RecordingStore(path)
            if self.mode == "play":
                store.load()
            self._store = store
        return self._store

    def register_player(self, player) -> None:
        """Track a player so its full consumption can be asserted at teardown."""
        self._players.append(player)

    def end_test(self) -> None:
        """Flush recordings (record) or assert full consumption (play)."""
        if self.mode == "record" and self._store is not None:
            self._store.flush()
        elif self.mode == "play":
            for player in self._players:
                player.assert_consumed()


def pytest_addoption(parser) -> None:
    """Register the --recorder option."""
    parser.addoption(
        "--recorder",
        action="store",
        default="off",
        choices=["off", "record", "play"],
        help="recorder mode: off (default), record, or play",
    )


def pytest_configure(config) -> None:
    """Create the global Controller from the chosen mode."""
    global _CONTROLLER
    _CONTROLLER = Controller(config.getoption("--recorder"))


def pytest_runtest_setup(item) -> None:
    """Reset controller state for the test about to run."""
    get_controller().begin_test(item.nodeid, item.path)


def pytest_runtest_teardown(item) -> None:
    """Flush or assert at the end of the test."""
    get_controller().end_test()
