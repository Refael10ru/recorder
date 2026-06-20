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

from pytest_recorder.engine import PlayerProxy, RecordingProxy, _encode_call
from pytest_recorder.plugin import get_controller
from pytest_recorder.storage import RecordingStore


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
        self._players: list[PlayerProxy] = []
        self._counters: dict[str, int] = {}

    def __enter__(self) -> "record_class":
        self._patches = []
        self._players = []
        self._counters = {}
        ctrl = get_controller()
        if ctrl.mode == "off":
            return self
        store = ctrl.current_store()
        for path in self._paths:
            module, attr = _resolve(path)
            original = getattr(module, attr)
            replacement = self._make_replacement(ctrl.mode, path, original, store)
            setattr(module, attr, replacement)
            self._patches.append((module, attr, original))
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        for module, attr, original in reversed(self._patches):
            setattr(module, attr, original)
        self._patches = []
        if exc_type is None:
            for player in self._players:
                player.assert_consumed()

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
        self, mode: str, path: str, original: Callable, store: RecordingStore
    ) -> Callable:
        def shim(*args: Any, **kwargs: Any) -> object:
            key = self._next_key(path, args, kwargs)
            if mode == "record":
                # Wrap the instance so method calls on it are also recorded.
                # Wrapping the class via __call__ instead would lose method recording.
                return RecordingProxy(original(*args, **kwargs), key, store)
            player = PlayerProxy(key, store)
            self._players.append(player)
            return player  # player replays method calls via __getattr__

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

    def _make_replacement(
        self, mode: str, path: str, original: Callable, store: RecordingStore
    ) -> Callable:
        def shim(*args: Any, **kwargs: Any) -> object:
            key = self._next_key(path, args, kwargs)
            if mode == "record":
                # Wrap the callable, not its return value: __call__ records and
                # returns the real result. record_class wraps the instance instead.
                return RecordingProxy(original, key, store)(*args, **kwargs)
            player = PlayerProxy(key, store)
            self._players.append(player)
            # Consume the __call__ event and return the recorded value directly.
            return player(*args, **kwargs)

        return shim
