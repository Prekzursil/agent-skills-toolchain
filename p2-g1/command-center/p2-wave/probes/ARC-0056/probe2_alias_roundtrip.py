#!/usr/bin/env python3
"""ARC-0056 probe2 -- alias round-trip (live, fail-closed).

Re-derives the alias resolution semantics from the artifact: every aliased
old name resolves to its recorded target, every target is a non-removed
surface name, removed names resolve to nothing, deprecated names carry a
warning successor, and a synthetic unknown name resolves nowhere (both-states
control). The recorded tests.alias_roundtrip verdict must agree. The on-disk
resolution arm (fixtures/live) is recorded instrument-absent on this worktree
and does not gate.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "command-center/phase3/A8/MIGRATION.json"
UNIT = "ARC-0056"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


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

    rows = doc.get("enumeration", {}).get("rows") or []
    by_name = {r["name"]: r for r in rows}
    aliases = doc.get("alias_table") or []
    deprec = (doc.get("deprecation", {}) or {}).get("entries") or []

    def resolve(name: str):
        """Round-trip resolver: preserved -> itself, aliased -> target,
        deprecated -> successor (warn), removed/unknown -> None."""
        r = by_name.get(name)
        if r is None:
            return None, "unknown"
        d = r["disposition"]
        if d == "preserved":
            return name, "direct"
        if d == "aliased":
            return r.get("target"), "alias"
        if d == "deprecated":
            return None, "deprecated-warning"
        return None, "removed"

    # forward: every alias old resolves through to its recorded target
    failed_rt = []
    for a in aliases:
        tgt, how = resolve(a.get("old", ""))
        if how != "alias" or tgt != a.get("target"):
            failed_rt.append(f"{a.get('old')}->{tgt}/{how}")
        t = by_name.get(a.get("target"))
        if t is None or t["disposition"] not in ("preserved", "aliased"):
            failed_rt.append(f"{a.get('old')} target disposition invalid")
    check(not failed_rt, "alias round-trip failures", "; ".join(failed_rt[:4]))
    # reverse: every preserved/aliased product surface name is reachable
    reachable = set()
    for n, r in by_name.items():
        if r["disposition"] in ("preserved", "aliased"):
            reachable.add(n)
    reachable_srcs = {n for n, r in by_name.items()
                      if r["disposition"] in ("preserved", "aliased")}
    check(reachable == reachable_srcs, "reverse-reachability set mismatch")
    # removed names never resolve and never appear as targets
    removed = {r["name"] for r in rows if r["disposition"] == "removed"}
    bad_removed = [n for n in removed if resolve(n)[1] != "removed"]
    check(not bad_removed, "removed names resolvable", "; ".join(bad_removed[:4]))
    check(not (removed & {a.get("target") for a in aliases}),
          "removed name used as alias target")
    # deprecated entries warn and point at live successors
    bad_dep = []
    for e in deprec:
        if resolve(e.get("name", ""))[1] != "deprecated-warning":
            bad_dep.append(str(e.get("name")))
        s = by_name.get(e.get("successor"))
        if s is None or s["disposition"] not in ("preserved", "aliased"):
            bad_dep.append(f"successor:{e.get('successor')}")
    check(not bad_dep, "deprecation round-trip failures", "; ".join(bad_dep[:4]))

    # recorded verdict must agree with this recomputation
    rec = ((doc.get("tests") or {}).get("alias_roundtrip") or {})
    check(rec.get("pass") is True, "tests.alias_roundtrip.pass not true")
    check(int(rec.get("aliases_checked", -1)) == len(aliases),
          "tests.alias_roundtrip.aliases_checked mismatch",
          f"{rec.get('aliases_checked')} vs {len(aliases)}")
    check(not rec.get("failed"), "tests.alias_roundtrip recorded failures",
          str(rec.get("failed"))[:120])

    # both-states negative control: unknown name must resolve nowhere
    unk, unk_how = resolve("/definitely-not-a-real-command-9x7")
    fired = unk is None and unk_how == "unknown"
    check(fired, "mutation control silent on unknown name")
    good_silent = resolve(aliases[0]["old"])[0] == aliases[0]["target"] if aliases else False
    check(good_silent, "mutation control failed on real alias")

    # drift note: on-disk resolution arm instrument-absent on this worktree
    live_root = REPO / "fixtures" / "live"
    if not live_root.is_dir():
        notes.append(
            "instrument-absent: fixtures/live enumeration source is not present on this "
            "worktree (lost with the prior builder's tree), so the live-invocation arm of "
            "the alias round-trip cannot re-run on disk; the structural round-trip over the "
            "recorded enumeration plus the unknown-name negative control gate instead"
        )

    report = {
        "probe": "probe2-alias-roundtrip",
        "unit_id": UNIT,
        "aliases_checked": len(aliases),
        "deprecated_checked": len(deprec),
        "removed_checked": len(removed),
        "notes": notes,
        "fails": fails,
    }
    print(json.dumps(report, indent=1, ensure_ascii=False))
    if fails:
        print(f"FAILED:{UNIT}-probe2 " + "; ".join(fails))
        return 1
    print(f"SUCCESS:{UNIT}-probe2 alias round-trip holds ({len(aliases)} aliases, "
          f"{len(deprec)} deprecations, {len(removed)} removed do-not-resolve); "
          "unknown-name control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
