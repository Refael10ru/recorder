import os

import numpy as np
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


def test_pickle_only_returns(data):
    assert np.array_equal(data.vector(3), np.arange(3))
    df = data.frame()
    assert list(df.columns) == ["a", "b"]
    assert df["a"].tolist() == [1, 2]


@pytest.mark.skipif(
    os.environ.get("RECORDER_MODE") == "play",
    reason="nested chain not replayable yet -- see depth-findings note",
)
def test_nested_chain_records_outer_only(client):
    sess = client.session()
    assert sess.query("SELECT 1") == "result:SELECT 1"
