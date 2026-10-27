"""Router select seam. May raise; wrappers must catch (IMP-0404)."""
from __future__ import annotations

import os


def select(*_a, **_k):
    if os.environ.get("IMP0404_ROUTER_FAULT") == "raise":
        raise RuntimeError("forced-router-exception")
    return {"ok": True}
