# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0] - 2026-06-24

### Added

- `record_function` for recording plain callables (not just class instances).
- `__is_recorder_mock__()` method on both `RecordingProxy` and `PlayerProxy` for identity checks.
- `_RecorderMock` mixin base class — eliminates method duplication between the two proxy classes.
- `is_recorder_mock(obj)` free function — safe to call on any object, no `AttributeError`.
- Exported `is_recorder_mock` from the top-level `pytest_recorder` package.
