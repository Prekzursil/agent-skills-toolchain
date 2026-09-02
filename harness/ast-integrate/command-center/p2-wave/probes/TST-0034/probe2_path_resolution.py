#!/usr/bin/env python3
"""Probe 2: every marketplace plugin source resolves to a real on-disk path.

Independent of probe 1 (does not test canonical dump bytes). Evidence: each
listed entry is printed with its resolved path; unresolved count is printed.
Both-states: clean fixture unresolved=0; dangling source unresolved>=1 and
the suite fails.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.manifest_reader import (  # noqa: E402
    RULE_SOURCE_RESOLVABLE,
    canonical_live_document,
    canonical_plugin_document,
    check_manifest,
    dump_bytes,
    ensure_live_subject,
)

ART = REPO / "command-center/receipts/TST-0034.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def _write(root: Path, data: dict) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "marketplace.json").write_bytes(dump_bytes(data))
    (root / "plugin.json").write_bytes(dump_bytes(canonical_plugin_document()))
    return root / "marketplace.json"


def main() -> int:
    live = ensure_live_subject(REPO)
    report = check_manifest(live, REPO)
    for entry in report.entries:
        print(
            f"entry={entry.name} source={entry.source} "
            f"resolved={entry.resolved} exists={entry.exists} "
            f"plugin_json={entry.plugin_json_exists}"
        )
    print(
        f"listed={report.listed} resolved={report.resolved} "
        f"unresolved={report.unresolved}"
    )
    if report.listed < 1:
        print("FAILED:TST-0034-probe2 no plugin entries listed")
        return 1
    if report.unresolved != 0:
        print("FAILED:TST-0034-probe2 live unresolved count is not zero")
        return 1
    if report.resolved != report.listed:
        print("FAILED:TST-0034-probe2 resolved != listed")
        return 1
    for entry in report.entries:
        if not entry.exists or not entry.resolved:
            print("FAILED:TST-0034-probe2 entry missing on disk", entry)
            return 1
        if not Path(entry.resolved).exists():
            print("FAILED:TST-0034-probe2 resolved path vanished", entry.resolved)
            return 1
        if not entry.plugin_json_exists:
            print("FAILED:TST-0034-probe2 plugin.json missing at source", entry)
            return 1

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        clean = _write(base / "clean", canonical_live_document())
        dangling_doc = copy.deepcopy(canonical_live_document())
        dangling_doc["plugins"][0]["source"] = "./does-not-exist"
        mutant = _write(base / "dangling", dangling_doc)
        c = check_manifest(clean, REPO)
        m = check_manifest(mutant, REPO)
        print(
            f"both_states clean_ok={c.ok} mutant_ok={m.ok} "
            f"clean_unresolved={c.unresolved} mutant_unresolved={m.unresolved} "
            f"mutant_rules={sorted({f.rule for f in m.findings})}"
        )
        if not c.ok or c.unresolved != 0:
            print("FAILED:TST-0034-probe2 clean fixture failed", c.findings)
            return 1
        if m.ok or m.unresolved < 1:
            print("FAILED:TST-0034-probe2 dangling mutant did not fire")
            return 1
        if RULE_SOURCE_RESOLVABLE not in {f.rule for f in m.findings}:
            print("FAILED:TST-0034-probe2 dangling mutant missed resolvable rule")
            return 1

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            print("FAILED:TST-0034-probe2 self-declared", doc.get("state"))
            return 1
        census = doc.get("path_census") or {}
        art_unresolved = census.get("unresolved")
        if art_unresolved is None or int(art_unresolved) != 0:
            print("FAILED:TST-0034-probe2 artifact unresolved", census)
            return 1
        if int(census.get("listed") or 0) != report.listed:
            print(
                "FAILED:TST-0034-probe2 artifact listed mismatch",
                census.get("listed"),
                report.listed,
            )
            return 1

    print(
        "SUCCESS:TST-0034-probe2 every listed source exists; "
        f"unresolved={report.unresolved}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
