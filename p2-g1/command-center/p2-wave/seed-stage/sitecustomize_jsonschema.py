"""Disk-only jsonschema $ref. Loaded as sitecustomize or via p2g1.pth."""
from __future__ import annotations

try:
    import p2_jsonschema_hook  # noqa: F401
except Exception:
    try:
        from pathlib import Path
        import sys

        here = Path(__file__).resolve().parent
        if str(here) not in sys.path:
            sys.path.insert(0, str(here))
        import p2_jsonschema_hook  # noqa: F401
    except Exception:
        pass
