"""record_class / record_function: monkeypatch by import path for a test.

``record_class`` is for **class/factory** symbols: the constructed instance is
wrapped in a proxy so method calls on it are also recorded.

``record_function`` is for **plain callable** symbols (functions, builtins,
methods): the call itself is recorded and the real return value is passed
through unchanged.  Use this for module-level APIs like ``wikipedia.search``.
"""

import functools
import importlib
import json
from collections.abc import Callable
from types import ModuleType
from typing import Any

from pytest_recorder.engine import PlayerProxy, RecordingProxy
from pytest_recorder.plugin import Controller, get_controller
from pytest_recorder.serialize import _encode_call
from pytest_recorder.storage import RecordingStore, StoreSource


class _BlockSource(StoreSource):
    """StoreSource shim that routes store/test_id to a Controller but collects
    its own player list so record_class can assert at block exit instead of
    relying on ctrl.end_test().
    """

    def __init__(self, ctrl: Controller) -> None:
        self._ctrl = ctrl
        self.players: list[Any] = []

    def current_store(self) -> RecordingStore:
        return self._ctrl.current_store()

    def test_id(self) -> object:
        return self._ctrl.test_id()

    def register_player(self, player: Any) -> None:
        # WHY: don't propagate to ctrl — record_class asserts at __exit__,
        # not at teardown, so players must not appear in ctrl._players.
        self.players.append(player)


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
        self._source: _BlockSource | None = None
        self._counters: dict[str, int] = {}

    def __enter__(self) -> "record_class":
        self._patches = []
        self._counters = {}
        ctrl = get_controller()
        if ctrl.mode == "off":
            return self
        self._source = _BlockSource(ctrl)
        for path in self._paths:
            module, attr = _resolve(path)
            original = getattr(module, attr)
            replacement = self._make_replacement(ctrl.mode, path, original)
            setattr(module, attr, replacement)
            self._patches.append((module, attr, original))
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        for module, attr, original in reversed(self._patches):
            setattr(module, attr, original)
        self._patches = []
        if exc_type is None and self._source is not None:
            for player in self._source.players:
                player.assert_consumed()
        self._source = None

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
        source = self._source
        assert source is not None

        def shim(*args: Any, **kwargs: Any) -> object:
            key = self._next_key(path, args, kwargs)
            if mode == "record":
                # Wrap the instance so method calls on it are also recorded.
                return RecordingProxy(original(*args, **kwargs), key, source)
            # source tracks players for __exit__ assertion (not ctrl).
            return PlayerProxy(key, source)

        return shim


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
        source = self._source
        assert source is not None

        def shim(*args: Any, **kwargs: Any) -> object:
            key = self._next_key(path, args, kwargs)
            if mode == "record":
                # Wrap the callable, not its return value: __call__ records and
                # returns the real result. record_class wraps the instance instead.
                return RecordingProxy(original, key, source)(*args, **kwargs)
            player = PlayerProxy(key, source)
            return player(*args, **kwargs)

        return shim
