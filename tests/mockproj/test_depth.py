import pytest


def test_pure_callable_returns(adder):
    assert adder(2, 3) == 5
    assert adder(10, 20) == 30


def test_pure_callable_raises(adder):
    with pytest.raises(TypeError):
        adder("x", 1)


def test_flat_object(calc):
    assert calc.add(2, 3) == 5
    assert calc.summary([1, 2, 3]) == {"sum": 6, "count": 3}


def test_flat_object_raises(calc):
    with pytest.raises(ZeroDivisionError):
        calc.divide(1, 0)
