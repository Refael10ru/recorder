import pytest

from pytest_recorder import record

from . import objects


@pytest.fixture
@record("adder")
def adder():
    return objects.add


@pytest.fixture
@record("calc")
def calc():
    return objects.Calculator()


@pytest.fixture
@record("data")
def data():
    return objects.DataSource()


@pytest.fixture
@record("client")
def client():
    return objects.Client()
