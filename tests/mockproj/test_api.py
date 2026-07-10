"""System coverage for record_class, record_function and is_recorder_mock.

Runs through the real plugin (via the subprocess harness in
tests/test_integration.py) in all three modes: off, record, play.
"""

import os

import pytest

from pytest_recorder import is_recorder_mock, record_class, record_function

from . import objects

# Import path of the objects module differs between the in-repo run
# ("tests.mockproj.objects") and the copied-to-tmp run ("mockproj.objects"),
# so derive it instead of hardcoding.
OBJECTS = objects.__name__
MODE = os.environ.get("RECORDER_MODE", "off")


def test_record_class_patches_constructor():
    with record_class(f"{OBJECTS}.Calculator"):
        calc = objects.Calculator()
        assert calc.add(4, 5) == 9
        assert calc.summary([2, 4]) == {"sum": 6, "count": 2}


def test_record_class_decorator_form():
    @record_class(f"{OBJECTS}.Calculator")
    def body():
        return objects.Calculator().add(1, 2)

    assert body() == 3


def test_record_function_returns_plain_value():
    with record_function(f"{OBJECTS}.add"):
        result = objects.add(7, 8)
    assert result == 15
    assert isinstance(result, int)  # plain value, not a proxy


def test_bare_record_decorator_fixture(bare_calc):
    assert bare_calc.add(3, 4) == 7


@pytest.fixture
@record_class(f"{OBJECTS}.Calculator")
def proxied_calc():
    # Patch is active only during the fixture body; the proxy it returns
    # keeps recording/replaying method calls made later, inside the test.
    return objects.Calculator()


def test_record_class_decorates_fixture(proxied_calc):
    assert proxied_calc.add(5, 6) == 11
    assert proxied_calc.summary([10]) == {"sum": 10, "count": 1}


@pytest.fixture
@record_function(f"{OBJECTS}.add")
def sums():
    # Calls happen during fixture setup, inside the patched window.
    return objects.add(1, 2), objects.add(30, 40)


def test_record_function_decorates_fixture(sums):
    assert sums == (3, 70)


@pytest.fixture
@record_class(f"{OBJECTS}.Connection")
@record_function(f"{OBJECTS}.resolve_host")
def service():
    # The object under test stays real; only the heavy dependencies it
    # creates inside __init__ (the socket-like Connection and the DNS-like
    # resolve_host call) are recorded/replayed.
    return objects.Service()


def test_fixture_records_only_inner_dependencies(service):
    assert is_recorder_mock(service) is False  # object under test is real
    assert is_recorder_mock(service.conn) is (MODE != "off")  # its socket isn't
    # method call at test time goes through the real Service, replayed conn
    assert service.transmit("ping") == "10.0.0.4:ack:ping"


def test_is_recorder_mock_matches_mode(calc):
    assert is_recorder_mock(calc) is (MODE in ("record", "play"))
    assert is_recorder_mock(object()) is False
    assert calc.add(1, 1) == 2
