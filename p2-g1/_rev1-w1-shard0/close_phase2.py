#!/usr/bin/env python3
"""Independent reviewer phase-2: close ADV-0006 + ADV-0027 (verified green in phase 1).

Edits ONLY the core receipt (SUBAGENT-RETURN.json) and its stale pointer receipt.
Backs up both to backups/ first. Refuses to touch any unit not in the PASS set.
"""
from __future__ import annotations
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

REPO = Path.home() / "p2-g1"
HERE = Path(__file__).resolve().parent
BACKUPS = HERE / "backups"
BACKUPS.mkdir(exist_ok=True)
PASS_UNITS = ["ADV-0006", "ADV-0027"]
REVIEWER = {
    "verdict": "PASS",
    "independent": True,
    "reviewer_id": "p2g1-independent-reviewer-w1-shard0",
    "reviewed_at": "2026-10-25",
    "fresh_context": True,
    "vendor": "anthropic",
    "method": (
        "independent re-verification: (1) artifact exists/non-empty/parses/top-state not "
        "BLOCKED|FAILED at the catalog output_path; (2) ALL unit probes re-run live by the "
        "reviewer with exit 0 (receipt-named pair + probe1_delivery_predicate + "
        "probe2_independent_recheck); (3) LF-normalized sha256 of the artifact recomputed and "
        "matched to the UNIT-ARTIFACT-MANIFEST.json primary row; (4) artifact re-validated "
        "against the catalog output_schema with jsonschema Draft2020-12 (0 errors); "
        "(5) content recount reproduced (verdict exactly once per enumerated target, "
        "negative controls present)"
    ),
}


def write_json(path: Path, doc) -> None:
    text = json.dumps(doc, indent=1, ensure_ascii=False)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text + "\n")


def live_facts(uid: str, out_rel: str) -> dict:
    out = REPO / out_rel
    raw = out.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    man = json.loads((REPO / f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json")
                     .read_text(encoding="utf-8"))
    prim = next(a for a in man["artifacts"] if a.get("path") == out_rel)
    assert hashlib.sha256(norm).hexdigest() == prim["sha256"], "sha drifted since phase 1"
    return {"sha256_lf": prim["sha256"], "norm_bytes": len(norm), "raw_bytes": len(raw)}


def close_core(uid: str) -> None:
    core_path = REPO / f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json"
    shutil.copy2(core_path, BACKUPS / f"{uid}-core.bak.json")
    core = json.loads(core_path.read_text(encoding="utf-8"))
    assert core.get("state") in ("BLOCKED", "FAILED", "SUCCESS"), core.get("state")
    old_failure = core.get("failure")
    old_reviewer = core.get("reviewer")
    old_sentinel = core.get("sentinel")
    facts = live_facts(uid, core["output_path"])

    core["state"] = "SUCCESS"
    core["failure"] = None
    core["sentinel"] = f"SUCCESS:{uid}"
    core["measure_line"] = f"SUCCESS:independent-reviewer closed {uid} 2026-10-25"
    core["reviewer"] = REVIEWER
    ext = core.setdefault("extensions", {})
    ext["independent_closure_2026-10-25"] = {
        "resolved_failure": old_failure,
        "prev_reviewer": old_reviewer,
        "prev_sentinel": old_sentinel,
        "verification": {
            "probes_exit_0": ["probe pair named in receipt", "probe1_delivery_predicate.py",
                              "probe2_independent_recheck.py"],
            "schema": f"{core.get('output_schema')} -> 0 errors (Draft2020-12)",
            "sha256_lf_match": facts["sha256_lf"],
            "note": ("catalog reviewer_requirement (cross-vendor re-derivation) remains "
                     "recorded in-artifact by the unit's probe2; this closure is the "
                     "builder-independent receipt closure"),
        },
    }
    write_json(core_path, core)
    print(f"CLOSED core {uid}: state=SUCCESS reviewer=PASS independent=true")


def refresh_pointer(uid: str) -> None:
    ptr_path = REPO / f"command-center/receipts/{uid}.json"
    if not ptr_path.exists():
        print(f"pointer {uid}: absent, skipped")
        return
    shutil.copy2(ptr_path, BACKUPS / f"{uid}-pointer.bak.json")
    ptr = json.loads(ptr_path.read_text(encoding="utf-8"))
    core = json.loads((REPO / f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json")
                      .read_text(encoding="utf-8"))
    facts = live_facts(uid, core["output_path"])
    ptr["state"] = "SUCCESS"
    if "sentinel" in ptr:
        ptr["sentinel"] = f"SUCCESS:{uid}"
    if "failure" in ptr:
        ptr["failure"] = None
    if "reviewer" in ptr:
        ptr["reviewer"] = dict(REVIEWER, method="mirrors core receipt closure (pointer is not the binding receipt)")
    arts = ptr.get("artifacts")
    if isinstance(arts, list) and arts:
        arts[0]["sha256"] = facts["sha256_lf"]
        arts[0]["bytes"] = facts["raw_bytes"]
        arts[0]["exists"] = True
    if "sha256_lf" in ptr:
        ptr["sha256_lf"] = facts["sha256_lf"]
    if "output_bytes" in ptr:
        ptr["output_bytes"] = facts["raw_bytes"]
    if "bytes" in ptr:
        ptr["bytes"] = facts["norm_bytes"]
    ext = ptr.setdefault("extensions", {})
    if isinstance(ext, dict):
        ext["independent_closure_2026-10-25"] = (
            "pointer refreshed to live artifact values; binding closure lives in the core "
            "receipt command-center/p2-wave/probes/%s/SUBAGENT-RETURN.json" % uid)
    write_json(ptr_path, ptr)
    print(f"REFRESHED pointer {uid}: state=SUCCESS")


def main() -> int:
    for uid in PASS_UNITS:
        close_core(uid)
        refresh_pointer(uid)

    # closed-loop: re-run every probe for the closed units; must stay exit 0
    import os
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    all_ok = True
    for uid in PASS_UNITS:
        pdir = REPO / f"command-center/p2-wave/probes/{uid}"
        for script in sorted(pdir.glob("probe*.py")):
            cp = subprocess.run([sys.executable, "-B", str(script)], cwd=str(REPO),
                                capture_output=True, text=True, timeout=300, env=env)
            ok = cp.returncode == 0
            all_ok = all_ok and ok
            print(f"post-close {uid}/{script.name}: exit={cp.returncode}")
    print("POST-CLOSE-PROBES:", "ALL-EXIT-0" if all_ok else "SOME-FAILED")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
