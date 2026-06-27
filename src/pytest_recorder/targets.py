"""record_class / record_function: monkeypatch by import path for a test.

``record_class`` is for **class/factory** symbols: the constructed instance is
wrapped in a proxy so method calls on it are also recorded.

``record_function`` is for **plain callable** symbols (functions, builtins,
methods): the call itself is recorded and the real return value is passed
through unchanged.  Use this for module-level APIs like ``wikipedia.search``.

``RecordTargets`` is the global lifecycle object for this module — it owns
recorder mode, the per-test store, and the player registry. ``plugin.py``
creates it at session start and calls ``begin_test`` / ``end_test`` around
each test.
"""

import functools
import importlib
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

from pytest_recorder.engine import PlayerProxy, RecordingProxy
from pytest_recorder.errors import MissingRecording
from pytest_recorder.serialize import _encode_call
from pytest_recorder.storage import RecordingStore, resolve_recording_path

_TARGETS: "RecordTargets | None" = None


def get_targets() -> "RecordTargets":
    """Return the active RecordTargets, or raise if the plugin is unconfigured."""
    if _TARGETS is None:
        msg = "recorder: targets not configured"
        raise RuntimeError(msg)
    return _TARGETS


def _set_targets(t: "RecordTargets") -> None:
    global _TARGETS
    _TARGETS = t


class RecordTargets:
    """Global lifecycle manager: recorder mode, per-test store, player registry.

    ``plugin.py`` creates one instance per session and wires pytest hooks to
    call ``begin_test`` / ``end_test``. ``record_class`` / ``record_function``
    and ``decorator.record`` all call ``get_targets()`` to reach this object.

    Assertion of player consumption happens at ``end_test`` (not at block
    ``__exit__``) so that fixture teardown calls — which happen after the
    test body exits — are included in the recording window.
    """

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self._nodeid: str | None = None
        self._test_file: Path | None = None
        self._store: RecordingStore | None = None
        self._players: list[Any] = []

    def begin_test(self, nodeid: str, test_file: Path) -> None:
        """Reset per-test state at the start of each test."""
        self._nodeid = nodeid
        self._test_file = test_file
        self._store = None
        self._players = []

    def current_store(self) -> RecordingStore:
        """Lazily build (record) or load (play) this test's recording store."""
        if self._store is None:
            if self._nodeid is None or self._test_file is None:
                msg = "recorder: current_store called outside a running test"
                raise RuntimeError(msg)
            path = resolve_recording_path(self._nodeid, self._test_file)
            if self.mode == "play" and not path.exists():
                msg = f"recorder: no recording at {path}; re-run with --recorder=record"
                raise MissingRecording(msg)
            store = RecordingStore(path)
            if self.mode == "play":
                store.load()
            self._store = store
        return self._store

    def register_player(self, player: Any) -> None:
        """Track a player so its full consumption can be asserted at end_test."""
        self._players.append(player)

    def end_test(self) -> None:
        """Flush recordings (record) or assert full consumption (play)."""
        if self.mode == "record" and self._store is not None:
            self._store.flush()
        elif self.mode == "play":
            for player in self._players:
                player.assert_consumed()


def _resolve(path: str) -> tuple[ModuleType, str]:
    """Split ``pkg.mod.Name`` into the imported module and the attribute name."""
    module_path, _, attr = path.rpartition(".")
    return importlib.import_module(module_path), attr


def _base_key(path: str, args: tuple, kwargs: dict) -> str:
    """Stable stream key for one construction: path + encoded constructor args."""
    enc_args, enc_kwargs = _encode_call(args, kwargs)
    sig = json.dumps([enc_args, enc_kwargs], sort_keys=True)
    return f"{path}({sig})"


class record_class:
    """Patch each import path for the enclosed block; usable as a decorator.

    Named in lowercase because it reads as a verb at call sites and doubles as a
    context manager and decorator, like ``contextlib.suppress``.
    """

    def __init__(self, *paths: str) -> None:
        self._paths = paths
        self._patches: list[tuple[ModuleType, str, object]] = []
        self._counters: dict[str, int] = {}

    def __enter__(self) -> "record_class":
        self._patches = []
        self._counters = {}
        targets = get_targets()
        if targets.mode == "off":
            return self
        for path in self._paths:
            module, attr = _resolve(path)
            original = getattr(module, attr)
            replacement = self._make_replacement(targets.mode, path, original)
            setattr(module, attr, replacement)
            self._patches.append((module, attr, original))
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        for module, attr, original in reversed(self._patches):
            setattr(module, attr, original)
        self._patches = []
        # Player consumption is asserted at RecordTargets.end_test, not here,
        # so that fixture teardown calls are included in the recording window.

    def __call__(self, func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with record_class(*self._paths):
                return func(*args, **kwargs)

        return wrapper

    def _next_key(self, path: str, args: tuple, kwargs: dict) -> str:
        base = _base_key(path, args, kwargs)
        idx = self._counters.get(base, 0)
        self._counters[base] = idx + 1
        return f"{base}#{idx}"

    def _make_replacement(self, mode: str, path: str, original: Callable) -> Callable:
        """Build the ctor_proxy that replaces the class/factory at ``path``.

        Wraps the constructed **instance** in a proxy so individual method calls
        on it are the recorded events. record_function overrides this to return
        the proxy directly instead (the call is the event, not the methods).
        """
        targets = get_targets()

        def ctor_proxy(*args: Any, **kwargs: Any) -> object:
            key = self._next_key(path, args, kwargs)
            if mode == "record":
                return RecordingProxy(
                    original(*args, **kwargs), key, targets.current_store
                )
            player = PlayerProxy(key, targets.current_store)
            targets.register_player(player)
            return player

        return ctor_proxy


class record_function(record_class):
    """Like record_class but for plain callables (functions, builtins, methods).

    The call itself is recorded and the real return value is passed through.
    Use this for module-level APIs like ``wikipedia.search`` where the symbol
    is a function, not a class whose returned instance needs method recording.
    """

    def __call__(self, func: Callable) -> Callable:
        # Override so the decorator form re-enters record_function, not record_class.
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with record_function(*self._paths):
                return func(*args, **kwargs)

        return wrapper

    def _make_replacement(self, mode: str, path: str, original: Callable) -> Callable:
        """Return the proxy directly as the callable replacement.

        Unlike record_class (which needs a ctor_proxy to intercept construction
        and wrap the returned instance), record_function's recorded unit is the
        call itself — so the proxy IS the replacement. Both RecordingProxy and
        PlayerProxy implement __call__, preserving the function's callable contract.
        Mode is decided here at patch time, not per-call.
        """
        targets = get_targets()
        if mode == "record":
            return RecordingProxy(original, path, targets.current_store)
        player = PlayerProxy(path, targets.current_store)
        targets.register_player(player)
        return player
