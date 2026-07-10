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


def resolve_host(name):
    """Heavy module-level call -- stands in for DNS over the network."""
    return f"10.0.0.{len(name)}"


class Connection:
    """Heavy inner dependency -- stands in for a real socket."""

    def __init__(self, host):
        self.host = host

    def send(self, payload):
        return f"{self.host}:ack:{payload}"


class Service:
    """Object under test: creates its own heavy Connection in __init__."""

    def __init__(self):
        host = resolve_host("prod")
        self.conn = Connection(host)

    def transmit(self, msg):
        return self.conn.send(msg)


class Session:
    def query(self, sql):
        return f"result:{sql}"


class Client:
    """Rung 4 -- chained: client.session().query(...)."""

    def session(self):
        return Session()
