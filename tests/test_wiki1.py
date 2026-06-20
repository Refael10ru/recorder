"""WIKI-1 regression: record_function works for plain module-level functions.

Run:
    # record against live Wikipedia (needs network):
    uv run pytest tests/test_wiki1.py --recorder=record -v

    # replay offline (no network needed):
    uv run pytest tests/test_wiki1.py --recorder=play -v

Bug (now fixed): record_class("wikipedia.search") wrapped the returned list in
a RecordingProxy so callers got TypeError on iteration.  record_function records
the __call__ and passes the real return value through unchanged.
"""

import pytest
import wikipedia

from pytest_recorder import record_function


@pytest.fixture(autouse=True)
def _wiki_ua():
    # Wikipedia returns 403 without a custom UA; set before any call is made.
    # This is WIKI-2 (env/UA issue, not a recorder bug) — noted in problems.md.
    wikipedia.set_user_agent("pytest-recorder-wiki1-test/1.0")


def test_search_returns_real_list():
    # Core WIKI-1 regression: result must be a plain list, not a RecordingProxy.
    with record_function("wikipedia.search"):
        results = wikipedia.search("Python programming language")
    assert isinstance(results, list), f"expected list, got {type(results)}"
    assert len(results) > 0


def test_search_result_is_iterable():
    # Iteration failed with the old proxy-wrapping bug (TypeError: not iterable).
    with record_function("wikipedia.search"):
        results = wikipedia.search("Python programming language")
    assert any("Python" in r for r in results)


def test_search_result_supports_index():
    # Indexing also raised AttributeError on the proxy.
    with record_function("wikipedia.search"):
        results = wikipedia.search("Python programming language")
    assert isinstance(results[0], str)


def test_search_play_matches_record():
    # Same query must round-trip: recorded value equals replayed value.
    with record_function("wikipedia.search"):
        results = wikipedia.search("Python programming language")
    assert results[0] == "Python (programming language)"
