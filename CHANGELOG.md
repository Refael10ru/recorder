# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Changed

- `record_class._make_replacement` inner function renamed `shim` → `ctor_proxy` to reflect its role as a constructor-level proxy.
- `record_function._make_replacement` simplified: returns `RecordingProxy`/`PlayerProxy` directly instead of wrapping in an inner function. Stream key is now `path` only (no encoded call args), so recording files use human-readable keys.

## [0.1.0] - 2026-06-24

### Added

- `record_function` for recording plain callables (not just class instances).
- `__is_recorder_mock__()` method on both `RecordingProxy` and `PlayerProxy` for identity checks.
- `_RecorderMock` mixin base class — eliminates method duplication between the two proxy classes.
- `is_recorder_mock(obj)` free function — safe to call on any object, no `AttributeError`.
- Exported `is_recorder_mock` from the top-level `pytest_recorder` package.
