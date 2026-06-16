FEATURE: record-time load validation
ID: SPEC-2026-06-16-record-time-load-validation
COMPONENT: pytest-recorder
TYPE: feature / serialization / test-tooling
STATUS: design-approved
KEYWORDS: pytest, pytest plugin, recorder, record, replay, play, validation, serialization, encode, decode, pickle, json, round-trip, round trip, load, unload, RecordingProxy, record_targets, fixture, exception, deserialization, data integrity, CLI option, --recorder, mode, RecordingValidationError, finnhub, FinnhubAPIException, latent failure, regression guard

PROBLEM:
- recorder stores call results via encode() = json-native passthrough OR base64 pickle.
- replay reconstructs via decode().
- some values encode() OK but fail decode() (e.g. custom exceptions: FinnhubAPIException raised with args==() but __init__ requires positional arg -> pickle.loads TypeError at serialize.py:42).
- failure is LATENT: record() succeeds + writes recording; breakage only appears at play().
- general exception reconstruction = out of scope (may be impossible).
- decision: detect unloadable recording at RECORD time, opt-in mode.

GOAL:
- new opt-in mode --recorder=validation.
- behaves like --recorder=record (calls real dependency, writes recording) PLUS verifies every stored value round-trips: load(unload(x)) == x.
- fail loud on non-loadable or non-equal round-trip.
- plain --recorder=record unchanged: fast, no checking.

ROBUST-EQUALITY:
- naive decode(stored)==original unreliable: numpy/pandas/custom objects -> non-bool == or "truth value is ambiguous".
- compare in ENCODED space instead: encode(decode(stored)) == stored.
- encoded forms always json-safe (scalar/str/list/dict OR {"__pickle__":"<b64>"}) -> equality well-defined.
- mirrors PlayerProxy matching calls on encoded args (engine.py:81).
- catches: (1) decode failure (finnhub), (2) unstable round-trip (reloaded re-encodes differently).

MODE-WIRING:
- REQ-1: --recorder choices = off | record | play | validation (plugin.py pytest_addoption).
- REQ-2: Controller treats validation like record: build proxies, flush at teardown; only play calls store.load().
- REQ-3: Controller.end_test flush when mode in {record, validation}; assert players when mode == play.

COMPONENTS:
- REQ-4: errors.py add class RecordingValidationError(RecorderError).
- REQ-5: validate.py new. function check_roundtrip(name: str, event: dict) -> None.
    - for each present field in (event["return"], event["raised"] if non-null): stored=event[field].
    - reloaded = decode(stored); on exception -> raise RecordingValidationError ("cannot be loaded").
    - re = encode(reloaded); on exception -> raise RecordingValidationError.
    - if re != stored -> raise RecordingValidationError ("does not round-trip").
    - message names proxy name, method, failing field.
    - no network; pure encoded-space round-trip.
- REQ-6: engine.py RecordingProxy.__init__(self, target, name, store, validate=False); store flag.
- REQ-7: engine.py RecordingProxy._record: if self._validate -> check_roundtrip(self._name, event) BEFORE store.append (non-round-tripping event never enters store).
- REQ-8: decorator.py @record: build RecordingProxy when ctrl.mode in {record, validation}; validate=(ctrl.mode=="validation").
- REQ-9: targets.py record_targets _make_shim: record in {record, validation}; RecordingProxy(..., validate=(mode=="validation")).
- COVERAGE: both @record and record_targets funnel through RecordingProxy -> both validated.

DATA-FLOW (validation mode):
1. test calls recorded method on RecordingProxy.
2. _record calls real target; make_event encodes return/raised.
3. check_roundtrip verifies encode(decode(stored))==stored for return + raised.
   - pass -> append event; return real value / re-raise real exception (as record).
   - fail (decode/encode raises OR values differ) -> raise RecordingValidationError; event NOT appended.
4. teardown: record/validation flush recording to disk.

ERROR-HANDLING:
- only new failure = RecordingValidationError during validation run.
- record, play, off behavior unchanged.
- default validate=False keeps existing callers unchanged.

TESTING:
- UNIT check_roundtrip: plain json dict event -> no raise; encoded BoomError-style exception (won't pickle.loads) -> raise; normal picklable object -> no raise; value re-encodes differently -> raise.
- INTEGRATION: fixture returns callable raising BoomError (custom exception, args==(), required ctor arg):
    - --recorder=record -> pass + writes recording (latent bug, unchecked).
    - --recorder=validation -> raise RecordingValidationError at record time.
- INTEGRATION good fixture (json dict return): --recorder=validation -> pass + recording identical to --recorder=record.
- INTEGRATION record_targets path: BoomError via inline construction -> validation raises, record does not.

OUT-OF-SCOPE:
- offline whole-file validation pass (re-load existing recordings without re-running).
- encode-time (pickle.dumps) failure diagnostics.

FILES-TOUCHED: src/pytest_recorder/plugin.py, errors.py, engine.py, decorator.py, targets.py; NEW src/pytest_recorder/validate.py; tests for validate + integration.
