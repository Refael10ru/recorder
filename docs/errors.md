# errors.py — Exception hierarchy

No recorder dependencies. All exceptions inherit from `RecorderError`.

```
RecorderError
├── MissingRecording      play mode, no .json file
├── RecordingExhausted    play mode, more calls than events
├── RecordingUnderused    play mode, fewer calls than events
└── RecordingMismatch     play mode, (method, args, kwargs) don't match next event
```

`RecorderError` is the catch-all for callers that want to handle any recorder
failure without caring which specific failure it is.
