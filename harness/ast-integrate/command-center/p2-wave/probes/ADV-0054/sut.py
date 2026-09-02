"""Load the RES-0138 onion-source kernel without copying it.

ADV-0054 is a conformance test, not a rebuild. The stage under test lives
in probes/RES-0138/. Importing it keeps a single enforcement kernel.
"""
from __future__ import annotations

import sys
from pathlib import Path

RES0138 = Path(__file__).resolve().parent.parent / "RES-0138"
_res = str(RES0138)
if _res not in sys.path:
    sys.path.insert(0, _res)

from controls import (  # noqa: E402
    CATALOG_PROHIBITIONS,
    DEFAULT_OWNER_OPT_IN,
    EGRESS_ALLOWLIST,
    FORBIDDEN_HEADER_NAMES,
    FORBIDDEN_METHODS,
    LAWFUL_PUBLIC_ONION,
    METHOD_ALLOWLIST,
    PROMPT_ONLY,
    STOLEN_DATA_MARKET_ONION,
    TECHNICAL_CONTROLS,
    missing_technical_enforcement,
    prompt_only_not_enforced,
)
from stage import (  # noqa: E402
    LABEL_TOR_DERIVED,
    LAWFUL_BODY,
    CredentialStoreSealed,
    LogSinkRequired,
    Stage,
    Transcript,
)

STAGE_PY = RES0138 / "stage.py"
CONTROLS_PY = RES0138 / "controls.py"

__all__ = [
    "CATALOG_PROHIBITIONS",
    "CONTROLS_PY",
    "DEFAULT_OWNER_OPT_IN",
    "EGRESS_ALLOWLIST",
    "FORBIDDEN_HEADER_NAMES",
    "FORBIDDEN_METHODS",
    "LABEL_TOR_DERIVED",
    "LAWFUL_BODY",
    "LAWFUL_PUBLIC_ONION",
    "METHOD_ALLOWLIST",
    "PROMPT_ONLY",
    "RES0138",
    "STAGE_PY",
    "STOLEN_DATA_MARKET_ONION",
    "TECHNICAL_CONTROLS",
    "CredentialStoreSealed",
    "LogSinkRequired",
    "Stage",
    "Transcript",
    "missing_technical_enforcement",
    "prompt_only_not_enforced",
]
