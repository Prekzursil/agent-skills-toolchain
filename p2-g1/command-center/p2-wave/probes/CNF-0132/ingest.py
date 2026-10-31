"""CNF-0132 live B09 ingest scan: candidate paths and confirmation records.

Re-derives the receipt's live_ingest lane against today's tree: counts real
confirmation records under the candidate roots and the CLAIM-REGISTRY lineage
rows. Rebuilt 2026-10-26 (wave-3 shard 7) after the original probe tree loss.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

CANDIDATE_PATHS = (
    "command-center/B09",
    "command-center/CLAIM-REGISTRY.json",
    "command-center/b09",
    "command-center/confirmation-records",
    "command-center/confirmations",
    "command-center/receipts/B09.json",
    "command-center/schema/confirmation-record.schema.json",
    "rules/common/single-signal-verification.md",
)


def scan(repo: Path | None = None) -> dict:
    repo = Path(repo) if repo else REPO
    presence = {p: (repo / p).exists() for p in CANDIDATE_PATHS}
    records_found = 0
    # confirmation-record.schema.json and CLAIM-REGISTRY.json are shims/registry,
    # not B09 confirmation records; any directory corpus or B09.json receipt would be.
    for p in ("command-center/B09", "command-center/b09",
              "command-center/confirmation-records", "command-center/confirmations",
              "command-center/receipts/B09.json"):
        target = repo / p
        if target.is_file():
            records_found += 1
        elif target.is_dir():
            records_found += sum(1 for f in target.rglob("*.json"))
    lineage = 0
    reg = repo / "command-center/CLAIM-REGISTRY.json"
    if reg.is_file():
        try:
            data = json.loads(reg.read_text(encoding="utf-8"))
            lineage = len(data.get("claims") or [])
        except (OSError, json.JSONDecodeError):
            lineage = -1
    return {
        "candidate_presence": presence,
        "confirmation_records_found": records_found,
        "claim_registry_present": bool(presence["command-center/CLAIM-REGISTRY.json"]),
        "claim_registry_lineage_rows": lineage,
    }


if __name__ == "__main__":
    print(json.dumps(scan(), indent=1))
