# CLAUDE.md

## Linting

- ruff runs with a curated `select` set (see `ruff.toml`).
- Do NOT suppress any ruff rule without explicit user approval. This includes adding to `ignore` / `per-file-ignores` in ruff config and `# noqa` comments in code. Prefer fixing the violation over ignoring it. If suppression seems necessary, stop and ask the user first.

## Type checking

- `uv run mypy` must pass (config in `pyproject.toml` `[tool.mypy]`; checks `src` and `tests`).
- Prefer real type annotations and narrowing (`isinstance`, `TypeGuard`) over `# type: ignore`. Do not add `# type: ignore` without explicit user approval.
