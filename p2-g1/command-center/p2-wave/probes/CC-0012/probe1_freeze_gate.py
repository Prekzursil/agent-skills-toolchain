#!/usr/bin/env python3
"""CC-0012 probe1 - freeze gate live + both-states in a scratch tree.

Live: the FREEZE.json ledger matches the bytes on disk (live sha == ledger
sha == snapshot sha for all three frozen rows), counts and fingerprint agree
with the receipt, bump_rules carries the no-version-bump reason, and
evaluate_gate on the real repo root is SILENT (tree quiescent vs freeze).
Both-states in a scratch tree: an unversioned edit to a frozen schema is
REJECTED with no-version-bump; the same edit WITH a version bump and a
migration is ADMITTED; an edit to a non-frozen control file is silent.
Rebuilt 2026-10-26 (wave-3 shard 7) after the original probe tree was lost.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "command-center"))
OUT = REPO / "command-center/receipts/CC-0012.json"
UNIT = "CC-0012"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}

from freeze.lib import evaluate_gate, load_migrations  # noqa: E402


def norm_digest(p):
    raw = Path(p).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    fails = []
    checks = []

    def check(ok, label, detail=""):
        checks.append({"check": label, "ok": bool(ok), "detail": str(detail)[:300]})
        if not ok:
            fails.append(label + (": " + str(detail)[:200] if detail else ""))

    text = OUT.read_text(encoding="utf-8")
    doc = json.loads(text)
    check(doc.get("unit_id") == UNIT, "unit_id matches catalog unit")
    check(str(doc.get("state", "")).upper() not in NOT_DELIVERING,
          "artifact not self-declared non-delivery", str(doc.get("state")))
    check(OUT.stat().st_size > 0, "artifact non-empty")
    sentinel = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sentinel) and sentinel in text, "sentinel present in artifact text")
    # ---- live freeze ledger vs disk ----
    ledger_path = REPO / "command-center/freeze/FREEZE.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    check(ledger.get("freeze_id") == "CC-0012-freeze",
          "freeze ledger id matches", str(ledger.get("freeze_id")))
    rows = ledger.get("frozen_paths") or []
    check(len(rows) == ledger.get("frozen_count") == 3,
          "frozen_count is 3 and matches the row list", str(len(rows)))
    check(ledger.get("schema_count") == 2 and ledger.get("launcher_count") == 1,
          "2 schemas + 1 launcher frozen")
    allcurrent = True
    drift = []
    for row in rows:
        live_sha, _ = norm_digest(REPO / row["path"])
        snap_sha, _ = norm_digest(REPO / row["snapshot"])
        if live_sha != row["sha256"] or snap_sha != row["sha256"]:
            allcurrent = False
            drift.append(row["path"])
    check(allcurrent, "every frozen row: live sha == ledger sha == snapshot sha",
          "drift=" + str(drift))
    rules = json.loads((REPO / "command-center/freeze/bump_rules.json")
                       .read_text(encoding="utf-8"))
    check(rules.get("no_version_bump_reason") == "no-version-bump",
          "bump_rules carries the no-version-bump reason")
    check(doc.get("freeze", {}).get("freeze_fingerprint_sha256")
          == ledger.get("freeze_fingerprint_sha256"),
          "receipt freeze fingerprint equals the live ledger fingerprint")
    check(doc.get("freeze", {}).get("active") is True
          and ledger.get("activation_commit_kind") in {"git-HEAD", "git-unavailable"},
          "freeze active; activation commit kind recorded honestly",
          str(ledger.get("activation_commit_kind")))
    # ---- evaluate_gate on the real repo: silent ----
    gate = evaluate_gate(REPO)
    check(gate.get("ok") is True and gate.get("reason") == "silent",
          "evaluate_gate on the real tree is silent (frozen bytes pristine)",
          json.dumps(gate.get("rejections"))[:200])
    check(gate.get("silent_count") == 3, "3 frozen files silent")

    # ---- both-states in a scratch tree ----
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        # replicate minimal freeze structure
        for sub in ("command-center/schema", "command-center/freeze/snapshots",
                    "command-center/freeze"):
            (tdp / sub).mkdir(parents=True, exist_ok=True)
        for row in rows:
            shutil.copyfile(REPO / row["path"], tdp / row["path"])
            shutil.copyfile(REPO / row["snapshot"], tdp / row["snapshot"])
        shutil.copyfile(ledger_path, tdp / "command-center/freeze/FREEZE.json")
        shutil.copyfile(REPO / "command-center/freeze/bump_rules.json",
                        tdp / "command-center/freeze/bump_rules.json")
        frozen_rel = rows[0]["path"]

        # (a) unversioned edit -> REJECTED no-version-bump
        target = tdp / frozen_rel
        target.write_bytes(target.read_bytes() + b" ")
        g1 = evaluate_gate(tdp)
        rejected = (not g1["ok"]) and any(
            r["reason"] == "no-version-bump" and r["path"] == frozen_rel
            for r in g1["rejections"])
        check(rejected, "unversioned frozen edit REJECTED with no-version-bump",
              json.dumps(g1.get("rejections"))[:200])
        target.write_bytes((REPO / frozen_rel).read_bytes())

        # (b) version bump + migration -> ADMITTED
        bumped = json.loads(target.read_text(encoding="utf-8"))
        bumped["schema_version"] = 2
        target.write_text(json.dumps(bumped, indent=1) + "\n",
                          encoding="utf-8", newline="\n")
        migdir = tdp / "command-center/freeze/migrations"
        migdir.mkdir(parents=True, exist_ok=True)
        mig_src = "\"\"\"scratch migration for the probe\"\"\"\n"
        mig_src += "MIGRATION_ID = 'm0002-probe'\nFROM_VERSION = 1\nTO_VERSION = 2\n"
        mig_src += "TARGETS = ['" + frozen_rel + "']\n"
        mig_src += "def up(d):\n    return d\n\n"
        mig_src += "def down(d):\n    return d\n"
        (migdir / "m0002_probe.py").write_text(mig_src, encoding="utf-8",
                                               newline="\n")
        g2 = evaluate_gate(tdp)
        admitted = [a for a in g2.get("admitted", [])
                    if a.get("path") == frozen_rel
                    and a.get("reason") == "version-bump-with-migration"]
        check(bool(admitted), "version bump + migration ADMITTED",
              json.dumps(g2.get("admitted"))[:200])
        check(admitted and admitted[0].get("migration") == "m0002-probe",
              "admission names the scratch migration")

        # (c) non-frozen control file edit -> gate stays silent
        ctrl = tdp / "command-center/receipts"
        ctrl.mkdir(parents=True, exist_ok=True)
        (ctrl / "control-receipt.json").write_text("{\"unfrozen\": true}\n",
                                                   encoding="utf-8", newline="\n")
        g3 = evaluate_gate(tdp)
        check(g3.get("ok") is True,
              "non-frozen control edit leaves the gate silent")
    # ---- migrations visible from the real repo ----
    migs = load_migrations(REPO)
    check(any(m.id == "m0001_catalog_v2_v3" and m.from_version == 2
              and m.to_version == 3 for m in migs),
          "m0001_catalog_v2_v3 (v2->v3) loadable from the real migrations dir",
          str([m.id for m in migs]))

    report = {
        "probe": "probe1-freeze-gate",
        "unit_id": UNIT,
        "artifact_bytes": OUT.stat().st_size,
        "checks": checks,
        "fails": fails,
    }
    print(json.dumps(report, indent=1))
    if fails:
        print("FAILED:" + UNIT + "-probe1 " + "; ".join(fails))
        return 1
    print("SUCCESS:" + UNIT + "-probe1 freeze gate live, both-states hold")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
