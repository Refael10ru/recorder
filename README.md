# pytest-recorder

**Record once what your slow fixtures do. Replay it instantly forever — and fail loudly the moment your code uses them differently.**

## What it is

A pytest plugin that hooks the objects/callables you mark in your fixtures, **records** their inputs and outputs to a per-test file, then in **play** mode swaps the real thing for a player that serves the recording back — asserting every call matches, in order.

## Why it exists

System tests are slow and flaky because they hit real dependencies — databases, HTTP APIs, pricing engines — on every run. The usual fix is hand-written mocks: tedious to build, easy to drift out of sync with reality, and they quietly keep passing even when your code's usage changes.

pytest-recorder removes the handwork. Record once against the real dependency; from then on tests run in milliseconds with zero network, and the recording *is* the contract — call the dependency with different args, or in a different order, and the test fails.

## What it's used for

- Turning slow integration/system tests into fast, deterministic ones.
- Pinning the exact way your code uses a dependency — a regression guard, not just a speed-up.
- Killing brittle, hand-maintained mocks for pure-function-like dependencies.
- **Running only the tests that matter:** a passing replay means that test's behaviour is unchanged, so it needn't run for real; a replay failure pinpoints exactly the tests whose behaviour actually moved and need a full rerun.

## How it works

Mark a fixture, then pick a mode with a flag:

```python
import pytest
from pytest_recorder import record

@pytest.fixture
@record("pricing")
def pricing():
    return PricingClient(host="prod")   # real, slow, networked
```

```bash
pytest --recorder=record   # capture real inputs/outputs beside each test
pytest --recorder=play     # replay from disk: no network, strict-ordered checks
pytest                     # default: plugin off, real objects
```

In `play` the real object is never built. The player serves recorded returns (and re-raises recorded exceptions); any drift — wrong args, wrong order, extra or missing calls — raises a clear error.

> Assumes recorded dependencies behave like **pure functions** (output determined by input). Recording depth is one level: chained calls like `client.session().query()` aren't replayed.

## Learn more

See [USAGE.md](USAGE.md) for the full API — `@record`, `record_class`, `record_function`, `is_recorder_mock`, the exception hierarchy, and where recordings live on disk.
