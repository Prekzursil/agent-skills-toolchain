"""PHASE-2C council protocol blueprints P25-P36 as executable CouncilSpec instances.

The authored source of the 12 protocols is Python (protocols_25_30.py, protocols_31_36.py);
the DELIVERABLE is the JSON under platform/council/protocols/. build.py writes the JSON,
validates the ON-DISK files with the sibling councilspec validator, and reports drift between
what is on disk and what regenerating would produce - so a hand-edit of a JSON file is
visible rather than silently overwritten.
"""

from __future__ import annotations

from .protocols_25_30 import PROTOCOLS_25_30
from .protocols_31_36 import PROTOCOLS_31_36

PROTOCOL_BUILDERS = PROTOCOLS_25_30 + PROTOCOLS_31_36

__all__ = [
    "PROTOCOL_BUILDERS",
    "PROTOCOLS_25_30",
    "PROTOCOLS_31_36",
    "build_all",
    "filename_for",
]


def filename_for(spec) -> str:
    return f"{spec['council_id']}.councilspec.json"


def build_all():
    """Return [(filename, spec), ...] in lane order P25..P36."""
    return [(filename_for(s), s) for s in (b() for b in PROTOCOL_BUILDERS)]
