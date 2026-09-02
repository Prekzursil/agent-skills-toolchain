"""Shared ADV-0049 paths, catalog sentinel and probe commands."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART_REL = "command-center/adversarial/ADV-0049-fusion-provenance-attribution-survival.json"
ART = REPO / ART_REL
SCHEMA_REL = "command-center/schema/license-and-rights-record.schema.json"
SCHEMA = REPO / SCHEMA_REL
WFA0127 = REPO / "command-center/p2-wave/probes/WFA-0127"
FIXTURES = HERE / "fixtures" / "sources.json"
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0049 emitted ONLY when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, records BOTH named probes verbatim "
    "with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, and "
    "records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0049 <reason>."
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0049/probe1_fusion_record.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0049/probe2_decompose.py"
)
QUESTION = (
    "When workflows are merged, distilled or clean-room reimplemented, does "
    "the output still carry every source's provenance, license and credit - "
    "and can the fusion be decomposed back into its sources?"
)
ALLOWED_VERDICTS = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, doc: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
