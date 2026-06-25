"""Shared abstract base for objects that supply a per-test RecordingStore.

Both RecordingStore (direct use) and Controller (plugin use) satisfy this
contract. engine.py imports only this module — not plugin.py — so there is
no circular dependency.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pytest_recorder.engine import PlayerProxy
    from pytest_recorder.storage import RecordingStore


class StoreSource(ABC):
    """Contract for objects that engine proxies call to get a store."""

    @abstractmethod
    def current_store(self) -> "RecordingStore":
        """Return the RecordingStore for the current test."""

    @abstractmethod
    def test_id(self) -> object:
        """Return a value that changes whenever the active test changes.

        Proxies compare successive return values to detect test-boundary
        crossings and reload events. Must be stable within one test and
        distinct across tests.
        """

    @abstractmethod
    def register_player(self, player: "PlayerProxy") -> None:
        """Register a player so its consumption can be verified at test end."""
