"""Tracks all proxies in the process.

record_class / record_function: monkeypatch by import path for a test.

``record_class`` is for **class/factory** symbols: the constructed instance is
wrapped in a proxy so method calls on it are also recorded.

``record_function`` is for **plain callable** symbols (functions, builtins,
methods): the call itself is recorded and the real return value is passed
through unchanged.  Use this for module-level APIs like ``wikipedia.search``.

``ProxyTracker`` is the global lifecycle object for this module — it owns
recorder mode, the per-test store, and the player registry. ``plugin.py``
creates it at session start and calls ``begin_test`` / ``end_test`` around
each test.
"""

import functools
import importlib
import json
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from types import ModuleType
from typing import Any

from pytest_recorder.engine import PlayerProxy, RecordingProxy
from pytest_recorder.errors import MissingRecording
from pytest_recorder.serialize import _encode_call
from pytest_recorder.storage import RecordingStore, resolve_recording_path


class RecorderMode(StrEnum):
    OFF = "off"
    RECORD = "record"
    PLAY = "play"


_TRACKER: "ProxyTracker | None" = None


def get_tracker() -> "ProxyTracker":
    """Return the active ProxyTracker, or raise if the plugin is unconfigured."""
    if _TRACKER is None:
        msg = "recorder: tracker not configured"
        raise RuntimeError(msg)
    return _TRACKER


def _set_tracker(t: "ProxyTracker") -> None:
    global _TRACKER
    _TRACKER = t


class ProxyTracker:
    """Global lifecycle manager: recorder mode, per-test store, player registry.

    ``plugin.py`` creates one instance per session and wires pytest hooks to
    call ``begin_test`` / ``end_test``. ``record_class`` / ``record_function``
    and ``decorator.record`` all call ``get_tracker()`` to reach this object.

    Assertion of player consumption happens at ``end_test`` (not at block
    ``__exit__``) so that fixture teardown calls — which happen after the
    test body exits — are included in the recording window.
    """

    def __init__(self, mode: RecorderMode) -> None:
        self.mode = mode
        self._store: RecordingStore | None = None
        self._players: list[Any] = []

    def begin_test(self, nodeid: str, test_file: Path) -> None:
        """Initialize per-test state; build (record) or load (play) the store."""
        self._players = []
        if self.mode == RecorderMode.OFF:
            self._store = None
            return
        path = resolve_recording_path(nodeid, test_file)
        if self.mode == RecorderMode.PLAY and not path.exists():
            msg = f"recorder: no recording at {path}; re-run with --recorder=record"
            raise MissingRecording(msg)
        self._store = RecordingStore(path)
        if self.mode == RecorderMode.PLAY:
            self._store.load()

    def current_store(self) -> RecordingStore:
        """Return this test's store; raises if called outside a running test."""
        if self._store is None:
            msg = "recorder: current_store called outside a running test"
            raise RuntimeError(msg)
        return self._store

    def register_player(self, player: Any) -> None:
        """Track a player so its full consumption can be asserted at end_test."""
        self._players.append(player)

    def end_test(self) -> None:
        """Flush recordings (record) or assert full consumption (play)."""
        if self.mode == RecorderMode.RECORD and self._store is not None:
            self._store.flush()
        elif self.mode == RecorderMode.PLAY:
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
        tracker = get_tracker()
        if tracker.mode == RecorderMode.OFF:
            return self
        for path in self._paths:
            module, attr = _resolve(path)
            original = getattr(module, attr)
            replacement = self._make_replacement(tracker.mode, path, original)
            setattr(module, attr, replacement)
            self._patches.append((module, attr, original))
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        for module, attr, original in reversed(self._patches):
            setattr(module, attr, original)
        self._patches = []
        # Player consumption is asserted at ProxyTracker.end_test, not here,
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

    def _make_replacement(
        self, mode: RecorderMode, path: str, original: Callable
    ) -> Callable:
        """Build the ctor_proxy that replaces the class/factory at ``path``.

        Wraps the constructed **instance** in a proxy so individual method calls
        on it are the recorded events. record_function overrides this to return
        the proxy directly instead (the call is the event, not the methods).
        """
        tracker = get_tracker()

        def ctor_proxy(*args: Any, **kwargs: Any) -> object:
            key = self._next_key(path, args, kwargs)
            if mode == RecorderMode.RECORD:
                return RecordingProxy(
                    original(*args, **kwargs), key, tracker.current_store
                )
            player = PlayerProxy(key, tracker.current_store)
            tracker.register_player(player)
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

    def _make_replacement(
        self, mode: RecorderMode, path: str, original: Callable
    ) -> Callable:
        """Return the proxy directly as the callable replacement.

        Unlike record_class (which needs a ctor_proxy to intercept construction
        and wrap the returned instance), record_function's recorded unit is the
        call itself — so the proxy IS the replacement. Both RecordingProxy and
        PlayerProxy implement __call__, preserving the function's callable contract.
        Mode is decided here at patch time, not per-call.
        """
        tracker = get_tracker()
        if mode == RecorderMode.RECORD:
            return RecordingProxy(original, path, tracker.current_store)
        player = PlayerProxy(path, tracker.current_store)
        tracker.register_player(player)
        return player
