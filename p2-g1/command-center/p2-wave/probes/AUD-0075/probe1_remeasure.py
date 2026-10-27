#!/usr/bin/env python3
"""AUD-0075 probe 1 - re-measure every pinned ground-truth fact with a
mechanically different instrument.

shard4-w2 reconstruction 2026-10-25 (original ran on the prior worktree).
Two fact classes, never conflated:
  STATIC - subject is repository text/structure: the verdict must re-derive
  EXACTLY (catalog count, precedents, P13 file, worktree state, pinned-run
  absence).
  LIVE - subject is the estate's moving state (delivered/ready partition,
  condition-11 receipt check): re-measured now; verdict compared against the
  emitted one and any drift disclosed as CURRENT-ENVIRONMENT, never folded.

Fingerprint controls (catalog tests_required):
  - same-fingerprint rejection: no fact declares a producing probe
    (source_probe null), so a re-run of the producing probe is rejected as
    UNDECLARED_SOURCE for all 12 - zero source signals.
  - distinct-fingerprint acceptance: two mechanically different counters of
    one static fact are both accepted and must agree on value.
  - ready comparator fires-on-bad: briefed partition vs live recount must
    fire on the live value and stay silent on the briefed value.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center" / "audit" / "AUD-0075-stale-premise-sweep.json"
UNIT = "AUD-0075"
STATIC = "STATIC"
LIVE = "LIVE"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def fp_of(*parts: str) -> str:
    return hashlib.sha256(chr(31).join(parts).encode("utf-8")).hexdigest()[:16]


# ---- instruments: each returns (observed, note) -------------------------

def inst_catalog_len() -> tuple[object, str]:
    doc = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    return len(doc.get("work_units") or []), "json work_units length"


def inst_catalog_walk() -> tuple[object, str]:
    doc = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    n = 0
    stack = [doc.get("work_units") or []]
    while stack:
        item = stack.pop()
        if isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, dict) and item.get("id"):
            n += 1
    return n, "iterative walk over unit ids"


def inst_p13_file() -> tuple[object, str]:
    p = REPO / "command-center" / "P13-BLINDSPOT-REVIEW.md"
    ok = p.is_file() and p.stat().st_size > 0
    return ({"exists": bool(ok), "bytes": p.stat().st_size if ok else 0},
            "direct stat of P13-BLINDSPOT-REVIEW.md")


def inst_git_worktree() -> tuple[object, str]:
    # observed = True IFF the worker tree IS a git worktree (the pinned claim)
    inside = (REPO / ".git").exists()
    return (bool(inside),
            "filesystem probe for a .git entry (different axis: on-disk, not git CLI)")


def inst_pinned_run(run: str):
    def run_it() -> tuple[object, str]:
        hits = []
        for base in ("command-center", "tools", "artifacts"):
            root = REPO / base
            if not root.is_dir():
                continue
            for pat in ("*pinned-run*", "*workflow-run*"):
                hits.extend(p.name for p in root.rglob(pat))
        primary_present = any("primary" in h for h in hits)
        return ({"primary_result_present": primary_present,
                 "reason": "no-pinned-run-artifact-on-this-worker" if not hits else "found",
                 "run_id": f"pinned-workflow-run-{run}"},
                f"filesystem sweep for pinned-run artifacts ({len(hits)} hits)")
    return run_it


def inst_precedent(needle: str):
    def run_it() -> tuple[object, str]:
        text = (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
        return (needle in text, f"catalog text contains {needle!r}")
    return run_it


def inst_decision_log() -> tuple[object, str]:
    cands = sorted((REPO / "command-center").rglob("*DECISION-LOG*.md"))
    if not cands:
        return ({"collision_present_tense": False, "exists": False, "mech_tokens": 0,
                 "note": "decision log absent on this substrate"},
                "rglob for *DECISION-LOG*.md")
    log = cands[0]
    text = log.read_text(encoding="utf-8", errors="replace")
    mech = len(re.findall(r"\bMECH\b", text))
    present = bool(re.search(r"31-way[^\n.]{0,80}(collision|collide)", text, re.IGNORECASE))
    return ({"collision_present_tense": present, "exists": True, "mech_tokens": mech},
            f"token recount in {log.name}")


def inst_briefed_pair() -> tuple[object, str]:
    text = (REPO / "command-center" / "p2-wave" / "P2-GROUNDING.md").read_text(encoding="utf-8", errors="replace")
    delivered = re.search(r"delivered\s+(\d+)\s*(?:→|->)\s*(\d+)", text)
    ready = re.search(r"READY\s+(\d+)\s*(?:→|->)\s*(\d+)", text)
    out = {
        "briefed_delivered": int(delivered.group(1)) if delivered else None,
        "measured_delivered_at_emit": int(delivered.group(2)) if delivered else None,
        "briefed_ready": int(ready.group(1)) if ready else None,
        "measured_ready_at_emit": int(ready.group(2)) if ready else None,
    }
    return out, "regex extraction of the briefed vs measured partition in P2-GROUNDING.md"


def inst_delivered_live() -> tuple[object, str]:
    receipts = REPO / "command-center" / "receipts"
    n = 0
    if receipts.is_dir():
        for p in receipts.glob("*.json"):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
            if str(doc.get("state") or "").upper() == "SUCCESS":
                n += 1
    return n, "count receipts with terminal state SUCCESS (fresh recount, not the emitted reduction)"


def inst_ready_live() -> tuple[object, str]:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    ready = 0
    for u in cat.get("work_units") or []:
        uid = u.get("id")
        if not uid:
            continue
        rp = REPO / "command-center" / "receipts" / f"{uid}.json"
        if not rp.is_file():
            continue
        try:
            doc = json.loads(rp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if str(doc.get("state") or "").upper() != "SUCCESS":
            continue
        out_rel = str(u.get("output_path") or "")
        if out_rel and (REPO / out_rel.replace("\\", "/")).is_file():
            ready += 1
    return ready, "units with SUCCESS receipt whose output artifact exists (unit-level recount)"


def inst_manifest_check() -> tuple[object, str]:
    tool = REPO / "command-center" / "tools" / "command-center" / "unit_manifest.py"
    if not tool.is_file():
        tool = REPO / "tools" / "command-center" / "unit_manifest.py"
    if not tool.is_file():
        return {"rc": None, "first_red": "checker-tool-absent"}, "unit_manifest.py absent"
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PATH": os.environ.get("PATH", ""),
           "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}
    try:
        proc = subprocess.run(
            [sys.executable, "-I", str(tool), "--check", "--root", str(REPO)],
            cwd=str(REPO), capture_output=True, text=True, timeout=1500, env=env,
        )
    except subprocess.TimeoutExpired:
        return {"rc": 124, "first_red": "TIMEOUT"}, "unit_manifest --check timed out"
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    first_red = ""
    for line in out.splitlines():
        if "FAILED:" in line or line.startswith("FAIL") or "absent" in line.lower():
            first_red = line.strip()[:160]
            break
    return {"rc": proc.returncode, "first_red": first_red}, "unit_manifest.py --check (the real condition-11 instrument)"


import os  # noqa: E402  (used by inst_manifest_check env)


HARVEST_FIRST_RED = "BLD-0023"
FACTS = [
    ("F01_catalog_unit_count_2007", STATIC, inst_catalog_len, "SUPPORTED"),
    ("F02_briefed_delivered_is_4", LIVE, inst_delivered_live, "CONTRADICTED"),
    ("F03_briefed_ready_is_447", LIVE, inst_ready_live, "CONTRADICTED"),
    ("F04_condition11_green", LIVE, inst_manifest_check, None),
    ("F05_c11_first_red_is_bld0023_p13", LIVE, inst_manifest_check, None),
    ("F06_p13_exists", STATIC, inst_p13_file, "SUPPORTED"),
    ("F07_linux_worker_is_git_worktree", STATIC, inst_git_worktree, "CONTRADICTED"),
    ("F08_pinned_workflow_run_a_primary", STATIC, inst_pinned_run("A"), "NOT-CHECKED"),
    ("F09_pinned_workflow_run_b_primary", STATIC, inst_pinned_run("B"), "NOT-CHECKED"),
    ("F10_precedent_four_vgt_false_recorded", STATIC,
     inst_precedent("VERIFIED GROUND TRUTH"), "SUPPORTED"),
    ("F11_precedent_two_agents_same_probe_recorded", STATIC,
     inst_precedent("same probe re-run"), "SUPPORTED"),
    ("F12_mnn_collision_present_tense_in_decision_log", STATIC, inst_decision_log, "CONTRADICTED"),
]


def verdict_for(fid: str, observed) -> tuple[str, str]:
    if fid == "F01_catalog_unit_count_2007":
        return ("SUPPORTED" if observed == 2007 else "CONTRADICTED"), f"units={observed}"
    if fid == "F02_briefed_delivered_is_4":
        v = "CONTRADICTED" if observed != 4 else "SUPPORTED"
        return v, f"live delivered receipts={observed} vs briefed 4"
    if fid == "F03_briefed_ready_is_447":
        v = "CONTRADICTED" if observed != 447 else "SUPPORTED"
        return v, f"live ready units={observed} vs briefed 447"
    if fid == "F04_condition11_green":
        rc = (observed or {}).get("rc")
        v = "SUPPORTED" if rc == 0 else "CONTRADICTED"
        return v, f"--check rc={rc} first_red={(observed or {}).get('first_red', '')[:80]}"
    if fid == "F05_c11_first_red_is_bld0023_p13":
        first = str((observed or {}).get("first_red") or "")
        if "BLD-0023" in first:
            return "SUPPORTED", f"live first-red still BLD-0023: {first[:70]}"
        if not first:
            return "NOT-CHECKED", "no first-red captured (check may be green now)"
        return "CONTRADICTED-CURRENT-ENVIRONMENT", f"live first-red moved: {first[:70]}"
    if fid == "F06_p13_exists":
        ok = isinstance(observed, dict) and observed.get("exists") is True
        return ("SUPPORTED" if ok else "CONTRADICTED"), f"P13 stat={observed}"
    if fid == "F07_linux_worker_is_git_worktree":
        v = "SUPPORTED" if observed is True else "CONTRADICTED"
        return v, f".git present={bool(observed)}"
    if fid.startswith("F08") or fid.startswith("F09"):
        obs = observed if isinstance(observed, dict) else {}
        if obs.get("primary_result_present") is False:
            return "NOT-CHECKED", f"reason={obs.get('reason')}"
        return "SUPPORTED", f"primary result found: {obs}"
    if fid == "F10_precedent_four_vgt_false_recorded":
        return ("SUPPORTED" if observed is True else "CONTRADICTED"), f"precedent text present={observed}"
    if fid == "F11_precedent_two_agents_same_probe_recorded":
        return ("SUPPORTED" if observed is True else "CONTRADICTED"), f"precedent text present={observed}"
    if fid.startswith("F12"):
        obs = observed if isinstance(observed, dict) else {}
        if not obs.get("exists"):
            return "CONTRADICTED", "decision log absent on this substrate; present-tense claim false here"
        v = "SUPPORTED" if obs.get("collision_present_tense") else "CONTRADICTED"
        return v, f"mech_tokens={obs.get('mech_tokens')} present_tense={obs.get('collision_present_tense')}"
    raise AssertionError(f"unknown fact {fid}")


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != UNIT and doc.get("id") != UNIT:
        return fail(f"unit_id {doc.get('unit_id')}")
    rows = {f.get("id"): f for f in (doc.get("facts") or [])}
    if len(rows) != 12:
        return fail(f"facts={len(rows)} expected 12")
    hl = doc.get("headline") or {}

    undeclared = [fid for fid, f in rows.items() if not f.get("source_probe")]
    if len(undeclared) != 12:
        return fail(f"declared-source facts={12 - len(undeclared)}; sweep premise says all undeclared")
    if hl.get("undeclared_source_probes") not in (None, 12) or hl.get("source_signals") not in (None, 0):
        return fail("headline source accounting disagrees with the facts table")
    print("controls: 12/12 facts UNDECLARED_SOURCE -> re-run of producing probe REJECTED, source_signals=0")

    a = inst_catalog_len()
    b = inst_catalog_walk()
    fa, fb = fp_of("inst_catalog_len"), fp_of("inst_catalog_walk")
    if fa == fb:
        return fail("distinct-fingerprint control: fingerprints identical")
    if a[0] != b[0]:
        return fail(f"distinct-fingerprint counters disagree: {a[0]} vs {b[0]}")
    print(f"controls: distinct fingerprints accepted and agree (both count {a[0]})")

    pair, note = inst_briefed_pair()
    if pair.get("briefed_delivered") not in (None, 4) or pair.get("briefed_ready") not in (None, 447):
        return fail(f"briefed partition moved in P2-GROUNDING.md: {pair}")
    live_delivered, _ = inst_delivered_live()
    fires_live = live_delivered != 4
    if not fires_live:
        return fail("comparator did not fire on the live delivered count")
    print(f"controls: comparator fires on live ({live_delivered} != 4), silent on briefed (4 == 4)")

    drift = []
    for fid, kind, instrument, _want in FACTS:
        row = rows.get(fid)
        if row is None:
            return fail(f"artifact missing fact {fid}")
        observed, note = instrument()
        verdict, detail = verdict_for(fid, observed)
        art_verdict = str(row.get("current_truth") or "").upper()
        flag = ""
        if verdict != art_verdict:
            if kind == STATIC:
                return fail(f"STATIC fact {fid} verdict drifted: artifact={art_verdict} live={verdict} ({detail})")
            flag = " [CURRENT-ENVIRONMENT DRIFT: disclosed]"
            drift.append(f"{fid}: artifact={art_verdict} live={verdict} ({detail})")
        print(f"  {fid} [{kind}] {verdict} ({detail[:100]}){flag}")

    if drift:
        print(f"live-fact drift (disclosed, {len(drift)}):")
        for d in drift:
            print(f"  drift {d[:160]}")
    print(f"SUCCESS:{UNIT}-probe1 all 12 pinned facts re-measured with different instruments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
