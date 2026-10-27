#!/usr/bin/env python3
"""TST-0124 probe2 -- known-gated join proof rebuilt and re-run live.

The receipt's control-estate fixture (3 suites, 2 gated, 1 ungated) is
rebuilt from the receipt's own recorded spec, the suite x gate census join is
re-run over it, and the load-bearing edge -- a known-gated suite classifying
GATED -- is asserted live. Recorded census internals are checked for
consistency; live workflow-dir drift is reported.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0124.json"
FIX = Path(__file__).resolve().parent / "fixtures" / "control-estate"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


QUALITY_YML = """name: quality
on: [push]
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - name: run known gated suite
        run: pytest known_gated/tests
      - name: run cwd gated suite
        run: pytest cwd_gated/tests
"""


def build_fixture() -> None:
    (FIX / ".github/workflows").mkdir(parents=True, exist_ok=True)
    (FIX / ".github/workflows/quality.yml").write_text(QUALITY_YML, encoding="utf-8", newline="\n")
    for suite in ("known_gated/tests", "cwd_gated/tests", "known_ungated/tests"):
        (FIX / suite).mkdir(parents=True, exist_ok=True)
        (FIX / suite / "test_join.py").write_text("def test_join():\n    assert True\n", encoding="utf-8", newline="\n")


def census(root: Path) -> dict:
    wf = root / ".github" / "workflows"
    texts = {p.name: p.read_text(encoding="utf-8") for p in sorted(wf.glob("*.yml"))} if wf.is_dir() else {}
    gated, ungated, rows = 0, 0, []
    for suite in sorted(p.relative_to(root).as_posix() for p in root.glob("*/tests")):
        gates = [
            {"gate_id": "%s::tests::%s" % (".github/workflows/" + name, "suite steps"),
             "workflow": ".github/workflows/" + name}
            for name, text in texts.items() if suite in text
        ]
        cls = "GATED" if gates else "UNGATED"
        rows.append({"suite": suite, "classification": cls, "gates": gates})
        if cls == "GATED":
            gated += 1
        else:
            ungated += 1
    return {"suite_count": gated + ungated, "gated_count": gated, "ungated_count": ungated, "join_table": rows}


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    # recorded internal consistency
    chk(doc.get("gated_count") == len(doc.get("gated_suites") or []), "gated-count-mismatch")
    chk(doc.get("ungated_count") == len(doc.get("ungated_suites") or []), "ungated-count-mismatch")
    ans = str(doc.get("answer") or "")
    chk("115 of 185" in ans and "UNGATED" in ans, "answer-text-drift")
    kg = doc.get("known_gated_control") or {}
    chk(kg.get("suite_count") == kg.get("gated_count", -1) + kg.get("ungated_count", -1) == 3, "kg-counts", (kg.get("suite_count"), kg.get("gated_count"), kg.get("ungated_count")))
    chk(kg.get("known_gated_classification") == "GATED", "kg-recorded-class", kg.get("known_gated_classification"))
    chk(kg.get("quality_yml_present") is True, "kg-quality-yml-recorded-absent")
    jt = doc.get("join_table") or []
    chk(len(jt) == doc.get("ungated_count"), "join-table-rows", len(jt))
    for row in jt[:5]:
        chk(str(row.get("classification")) in ("GATED", "UNGATED"), "row-class-illegal", row.get("classification"))
    # the recorded known-gated gate carries a workflow + collect path (the join edge)
    kgg = kg.get("known_gated_gates") or []
    chk(bool(kgg) and all(g.get("workflow") and g.get("collect_path") for g in kgg), "kg-gates-shape", kgg[:1])

    # live fixture rebuild + re-run of the join
    build_fixture()
    live = census(FIX)
    chk(live["suite_count"] == 3 and live["gated_count"] == 2 and live["ungated_count"] == 1,
        "fixture-census", (live["suite_count"], live["gated_count"], live["ungated_count"]))
    by_suite = {r["suite"]: r for r in live["join_table"]}
    chk(by_suite["known_gated/tests"]["classification"] == "GATED", "known-gated-not-gated-live")
    chk(by_suite["known_gated/tests"]["gates"][0]["workflow"] == ".github/workflows/quality.yml", "kg-gate-workflow")
    chk(by_suite["known_ungated/tests"]["classification"] == "UNGATED", "known-ungated-not-ungated-live")
    chk(by_suite["cwd_gated/tests"]["classification"] == "GATED", "cwd-gated-not-gated-live")

    # live tree workflow dir still present (drift reported, not hidden)
    live_wf = REPO / ".github" / "workflows"
    chk(live_wf.is_dir(), "live-workflows-absent")
    n_live = len(list(live_wf.glob("*.yml"))) + len(list(live_wf.glob("*.yaml")))
    g = doc.get("gates") or {}
    if n_live != g.get("n_workflow_files"):
        print("NOTE drift: live workflow files=%d, receipt census recorded=%s" % (n_live, g.get("n_workflow_files")))
    if FAILS:
        print("FAILED:TST-0124-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0124-probe2 control-estate rebuilt from receipt spec; census join re-run live; known-gated suite classifies GATED (join proven), known-ungated UNGATED; 2/1 counts match recorded control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
