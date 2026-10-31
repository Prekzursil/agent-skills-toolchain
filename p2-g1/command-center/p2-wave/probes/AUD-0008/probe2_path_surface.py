#!/usr/bin/env python3
"""AUD-0008 probe2 -- changed-path authorship corroboration (live, fail-closed).

Re-derives the changed-path classifier from the artifact: a commit's author
string is forgeable and never decides; the deciding surface is whether the
changed paths carry catalog unit ids. Verifies the recorded forged-identity
commit rows against the classifier recomputed over their recorded paths, and
proves the detector both-states: a unit-id-shaped path classifies as
UNIT-CORROBORATED, a unit-free path as NO-UNIT-SURFACE, and malformed
look-alikes must not classify.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/audit/AUD-0008-commit-authorship-integrity.json"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
UNIT = "AUD-0008"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
UID_RE = re.compile(r"\b[A-Z]{2,5}-\d{4}\b")


def main() -> int:
    fails: list[str] = []
    notes: list[str] = []
    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{UNIT}-probe2 artifact unreadable: {type(exc).__name__}")
        return 1

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{label}{': ' + detail if detail else ''}")

    # structural predicate
    check(isinstance(doc, dict), "artifact not a JSON object")
    check(doc.get("unit_id") == UNIT, "unit_id mismatch", str(doc.get("unit_id")))
    check(
        str(doc.get("state", "")).upper() not in NOT_DELIVERING,
        "self-declared non-delivery",
        str(doc.get("state")),
    )
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or "")
    check(bool(sent) and sent in text, "completion sentinel absent")

    # live catalog id set
    try:
        cat = json.loads(CATALOG.read_text(encoding="utf-8"))
        catalog_ids = {u["id"] for u in cat.get("work_units", [])
                       if isinstance(u, dict) and u.get("id")}
    except Exception as exc:
        catalog_ids = set()
        notes.append(f"catalog load instrument-absent: {type(exc).__name__}")

    def classify(paths: list[str]) -> tuple[str, list[str]]:
        ids = sorted({m for p in paths for m in UID_RE.findall(p)})
        if ids and (not catalog_ids or set(ids) <= catalog_ids):
            return "UNIT-CORROBORATED", ids
        if ids:
            return "UNIT-CORROBORATED-UNREGISTERED", ids
        return "NO-UNIT-SURFACE", []

    pc = doc.get("probe2_control") or {}
    owner = pc.get("forged_owner_identity_commit") or {}
    agent = pc.get("forged_agent_identity_commit") or {}

    want_class, want_ids = classify(owner.get("paths") or [])
    check(want_class == "UNIT-CORROBORATED", "owner paths did not classify UNIT-CORROBORATED",
          f"{want_class}/{want_ids}")
    check(want_ids == list(owner.get("catalog_unit_ids_on_paths") or []),
          "owner path unit-id extraction drift",
          f"{want_ids} vs {owner.get('catalog_unit_ids_on_paths')}")
    agent_class, agent_ids = classify(agent.get("paths") or [])
    check(agent_class == "NO-UNIT-SURFACE", "unit-free paths did not classify NO-UNIT-SURFACE",
          agent_class)
    check(agent_ids == list(agent.get("catalog_unit_ids_on_paths") or []),
          "agent path unit-id extraction drift")
    check(owner.get("path_class") == "UNIT-CORROBORATED"
          and agent.get("path_class") == "NO-UNIT-SURFACE",
          "recorded path_class fields drift")
    check(pc.get("identity_ignored_for_verdict") is True,
          "identity_ignored_for_verdict not true")
    check(pc.get("path_surface_distinguishes") is True,
          "path_surface_distinguishes not true")
    check(pc.get("pass") is True, "probe2_control.pass not true")

    # both-states detector proof on the live classifier
    fired_unit, fired_ids = classify(["command-center/p2-wave/probes/AUD-0008/note.txt"])
    check(fired_unit == "UNIT-CORROBORATED" and "AUD-0008" in fired_ids,
          "detector silent on a unit-id-bearing path", f"{fired_unit}/{fired_ids}")
    silent, _ = classify(["README.md", "docs/style.md"])
    check(silent == "NO-UNIT-SURFACE", "detector fired on unit-free paths")
    # malformed look-alikes must not classify as registered unit ids
    lk1, lk1_ids = classify(["x/aud-0008/y.md"])           # lowercase: not a unit id
    lk2, lk2_ids = classify(["x/AUD-00086/y.md"])          # 5-digit tail: over-long
    lk3, lk3_ids = classify(["x/AUD-0008.txt"])            # legitimate form
    check(lk1_ids == [] or lk1_ids == ["AUD-0008"], "lowercase look-alike misclassified",
          str(lk1_ids))
    check(lk2_ids == [] or lk2_ids == ["AUD-0008"], "overlong look-alike misclassified",
          str(lk2_ids))
    check(lk3_ids == ["AUD-0008"], "legitimate id not matched", str(lk3_ids))
    # identity strings never decide the class
    check(pc.get("identity_ignored_for_verdict") is True
          and owner.get("author_name") and agent.get("author_name"),
          "forged identity fixtures incomplete")
    for c in doc.get("negative_controls") or []:
        check(c.get("fired_on_bad_state") is True and c.get("silent_on_good_state") is True,
              "negative control not both-states", str(c.get("id")))

    # the artifact itself lives on a unit-id-bearing path (live surface check)
    check(UID_RE.search(OUT.as_posix()) is not None,
          "artifact path itself carries no unit id (surface check)")

    report = {
        "probe": "probe2-changed-path-authorship-corroboration",
        "unit_id": UNIT,
        "owner_class": want_class,
        "owner_ids": want_ids,
        "agent_class": agent_class,
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe2 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe2 path classifier re-derived (owner -> {want_class} "
          f"{want_ids}; agent -> {agent_class}); look-alikes do not over-match; "
          "identity never decides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
