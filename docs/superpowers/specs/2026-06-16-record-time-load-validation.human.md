# Record-time load validation — human-readable

A walkthrough of the `--recorder=validation` feature, written for a person.

## The problem in one breath

The recorder saves each call's result by *encoding* it (JSON when it can, a
base64 pickle when it can't). Replaying reads it back by *decoding*. Most values
survive the trip; some don't. A custom exception like finnhub's
`FinnhubAPIException` encodes fine but blows up on decode, because it's raised with
no `args` yet its constructor demands one. The nasty part: recording succeeds and
writes a perfectly innocent-looking file. The break only appears later, the first
time someone replays it.

We decided not to try to fix exception reconstruction in general — that's a deep
hole and may be impossible. Instead we catch the bad recording *the moment it's
made*, and we make that an opt-in so normal recording stays fast.

## What we're building

A fourth recorder mode: `--recorder=validation`. It records exactly like
`--recorder=record` — it calls the real dependency and writes the recording — but
for every value it stores, it immediately checks that the value *round-trips*:
load what you just saved and confirm you get the same thing back. In shorthand,
`load(unload(x)) == x`. If a value won't load, or loads into something different,
the run fails right there with a clear error.

Plain `--recorder=record` is unchanged: fast, no checking. You reach for
`validation` when you want to trust a recording you're about to commit.

## The one subtlety: comparing values safely

"Same thing back" is harder than it sounds. Lots of real return values — numpy
arrays, pandas frames, hand-rolled objects — have an `==` that returns a non-bool
or throws "truth value is ambiguous". So we don't compare the live objects.

Every value is already stored in an *encoded* form that is, by construction,
plain JSON: numbers, strings, lists, dicts, or a `{"__pickle__": "<base64>"}`
envelope. Comparing those is always safe. So the check is:

```
encode(decode(stored)) == stored
```

Decode the stored value, encode it again, and compare the two encoded forms.
That's a faithful stand-in for `load(unload(x)) == x` that never trips over a
weird `__eq__`. (It's the same reasoning the player already uses when it matches
calls on encoded arguments.)

This catches two things: a value that won't decode at all (finnhub), and a value
whose decode→encode comes back different (an unstable round-trip).

## How it fits the existing code

- A new error, `RecordingValidationError`, alongside the other recorder errors.
- A small new module, `validate.py`, with one function `check_roundtrip(name,
  event)` that runs the comparison above on the event's return and exception, and
  raises with a helpful message naming the proxy, the method, and what went wrong.
- `RecordingProxy` (the thing that wraps a real object during recording) gains a
  `validate` flag. When it's on, it runs `check_roundtrip` *before* it appends the
  event, so a bad value never even enters the store. Because both `@record` and
  `record_targets` funnel through `RecordingProxy`, both get validation for free.
- The plugin learns the new mode: `validation` records and flushes like `record`,
  and turns the `validate` flag on.

## How we'll know it works

Small, direct tests:

- The check function passes a normal dict, passes a normal picklable object,
  fails a finnhub-style exception, and fails a value that re-encodes differently.
- End to end: a fixture that raises a finnhub-style exception passes under
  `record` (the latent bug) but fails under `validation` — which is the whole
  point. A well-behaved fixture passes `validation` and produces the same file
  `record` would.

## What we're deliberately leaving out for now

Scanning existing recording files offline without re-running, and nicer messages
when *encoding* (not decoding) is what fails. Both can come later if we want them.
