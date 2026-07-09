# CLAUDE.md

## Project map

See [project_map.md](project_map.md) for the architecture overview, module
responsibilities, data flow, and key design decisions. Keep it up to date when
module boundaries or key decisions change.

See [USAGE.md](USAGE.md) for the public API and how users invoke the plugin.
Keep it up to date when the public API or CLI surface changes.

## Linting

- ruff runs with a curated `select` set (see `ruff.toml`).
- Do NOT suppress any ruff rule without explicit user approval. This includes adding to `ignore` / `per-file-ignores` in ruff config and `# noqa` comments in code. Prefer fixing the violation over ignoring it. If suppression seems necessary, stop and ask the user first.

## Type checking

- `uv run mypy` must pass (config in `pyproject.toml` `[tool.mypy]`; checks `src` and `tests`).
- Prefer real type annotations and narrowing (`isinstance`, `TypeGuard`) over `# type: ignore`. Do not add `# type: ignore` without explicit user approval.

## Changelog

- Maintain `CHANGELOG.md` at the repo root in [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format (Unreleased → Added/Changed/Fixed/Removed sections).
- Every code change that touches `src/` or `tests/` must include a corresponding `CHANGELOG.md` entry in the same commit.
- Do NOT update the changelog for changes to `CLAUDE.md`, config files, or docs only.
