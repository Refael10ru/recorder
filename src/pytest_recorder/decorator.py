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
                # WHY: pass ctrl not ctrl.current_store() — the latter locks the proxy
                # to the store of whichever test is running at fixture-creation time.
                # For non-function-scope fixtures that outlive one test this is wrong:
                # T2's calls land in T1's recording. Passing ctrl lets the proxy call
                # ctrl.current_store() per call, always getting the right file.
                yield RecordingProxy(factory(*args, **kwargs), fixture_name, ctrl)
            else:  # play -- factory NOT called
                # WHY: same rationale — PlayerProxy self-registers via _maybe_reload on
                # each test boundary, so no explicit register_player call needed here.
                yield PlayerProxy(fixture_name, ctrl)

        return wrapper

    return deco
