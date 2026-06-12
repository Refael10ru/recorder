import pytest

from pytest_recorder import record
from tests.mockproj import objects


@pytest.fixture
@record("adder")
def adder():
    return objects.add
