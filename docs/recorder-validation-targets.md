# Recorder validation targets

Real, public, **API-client** projects used to validate pytest-recorder against
production code. Goal: prove record→replay (and the drift-as-contract guarantee)
holds on dependencies people actually use, and let the recorder's API mature
against the rough edges real clients expose.

The recorder's sweet spot:

- calls are **one level deep** — `client.method(args) -> result` (no `client.foo().bar()`),
- the dependency is **pure-ish** (output determined by input),
- returns are **JSON-serializable or picklable** (plain dicts/lists ideal),
- the project's tests currently **hit a real network service** or lean on heavy hand-mocks.

Two integration entry points:

- `@record("name")` on a **fixture** that returns the client object,
- `record_class("pkg.mod.ClassName")` / `record_function("pkg.mod.func")` —
  monkeypatch by import path, for dependencies **used inline** (no fixture seam).

## Status legend

- ✅ **validated** — integrated, record→play green, findings captured in `problems.md`.
- 🎯 **approved** — queued for an integration agent.
- ⬜ **candidate** — researched, not yet started.

## Candidates

Ranked by fit. Star counts approximate.

| Status | Project | API | ~Stars | pytest | Test style | Seam | Depth | Returns | Key? | Fit |
|--------|---------|-----|--------|--------|-----------|------|-------|---------|------|-----|
| ✅ | [sammchardy/python-binance](https://github.com/sammchardy/python-binance) | Binance | ~6.9k | yes | real-net system tests | `client` fixture | flat | JSON dicts | public keyless | **GOOD** |
| ✅ | [danpaquin/coinbasepro-python](https://github.com/danpaquin/coinbasepro-python) | Coinbase Pro | ~1.8k | yes | real-net / sandbox | inline `PublicClient()` | flat | dicts | public keyless | **GOOD** |
| ⬜ | [PokeAPI/pokebase](https://github.com/PokeAPI/pokebase) | PokéAPI | ~350 | no (unittest) | real-net by default | inline `pb.api.get_data()` | flat | plain dicts | keyless | **GOOD** |
| ✅ | [Finnhub-Stock-API/finnhub-python](https://github.com/Finnhub-Stock-API/finnhub-python) | Finnhub | ~1.0k | tox/sync | real-net | inline singleton client | flat | dicts | key (free) | **GOOD** |
| ✅ | [goldsmith/Wikipedia](https://github.com/goldsmith/Wikipedia) | Wikipedia | ~3.0k | no (unittest) | mocked `_wiki_request` | module funcs | flat | lists/str/dict | keyless | **GOOD/OK** |
| ⬜ | [bybit-exchange/pybit](https://github.com/bybit-exchange/pybit) | Bybit | ~0.66k | yes | mostly mock; 1 real-net | inline `HTTP()` | flat | dicts | public keyless | **OK** |
| ⬜ | [coinbase/coinbase-advanced-py](https://github.com/coinbase/coinbase-advanced-py) | Coinbase Adv | ~0.6k | no (unittest) | requests_mock | inline `RESTClient()` | flat | typed objs `.to_dict()` | key+secret | **OK/POOR** |
| ⬜ | [RomelTorres/alpha_vantage](https://github.com/RomelTorres/alpha_vantage) | Alpha Vantage | ~4.8k | no (nose) | recorded data | inline `TimeSeries()` | flat | dict or DataFrame | key (free) | **OK/POOR** |

### Negative examples (out of sweet spot — useful as boundary tests)

| Project | Why POOR |
|---------|----------|
| [tweepy/tweepy](https://github.com/tweepy/tweepy) | rich domain objects; already VCR |
| [geopy/geopy](https://github.com/geopy/geopy) | geocoder tests are `async def` |
| [martin-majlis/Wikipedia-API](https://github.com/martin-majlis/Wikipedia-API) | lazy-property fetch on attribute access |
| [praw-dev/praw](https://github.com/praw-dev/praw) | chained + lazy objects; OAuth |
| [PyGithub/PyGithub](https://github.com/PyGithub/PyGithub) | chained + lazy objects |
| [PokeAPI/pokepy](https://github.com/PokeAPI/pokepy) | returns objects, not dicts |
| [ccxt/ccxt](https://github.com/ccxt/ccxt) | transpiled/async, non-idiomatic tests |

## Recurring gotchas (recorder roadmap drivers)

> Confirmed recorder defects/limitations are tracked in [`known-issues.md`](known-issues.md).

- **Secrets in recordings.** Key-required clients (finnhub, coinbase-advanced,
  alpha_vantage) pass `api_key`/`secret` into the constructor. `record_class`
  keys streams by constructor args → the key lands in the recording file verbatim.
  Need a scrub/redact hook (cf. PRAW's `filter_access_token` VCR pattern).
- **Lazy-property / chained objects.** The #1 disqualifier (PyGithub, PRAW,
  Wikipedia-API, pokepy, tweepy). Breaks "one level deep, picklable return".
- **Non-JSON returns.** pandas DataFrames (alpha_vantage), numpy/flatbuffers — record
  only the raw-json/dict output mode, else rely on pickle fallback.
- **Async-only suites.** geopy geocoders, ccxt async layer — outside the sync sweet spot.
- **Typed-response wrappers** with `.to_dict()` (coinbase-advanced) — recordable only
  if snapshotting post-`.to_dict()`.

## Next picks (cover the full matrix)

1. **coinbasepro-python** — keyless + fixture/inline, second crypto exchange.
2. **pokebase** — keyless + exercises `record_function` (module-level funcs).
3. **finnhub-python** — key-required → forces secret-scrubbing work.

## Per-project findings

Integration problems land in [`problems.md`](../problems.md), one section per project.
