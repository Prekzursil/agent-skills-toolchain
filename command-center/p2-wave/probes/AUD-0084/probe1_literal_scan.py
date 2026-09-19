#!/usr/bin/env python3
"""Probe 1: live literal-string scan for drive letters, /home/, /Users/, backslash separators."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

ART = REPO / "command-center/audit/AUD-0084-hardcoded-path-census.json"
SENTINEL = C.CATALOG_SENTINEL
OUT = HERE / "probe1-literal-scan.json"


def main() -> int:
    scan = C.scan_tree()
    summary = C.summarize(scan)
    sample = scan["lexical_hits"][:40]
    C.dump_json(
        OUT,
        {
            "probe": "probe1-literal-scan",
            "evidence_requirement": (
                "Probe 1: a literal-string scan for drive letters, /home/, "
                "/Users/, and backslash separators inside path contexts."
            ),
            "summary": summary,
            "sample_hits": sample,
        },
    )
    print(f"source_files={summary['source_files_discovered']}")
    print(f"lexical_hits={summary['lexical_hit_count']}")
    print(f"lexical_files={summary['lexical_file_count']}")
    print(f"kind_counts={json.dumps(summary['kind_counts'], sort_keys=True)}")
    print(f"operational_files={summary['operational_file_count']}")
    print(
        f"first_party_operational_files={summary['first_party_operational_file_count']}"
    )
    print(f"wrote={OUT.relative_to(REPO).as_posix()}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:AUD-0084-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:AUD-0084-probe1 artifact unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0084-probe1 catalog sentinel absent")
        return 1
    # Artifact-level scoping (2026-09-19): FAILED/SEVERED/TIMEOUT mean the
    # artifact claim itself failed. BLOCKED-on-review is a UNIT state -- the
    # probes must stay reproducible against an honestly-blocked receipt so the
    # independent reviewer can re-run them.
    st = str(doc.get("state") or "").upper()
    if st in {"FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:AUD-0084-probe1 self-declared {st}")
        return 1
    live = (doc.get("census") or {}).get("lexical_hit_count")
    if live is not None and int(live) != int(summary["lexical_hit_count"]):
        print(
            f"FAILED:AUD-0084-probe1 lexical count drift "
            f"artifact={live} live={summary['lexical_hit_count']}"
        )
        return 1
    print("SUCCESS:AUD-0084-probe1 literal-string scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
