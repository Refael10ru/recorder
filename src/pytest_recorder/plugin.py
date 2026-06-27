"""pytest plugin: --recorder option; thin adapter that drives ProxyTracker."""

from pytest_recorder.proxy_tracking import (
    ProxyTracker,
    RecorderMode,
    _set_tracker,
    get_tracker,
)


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
    """Create the global ProxyTracker from the chosen mode."""
    _set_tracker(ProxyTracker(RecorderMode(config.getoption("--recorder"))))


def pytest_runtest_setup(item) -> None:
    """Reset tracker state for the test about to run."""
    get_tracker().begin_test(item.nodeid, item.path)


def pytest_runtest_teardown(item) -> None:
    """Flush or assert at the end of the test."""
    get_tracker().end_test()
