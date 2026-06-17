# Recorder integration problems

Problems found while integrating pytest-recorder into real API-client projects.
One section per project. Severity = impact on using the recorder for real.

Each project was cloned to `~/code/<project>`, given a `.venv`, installed with the
recorder (`uv pip install -e . pytest /home/ref/code/recorder`), wired with
`@record` and/or `record_targets`, then run `--recorder=record` (live) →
`--recorder=play` (offline, proven with `HTTPS_PROXY=http://127.0.0.1:1`).

Legend: 🟥 high · 🟧 med · 🟨 low · ✅ no defect.
IDs: `<PROJECT>-<n>` (BIN=python-binance, CBP=coinbasepro-python, WIKI=goldsmith-Wikipedia, FIN=finnhub-python).

---

## python-binance

Validated earlier. `client` fixture + `@record`; flat JSON methods; real-net system tests.
record 6/6 (4.77s) → play 6/6 (0.05s, offline) → arg flip ⇒ `RecordingMismatch`.
`record_targets("binance.client.Client")` inline path also green (1.15s → 0.01s).

**Problems**
- 🟥 **[BIN-1] Secrets in recordings.** `record_targets` keys streams by constructor args, so
  `api_key`/`api_secret` passed to `Client(...)` are written verbatim into the
  recording file. *Cause:* `_base_key` in `targets.py` json-dumps the raw args.
  *Fix:* redact/hash constructor args, or a per-target arg-scrubber hook (cf. VCR's
  `filter_*` record hooks). The fixture `@record` path is unaffected (keys by name).

---

## coinbasepro-python

Keyless `PublicClient`. Both entry points exercised:
`@record("public")` fixture **and** `record_targets("cbpro.PublicClient")` inline.
record 2/2 (35.2s) → play 2/2 (0.01s, offline) → arg flip (`BTC-USD`→`ETH-USD`) ⇒
`RecordingMismatch`. Returns are plain dicts/lists (JSON pass-through, no pickle).

**Problems**
- ✅ **[CBP-1]** No recorder defect.
- 🟨 **[CBP-2]** *Project/API, not recorder:* the library's default `api_url`
  (`api.pro.coinbase.com`) is sunset — only `get_time` works there; everything else
  returns `{"message": ...}`. Must pass `api_url="https://api.exchange.coinbase.com"`.
- 🟨 **[CBP-3] Ergonomic note:** record took 35s because `get_products()` returns ~824
  objects; encoding/replay handles it fine (play 0.01s) but large-payload recordings
  are heavy on disk. Not a bug — flagging for a possible size note in docs.

---

## goldsmith-Wikipedia

Keyless, but the API is exposed as **module-level functions** (`wikipedia.search`,
`wikipedia.summary`), not a client object.

Working path — `@record` on fixtures that *return the function*:
record 2/2 (2.63s) → play 2/2 (0.01s, offline) → query change ⇒ `RecordingMismatch`.

**Problems**
- 🟧 **[WIKI-1] `record_targets` does not fit plain functions.**
  `record_targets("wikipedia.search")` makes the test receive a `RecordingProxy`
  *around the return list* instead of the list:
  `TypeError: argument of type 'RecordingProxy' is not iterable`, and nothing useful
  is recorded. *Cause:* the shim does `RecordingProxy(original(*args))` — it assumes
  the patched symbol is a **factory/constructor** whose *return* is the object to
  record. For a function, the symbol *itself* is the recordable call.
  *Fix:* detect when the target is a plain function (not a class/factory) and record
  the call directly (wrap the symbol as a callable `RecordingProxy`, like the fixture
  path does), rather than wrapping its return value. *Workaround today:* use the
  `@record` fixture form returning the function.
- 🟨 **[WIKI-2] UA gotcha (env, not recorder):** Wikipedia returns HTTP 403 to the default UA;
  must `wikipedia.set_user_agent(...)` before recording.

---

## finnhub-python

Key-required (`finnhub.Client(api_key=...)`); no key in env, so only the **error
path** was recorded (dummy key → `FinnhubAPIException` 401).
`record_targets("finnhub.Client")`. record 1/1 (0.56s) → **play FAILED**.

**Problems**
- 🟥 **[FIN-1] Recorded exceptions can fail to replay (latent record-passes / play-fails).**
  record succeeds, but play raises
  `TypeError: FinnhubAPIException.__init__() missing 1 required positional argument`
  at `serialize.py:42` (`pickle.loads`). *Cause:* the recorder pickles exceptions;
  `FinnhubAPIException` raises with `args == ()` while its `__init__` requires one
  positional arg, so `BaseException.__reduce__` yields `cls()` which fails to
  reconstruct. The exception pickles fine (`record`) but won't unpickle (`play`).
  This is fragile for *any* exception class that isn't cleanly picklable, and the
  failure only surfaces at replay. *Fix:* round-trip exceptions at **record** time
  (encode→decode immediately) and fail loudly then; or store exception by
  type+message/args and rebuild defensively (fallback to a generic re-raise
  preserving type name + str) instead of relying on pickle reconstruction.
- 🟥 **[FIN-2] Secrets in recordings** (same as python-binance, confirmed concretely):
  recording stream key = `finnhub.Client([[], {"api_key": "DEMO_LEAK_KEY_12345"}])#0`
  — the api_key is written into the recording. *Fix:* as above (scrub constructor args).
- 🟧 **[FIN-3] Blocked: success-path not validated.** Needs a free `FINNHUB_API_KEY` to
  record real data; only the error path was exercisable here.

---

## Summary of recorder changes suggested

1. 🟥 Scrub/redact constructor args in `record_targets` keys (secrets leak) — hits
   every key-required client (finnhub, binance, coinbase-advanced, alpha_vantage).
   [BIN-1, FIN-2]
2. 🟥 Make exception replay robust (don't depend on clean pickle round-trip;
   validate at record time) — `serialize.py` / `engine.py`. [FIN-1]
3. 🟧 Support plain functions in `record_targets` (record the call, not the return) —
   needed for module-function APIs like Wikipedia. [WIKI-1]
