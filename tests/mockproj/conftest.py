import pytest

from pytest_recorder import record
from tests.mockproj import objects


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
