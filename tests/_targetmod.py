"""Importable system-under-test for record_targets tests.

``run`` looks up ``Dependency`` via this module's global namespace, so patching
``tests._targetmod.Dependency`` redirects construction the same way production
code's module-level lookups are redirected.
"""


class Dependency:
    def __init__(self, host):
        self.host = host

    def fetch(self, key):
        return f"{self.host}:{key}"


def run(host, key):
    dep = Dependency(host)
    return dep.fetch(key)
