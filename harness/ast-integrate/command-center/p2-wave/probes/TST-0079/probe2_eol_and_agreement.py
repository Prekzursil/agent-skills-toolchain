#!/usr/bin/env python3
"""Probe 2: EOL-only is not content drift; independent differ agrees.

Required test:
  test_eol_only_differences_are_not_reported_as_content_drift

Both-states: identical pair is silent; planting a content edit fires.
Independent differ must match the tool on every fixture file; disagreement
is BLOCKED, not a picked winner.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import independent_differ as D  # noqa: E402
import sync_tool as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0079.json"
OUT = HERE / "probe2-eol-agreement.raw.json"


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:TST-0079-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:3000])
    return 1


def test_eol_only_differences_are_not_reported_as_content_drift(repo: Path, live: Path) -> dict:
    rel = "common/eol-only.md"
    rp, lp = repo / rel, live / rel
    rec = S.classify_pair(rp.read_bytes(), lp.read_bytes())
    if rec["class"] != S.EOL_ONLY:
        raise AssertionError(f"eol-only classified as {rec['class']}")
    if rec["content_drift"]:
        raise AssertionError("eol-only reported as content_drift")
    if rec["repo_unique_lines"] or rec["live_unique_lines"]:
        raise AssertionError("eol-only listed unique lines")

    census = S.classify_trees(repo, live)
    eol_rows = [r for r in census["rows"] if r["path"] == rel]
    if len(eol_rows) != 1 or eol_rows[0]["class"] != S.EOL_ONLY:
        raise AssertionError(f"census eol-only row: {eol_rows}")
    if census["counts"][S.EOL_ONLY] < 1:
        raise AssertionError("census missing eol-only count")
    drift_paths = [r["path"] for r in census["rows"] if r["content_drift"]]
    if rel in drift_paths:
        raise AssertionError("eol-only appeared in content-drift list")

    r2l = S.apply_sync_pair(rp, lp, S.DIR_REPO_TO_LIVE)
    if r2l["decision"] != S.PROCEED:
        raise AssertionError(f"eol-only sync refused: {r2l}")
    return {
        "id": "test_eol_only_differences_are_not_reported_as_content_drift",
        "result": "PASS",
        "class": rec["class"],
        "content_drift": False,
        "sync_decision": r2l["decision"],
    }


def independent_agreement(repo: Path, live: Path) -> dict:
    census = S.classify_trees(repo, live)
    rows = []
    for rec in census["rows"]:
        rb = (repo / rec["path"]).read_bytes() if rec["in_repo"] else None
        lb = (live / rec["path"]).read_bytes() if rec["in_live"] else None
        cmp = D.agree(rec["class"], rb, lb)
        rows.append({"path": rec["path"], **cmp})
    disagree = [r for r in rows if not r["agree"]]
    if disagree:
        raise AssertionError(f"independent differ disagreed: {disagree}")
    return {
        "id": "independent_differ_agrees",
        "result": "PASS",
        "files": len(rows),
        "agreements": len(rows),
        "disagreements": 0,
        "rows": rows,
    }


def both_states(root: Path) -> dict:
    trees = F.write_trees(root / "control")
    repo, live = trees["repo"], trees["live"]
    ident = "common/identical.md"
    good = S.classify_pair((repo / ident).read_bytes(), (live / ident).read_bytes())
    if good["class"] != S.IDENTICAL or good["content_drift"]:
        raise AssertionError(f"identical control not silent: {good}")

    planted = (live / ident).read_bytes() + b"PLANTED-CONTENT-EDIT\n"
    (live / ident).write_bytes(planted)
    bad = S.classify_pair((repo / ident).read_bytes(), (live / ident).read_bytes())
    if bad["class"] != S.LIVE_AHEAD or not bad["content_drift"]:
        raise AssertionError(f"planted edit did not fire: {bad}")
    (live / ident).write_bytes(good and (repo / ident).read_bytes())
    restored = S.classify_pair((repo / ident).read_bytes(), (live / ident).read_bytes())
    if restored["class"] != S.IDENTICAL:
        raise AssertionError(f"revert did not restore identical: {restored}")
    return {
        "id": "both_states_identical_vs_planted",
        "result": "PASS",
        "silent_on_good": True,
        "fired_on_bad": True,
        "silent_after_revert": True,
        "bad_class": bad["class"],
    }


def want_classes(repo: Path, live: Path) -> dict:
    census = S.classify_trees(repo, live)
    by_path = {r["path"]: r["class"] for r in census["rows"]}
    for rel, spec in F.FILES.items():
        if by_path.get(rel) != spec["want"]:
            raise AssertionError(f"{rel} want={spec['want']} got={by_path.get(rel)}")
    return {"id": "fixture_want_classes", "result": "PASS", "by_path": by_path}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        return fail("receipt artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0079":
        return fail("unit_id", doc.get("unit_id"))
    if "SUCCESS:TST-0079" not in text:
        return fail("sentinel-absent")

    with tempfile.TemporaryDirectory(prefix="tst0079-p2-") as tmp:
        root = Path(tmp)
        trees = F.write_trees(root / "base")
        t1 = test_eol_only_differences_are_not_reported_as_content_drift(
            trees["repo"], trees["live"]
        )
        # eol-only proceed mutated live; rebuild for agreement/census
        trees = F.write_trees(root / "agree")
        t2 = independent_agreement(trees["repo"], trees["live"])
        t3 = want_classes(trees["repo"], trees["live"])
        t4 = both_states(root)

    payload = {
        "pass": True,
        "probe": "probe2-eol-agreement",
        "unit_id": "TST-0079",
        "tests": [t1, t2, t3, t4],
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": True, "eol_not_drift": True, "agree": t2["agreements"]}))
    print(
        "eol_only_not_content_drift=True independent_agree=True "
        f"files={t2['files']} both_states=True"
    )
    print("SUCCESS:TST-0079-probe2 eol-only is not content drift; differs agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
