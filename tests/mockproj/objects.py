"""Depth-ladder objects exercised by the recorder testbed."""

import numpy as np
import pandas as pd


def add(a, b):
    """Pure callable -- rung 1."""
    return a + b


class Calculator:
    """Flat object -- rung 2. Methods return JSON-able values."""

    def add(self, a, b):
        return a + b

    def summary(self, nums):
        return {"sum": sum(nums), "count": len(nums)}

    def divide(self, a, b):
        return a / b


class DataSource:
    """Rung 3 -- returns objects that need the pickle fallback."""

    def vector(self, n):
        return np.arange(n)

    def frame(self):
        return pd.DataFrame({"a": [1, 2], "b": [3, 4]})
