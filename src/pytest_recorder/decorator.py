"""The @record(name) decorator: a thin off/record/play selector."""

import functools

from pytest_recorder.engine import PlayerProxy, RecordingProxy
from pytest_recorder.plugin import get_controller


def record(name: str | None = None):
    """Wrap a fixture factory so its value is recorded or replayed by mode.

    ``name`` keys the recording. Defaults to the decorated function's name,
    so ``@record()`` on ``def pricing(): ...`` records under ``"pricing"``.
    """

    def deco(factory):
        fixture_name = name if name is not None else factory.__name__

        @functools.wraps(factory)
        def wrapper(*args, **kwargs):
            ctrl = get_controller()
            if ctrl.mode == "off":
                yield factory(*args, **kwargs)
                return
            if ctrl.mode == "record":
                # WHY: pass ctrl not ctrl.current_store() — ctrl.current_store()
                # is called per method call so each test gets its own store (SCP-1).
                yield RecordingProxy(factory(*args, **kwargs), fixture_name, ctrl)
            else:  # play -- factory NOT called
                player = PlayerProxy(fixture_name, ctrl)
                yield player

        return wrapper

    return deco
