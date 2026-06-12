"""Depth-ladder objects exercised by the recorder testbed."""


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
