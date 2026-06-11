# CLAUDE.md

## Linting

- ruff runs with `select = ["ALL"]` (see `ruff.toml`).
- Do NOT suppress any ruff rule without explicit user approval. This includes adding to `ignore` / `per-file-ignores` in ruff config and `# noqa` comments in code. Prefer fixing the violation over ignoring it. If suppression seems necessary, stop and ask the user first.
