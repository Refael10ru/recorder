import pytest


def test_pure_callable_returns(adder):
    assert adder(2, 3) == 5
    assert adder(10, 20) == 30


def test_pure_callable_raises(adder):
    with pytest.raises(TypeError):
        adder("x", 1)
