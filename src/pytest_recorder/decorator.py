"""The @record(name) decorator: a thin off/record/play selector."""

import functools

from pytest_recorder.engine import PlayerProxy, RecordingProxy
from pytest_recorder.plugin import get_controller


def record(name):
    """Wrap a fixture factory so its value is recorded or replayed by mode."""

    def deco(factory):
        @functools.wraps(factory)
        def wrapper(*args, **kwargs):
            ctrl = get_controller()
            if ctrl.mode == "off":
                yield factory(*args, **kwargs)
                return
            store = ctrl.current_store()
            if ctrl.mode == "record":
                yield RecordingProxy(factory(*args, **kwargs), name, store)
            else:  # play -- factory NOT called
                player = PlayerProxy(name, store)
                ctrl.register_player(player)
                yield player

        return wrapper

    return deco
