# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- `ProxyTracker` in `proxy_tracking.py`: global lifecycle manager owning recorder mode, per-test store, and player registry. Plugin creates it; `record_class`, `record_function`, and `@record` all reach it via `get_tracker()`.
- `get_tracker()` / `_set_tracker()` in `proxy_tracking.py`: accessor and installer for the session-global `ProxyTracker` instance.

### Changed

- `plugin.py` is now a thin pytest adapter: only registers hooks and delegates to `ProxyTracker`. `Controller` class removed.
- `RecordingProxy` and `PlayerProxy` now accept `get_store: Callable[[], RecordingStore]` instead of `StoreSource`. `PlayerProxy._maybe_reload` detects test boundaries by store identity (new instance = new test) rather than `test_id()`.
- Player consumption is now asserted at `ProxyTracker.end_test` (after teardown) instead of at `record_class.__exit__`, so fixture teardown method calls are included in the recording window. `test_play_underuse_raises_at_block_exit` renamed `test_play_underuse_raises_at_test_end`.
- `_BlockSource` shim removed from `proxy_tracking.py` — player lifecycle is now fully owned by `ProxyTracker`.
- `record_class._make_replacement` inner function renamed `shim` → `ctor_proxy` to reflect its role as a constructor-level proxy.
- `record_function._make_replacement` simplified: returns `RecordingProxy`/`PlayerProxy` directly instead of wrapping in an inner function. Stream key is now `path` only (no encoded call args), so recording files use human-readable keys.

### Removed

- `StoreSource` ABC removed from `storage.py`. `RecordingStore` no longer subclasses it; the `current_store()` / `test_id()` / `register_player()` shim methods on `RecordingStore` are gone.

## [0.1.0] - 2026-06-24

### Added

- `record_function` for recording plain callables (not just class instances).
- `__is_recorder_mock__()` method on both `RecordingProxy` and `PlayerProxy` for identity checks.
- `_RecorderMock` mixin base class — eliminates method duplication between the two proxy classes.
- `is_recorder_mock(obj)` free function — safe to call on any object, no `AttributeError`.
- Exported `is_recorder_mock` from the top-level `pytest_recorder` package.
