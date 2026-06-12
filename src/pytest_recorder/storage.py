"""Recording file path resolution and per-test event store."""

import re
from pathlib import Path


def resolve_recording_path(nodeid: str, root: Path) -> Path:
    """Map a pytest nodeid to its recording file under <root>/recordings/.

    Structural separators (``/`` between path segments and ``::`` between the
    module and test name) become ``__``; every other non-alphanumeric
    character becomes a single ``_``.
    """
    structural = nodeid.replace("/", "__").replace("::", "__")
    safe = re.sub(r"[^0-9A-Za-z_]", "_", structural)
    return Path(root) / "recordings" / f"{safe}.json"
