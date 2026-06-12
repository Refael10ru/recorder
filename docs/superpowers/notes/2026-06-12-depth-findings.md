# Object-Depth Findings (2026-06-12)

| Rung | Shape | Record | Play | Notes |
|------|-------|--------|------|-------|
| 1 | pure callable | OK | OK | full coverage |
| 2 | flat object | OK | OK | full coverage |
| 3 | pickle-only returns | OK | OK | values round-trip via pickle envelope |
| 4 | nested/chained | warn | warn | only the outer call is recorded; the returned inner object is pickled, so inner calls are NOT replayed/verified -- they silently run against a REAL un-proxied object |

**Conclusion:** Strict pure-function depth is 1 (calls on the marked object).
Chained APIs need nested proxying -- RecordingProxy.__getattr__ would have to wrap
non-serializable return values in a child proxy and the player would replay the
child's events. Deferred; decide based on real fixture needs.

**Observed rung-4 play behavior (actual):**

Contrary to the initial prediction that play would FAIL, the probe
`uv run pytest tests/mockproj --recorder=play -k nested -q` (with no
`RECORDER_MODE` set, so the skip is inactive) actually PASSED:

```
.                                                                        [100%]
1 passed, 5 deselected in 0.01s
```

The reason it passes is the real danger. The recording for `client` holds a
single event:

```json
{
  "client": [
    {
      "method": "session",
      "args": [],
      "kwargs": {},
      "return": {
        "__pickle__": "gASVKQAAAAAAAACMFnRlc3RzLm1vY2twcm9qLm9iamVjdHOUjAdTZXNzaW9ulJOUKYGULg=="
      },
      "raised": null
    }
  ]
}
```

Only the OUTER `session()` call is recorded. Its return value is a pickled
**real** `tests.mockproj.objects.Session`. In play, `PlayerProxy.session()`
consumes that event and `decode()` unpickles the envelope back into a live
`Session` instance. The subsequent `sess.query("SELECT 1")` therefore runs
against that real, un-proxied object and returns `"result:SELECT 1"` by
executing the actual code path -- it is never replayed from a recording and
never verified by the player (there is no `query` event in the JSON, and the
player's `assert_consumed()` only checks the single `session` event).

So the rung-4 limit is **silent passthrough**, not a hard failure: depth-2
calls appear to "work" in play but are executing live code rather than replayed
events. This is more dangerous than an outright failure because it can mask
divergence in the inner object. Hence the test is guarded with
`skipif(os.environ.get("RECORDER_MODE") == "play", ...)` so it does not give a
false sense of replay coverage.

**Guarded behavior confirmed:**

- Record (no `RECORDER_MODE`): all 6 tests pass.
- Play with `RECORDER_MODE=play`: `5 passed, 1 skipped` -- the nested test is
  skipped, every other rung replays cleanly.
