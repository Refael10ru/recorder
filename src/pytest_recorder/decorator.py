"""The @record(name) decorator: a thin off/record/play selector."""

import functools

from pytest_recorder.engine import PlayerProxy, RecordingProxy
from pytest_recorder.targets import get_targets


def record(name: str | None = None):
    """Wrap a fixture factory so its value is recorded or replayed by mode.

    ``name`` keys the recording. Defaults to the decorated function's name,
    so ``@record()`` on ``def pricing(): ...`` records under ``"pricing"``.
    """

    def deco(factory):
        fixture_name = name if name is not None else factory.__name__

        @functools.wraps(factory)
        def wrapper(*args, **kwargs):
            targets = get_targets()
            if targets.mode == "off":
                yield factory(*args, **kwargs)
                return
            if targets.mode == "record":
                yield RecordingProxy(
                    factory(*args, **kwargs), fixture_name, targets.current_store
                )
            else:  # play -- factory NOT called
                player = PlayerProxy(fixture_name, targets.current_store)
                targets.register_player(player)
                yield player

        return wrapper

    return deco
