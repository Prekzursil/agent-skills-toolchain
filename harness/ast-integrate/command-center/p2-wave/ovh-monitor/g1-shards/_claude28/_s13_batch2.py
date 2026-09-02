#!/usr/bin/env python3
"""Shard-13 batch-2: CNF-0001 sha, CNF-0169 report_kind+live pairs, CNL schema check."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def refresh_manifest(uid: str, paths: list[str]) -> None:
    mp = REPO / "command-center" / "p2-wave" / "probes" / uid / "UNIT-ARTIFACT-MANIFEST.json"
    man = json.loads(mp.read_text(encoding="utf-8"))
    wanted = set(paths)
    seen = set()
    for row in man.get("artifacts") or []:
        rel = str(row.get("path") or "").replace("\\", "/")
        if rel not in wanted:
            continue
        p = REPO / rel
        sha, size = digest_file(p)
        row["sha256"] = sha
        row["bytes"] = size
        row["present"] = p.is_file()
        seen.add(rel)
        print(f"  manifest {uid} {rel} sha={sha[:12]} bytes={size}")
    missing = wanted - seen
    if missing:
        print(f"  NOT-IN-MANIFEST {uid}: {sorted(missing)}")
    mp.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")


def fix_cnf0001() -> None:
    print("=== CNF-0001 ===")
    refresh_manifest(
        "CNF-0001",
        ["command-center/schema/confirmation-receipt.schema.json"],
    )


def fix_cnf0169() -> None:
    print("=== CNF-0169 ===")
    here = REPO / "command-center" / "p2-wave" / "probes" / "CNF-0169"
    sys.path.insert(0, str(here))
    import differ as D  # noqa: E402
    import emit_report as E  # noqa: E402

    live = D.load_live(REPO, extra_receipts=["CNF-0169"])
    art = REPO / "command-center/receipts/CNF-0169.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    doc["report_kind"] = "evidence-integrity"
    doc["five_way_agree"] = live["five_way_agree"]
    doc["sources"] = E.public_sources(live)
    doc["pairwise_differences"] = E.public_pairs(live)
    rpt = doc.get("report")
    if isinstance(rpt, dict):
        rpt["kind"] = rpt.get("kind") or "evidence-integrity-report"
        rpt["report_kind"] = "evidence-integrity"
        rpt["pairwise_differences"] = doc["pairwise_differences"]
        rpt["sources"] = doc["sources"]
        rpt["five_way_agree"] = live["five_way_agree"]
    art.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    n_pairs = len(doc["pairwise_differences"])
    print(
        f"  report_kind=evidence-integrity pairs={n_pairs} "
        f"five_way_agree={live['five_way_agree']} "
        f"catalog_n={live['sources']['catalog']['id_count']}"
    )
    refresh_manifest("CNF-0169", [E.OUT])


def check_cnl0058() -> None:
    print("=== CNL-0058 schema check ===")
    import jsonschema

    art = REPO / (
        "command-center/design/council/"
        "CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md"
    )
    schema_path = REPO / "command-center/schema/council-design-note.schema.json"
    doc = json.loads(art.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    live_errs = list(validator.iter_errors(doc))
    mutant = dict(doc)
    mutant.pop("reviewer", None)
    mutant_errs = list(validator.iter_errors(mutant))
    garbage = list(validator.iter_errors({"totally": "unrelated"}))
    print(
        f"  live_errs={len(live_errs)} "
        f"reviewer_stripped_errs={len(mutant_errs)} "
        f"garbage_errs={len(garbage)} "
        f"has_reviewer={isinstance(doc.get('reviewer'), dict)}"
    )
    if live_errs:
        print("  live first:", live_errs[0].message)
    if not mutant_errs:
        print("  WINDOWS schema also accepts reviewer-stripped")


def refresh_aud0089() -> None:
    print("=== AUD-0089 probe timeout bump ===")
    refresh_manifest(
        "AUD-0089",
        ["command-center/p2-wave/probes/AUD-0089/probe1_lizard.py"],
    )


def main() -> int:
    fix_cnf0001()
    fix_cnf0169()
    check_cnl0058()
    refresh_aud0089()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
