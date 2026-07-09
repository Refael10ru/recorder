"""The @record(name) decorator: a thin off/record/play selector."""

import functools
from collections.abc import Callable

from pytest_recorder.engine import PlayerProxy, RecordingProxy
from pytest_recorder.proxy_tracking import RecorderMode, get_tracker


def record(name: str | Callable | None = None):
    """Wrap a fixture factory so its value is recorded or replayed by mode.

    ``name`` keys the recording. Defaults to the decorated function's name,
    so ``@record()`` (or bare ``@record``) on ``def pricing(): ...`` records
    under ``"pricing"``.
    """

    def deco(factory):
        fixture_name = name if name is not None else factory.__name__

        @functools.wraps(factory)
        def wrapper(*args, **kwargs):
            targets = get_tracker()
            if targets.mode == RecorderMode.OFF:
                yield factory(*args, **kwargs)
                return
            if targets.mode == RecorderMode.RECORD:
                yield RecordingProxy(
                    factory(*args, **kwargs), fixture_name, targets.current_store
                )
            else:  # play -- factory NOT called
                player = PlayerProxy(fixture_name, targets.current_store)
                targets.register_player(player)
                yield player

        return wrapper

    if callable(name):  # bare @record: name is the factory itself
        factory, name = name, None
        return deco(factory)
    return deco
