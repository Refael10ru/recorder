# CLAUDE.md

## Project map

See [project_map.md](project_map.md) for the architecture overview, module
responsibilities, data flow, and key design decisions. Keep it up to date when
module boundaries or key decisions change.

## Linting

- ruff runs with a curated `select` set (see `ruff.toml`).
- Do NOT suppress any ruff rule without explicit user approval. This includes adding to `ignore` / `per-file-ignores` in ruff config and `# noqa` comments in code. Prefer fixing the violation over ignoring it. If suppression seems necessary, stop and ask the user first.

## Type checking

- `uv run mypy` must pass (config in `pyproject.toml` `[tool.mypy]`; checks `src` and `tests`).
- Prefer real type annotations and narrowing (`isinstance`, `TypeGuard`) over `# type: ignore`. Do not add `# type: ignore` without explicit user approval.

## Hard types — no duck typing

- Use nominal types (class inheritance, Union) not structural/duck typing (Protocol, `getattr` probes).
- When two modules cannot import each other, extract a shared ABC to `interfaces.py`; do not use `Protocol` as a workaround.
- Never use `getattr(obj, "method", None)` to detect optional behaviour — put the method on the ABC with a no-op default impl.
