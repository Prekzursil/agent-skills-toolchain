#!/usr/bin/env python3
"""Probe 2: re-read cited gates; both-states control on the gap table."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
UNIT = "RES-0112"
ART = REPO / "command-center/research/RES-0112.json"
FORBIDDEN_IN_G1 = (
    "pause_point",
    "pause-point",
    "sign_in",
    "time_out",
    "read-do",
    "read_do",
    "do-confirm",
    "do_confirm",
    "challenge-response",
    "do-list",
)


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def load_lines(rel: str) -> list[str]:
    path = REPO / rel
    if not path.is_file():
        raise FileNotFoundError(rel)
    return path.read_text(encoding="utf-8").splitlines()


def snippet_hits(rel: str, line: int, snippet: str, end_line: int | None) -> bool:
    lines = load_lines(rel)
    lo = max(1, line)
    hi = end_line if isinstance(end_line, int) and end_line >= lo else lo
    if hi > len(lines) or lo > len(lines):
        return False
    window = "\n".join(lines[lo - 1 : hi])
    return snippet in window


def table_ok(table: list) -> tuple[bool, str]:
    if not isinstance(table, list) or not table:
        return False, "empty-table"
    already = [r for r in table if r.get("status") == "already-satisfied"]
    absent = [r for r in table if r.get("status") == "absent"]
    if not already:
        return False, "no-already-satisfied"
    if not absent:
        return False, "no-absent"
    for row in table:
        for c in row.get("gate_citations") or []:
            rel = str(c.get("path") or "")
            line = c.get("line")
            snip = str(c.get("snippet") or "")
            if not rel or not isinstance(line, int) or not snip:
                return False, f"bad-cite:{row.get('property_id')}"
            if not snippet_hits(rel, line, snip, c.get("end_line")):
                return False, f"snippet-miss:{rel}:{line}"
        if row.get("status") == "absent":
            # Absence must be measured on the cited gate, not assumed.
            rel = (row.get("gate_citations") or [{}])[0].get("path")
            body = (REPO / str(rel)).read_text(encoding="utf-8").lower()
            if row.get("property_id") == "pause-points":
                if "pause_point" in body or "sign-in" in body.replace("_", "-"):
                    return False, "pause-points-unexpectedly-named-in-g1"
            if row.get("property_id") == "read-do-versus-do-confirm":
                hits = [tok for tok in FORBIDDEN_IN_G1 if tok in body]
                # do-confirm analog exists as live re-run, but must not be named as the split
                named_split = [t for t in hits if t in ("read-do", "read_do", "do-confirm", "do_confirm", "challenge-response", "do-list")]
                if named_split:
                    return False, f"method-split-named-in-g1:{named_split}"
    return True, "ok"


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    table = doc.get("property_gap_table") or []
    ok, why = table_ok(table)
    if not ok:
        return fail(f"live table {why}")

    # Both-states: stripping already-satisfied rows MUST fail (control is load-bearing).
    stripped = copy.deepcopy(table)
    for row in stripped:
        if row.get("status") == "already-satisfied":
            row["status"] = "absent"
    ok_bad, why_bad = table_ok(stripped)
    if ok_bad:
        return fail("control silent: table still ok after removing already-satisfied")
    if why_bad != "no-already-satisfied":
        return fail(f"control fired for the wrong reason {why_bad!r}")

    # Both-states: a forged file:line that is not on disk MUST fail.
    forged = copy.deepcopy(table)
    forged[0]["gate_citations"][0]["snippet"] = "this-snippet-is-not-in-the-gate"
    ok_forge, why_forge = table_ok(forged)
    if ok_forge:
        return fail("control silent: forged snippet accepted")
    if not str(why_forge).startswith("snippet-miss:"):
        return fail(f"forged snippet reason {why_forge!r}")

    contrast = None
    for row in table:
        if row.get("property_id") == "pause-points":
            contrast = row.get("contrast_not_this_gate")
    if isinstance(contrast, dict):
        if not snippet_hits(
            str(contrast["path"]),
            int(contrast["line"]),
            str(contrast["snippet"]),
            None,
        ):
            return fail("plugin-install contrast snippet miss")

    out = {
        "pass": True,
        "probe": "probe2-gate-measure",
        "unit_id": UNIT,
        "live_table": why,
        "control_stripped": why_bad,
        "control_forged": why_forge,
        "absent_measured_on_disk": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(f"live={why} stripped={why_bad} forged={why_forge}")
    print(f"SUCCESS:{UNIT}-probe2 gate file:line measured; both-states fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
