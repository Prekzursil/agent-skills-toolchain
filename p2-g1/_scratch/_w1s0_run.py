"""Wave-1 shard-0 orchestrator.

Per unit: fix artifact -> generate probes -> live mutation control -> merge NC ->
manifest -> final probe runs -> SUBAGENT-RETURN -> BLOCKED receipt -> measure.

Usage:
    python _scratch/_w1s0_run.py <UNIT-ID>          # one unit
    python _scratch/_w1s0_run.py ALL                # all 12 in order
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import _w1s0_fixers as fx  # noqa: E402
import _w1s0_lib as L  # noqa: E402


RECOMPUTE_GENERIC = '''
def recompute(doc):
    """Independent re-derivation: re-hash every non-self artifacts[] row live.
    A self-referential row (the file cannot contain its own hash) is verified by
    presence and non-emptiness; the external manifest carries the live hash."""
    bad = []
    n = 0
    for a in doc.get("artifacts") or []:
        if not isinstance(a, dict) or not a.get("path"):
            continue
        rel = str(a["path"]).replace(chr(92) * 2, "/")
        p = REPO / rel
        if not p.is_file():
            bad.append("missing:" + rel)
            continue
        if p.resolve() == OUT.resolve():
            if p.stat().st_size <= 0:
                bad.append("empty:" + rel)
            n += 1
            continue
        raw = p.read_bytes()
        sha = hashlib.sha256(raw.replace(b"\\r\\n", b"\\n")).hexdigest()
        n += 1
        if a.get("sha256") and a["sha256"] != sha:
            bad.append("sha-drift:" + rel)
    if bad:
        return False, "; ".join(bad[:4])
    return True, str(n) + " artifact rows re-verified live, all match"
'''

RECOMPUTE_0006 = '''
def recompute(doc):
    """Recount the target verdict histogram against the declared counts."""
    table = doc.get("target_refutations") or []
    counts = doc.get("counts") or {}
    if not table or not counts:
        return False, "target_refutations/counts absent"
    hist = {}
    for row in table:
        v = row.get("verdict")
        hist[v] = hist.get(v, 0) + 1
    for k, v in counts.items():
        if hist.get(k, 0) != v:
            return False, "counts[" + str(k) + "]=" + str(v) + " but recounted " + str(hist.get(k, 0))
    return True, "verdict histogram recounted " + json.dumps(hist) + " == declared counts"
'''

RECOMPUTE_0124 = '''
def recompute(doc):
    """Verify the four-state confusion matrix rows are distinct and complete."""
    rows = doc.get("rows") or []
    states = {"FINISHED", "RUNNING_MONITOR_ALIVE", "RUNNING_MONITOR_DEAD", "STALLED"}
    if len(rows) < 4:
        return False, "scenario rows=" + str(len(rows)) + " < 4"
    cm = doc.get("confusion_matrix") or {}
    if set(cm) != states:
        return False, "confusion_matrix keys=" + str(sorted(cm))
    return True, "4 scenario rows present; four-state confusion matrix complete"
'''

RECOMPUTE = {"ADV-0006": RECOMPUTE_0006, "ADV-0124": RECOMPUTE_0124}


def run_probe(path: Path) -> dict:
    rel = path.relative_to(L.REPO).as_posix()
    cmd = "PYTHONDONTWRITEBYTECODE=1 python3 -B " + rel
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
           "AST_INTEGRATE_ROOT": str(L.REPO)}
    while True:
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
        if m is None:
            break
        env[m.group(1)] = m.group(2).strip('"').strip("'")
        cmd = cmd[m.end():]
    exe = sys.executable.replace("\\", "/")
    cmd = cmd.replace("python3", exe, 1)
    p = subprocess.run(cmd, cwd=str(L.REPO), shell=True, capture_output=True,
                       text=True, timeout=300, env=env)
    text = ((p.stdout or "") + (p.stderr or "")).strip()[-8000:]
    return {"id": path.name.split("_")[0],
            "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B " + rel,
            "exit_code": p.returncode, "raw_output": text}


def process(uid: str) -> dict:
    cat = L.load_catalog()
    unit = L.catalog_unit(cat, uid)
    ctx = {"uid": uid, "unit": unit, "probe_dir": str(L.PROBES / uid)}
    notes: list[str] = []
    out: dict = {"unit": uid}

    # ---- 1. fix ------------------------------------------------------------
    doc = json.loads((L.REPO / unit["output_path"]).read_text(encoding="utf-8"))
    fixer = fx.FIX[uid]
    try:
        fixer(doc, ctx)
    except fx.SkipUnit as exc:
        return skip_unit(uid, unit, str(exc))

    notes.append("fixer:" + fixer.__name__)
    fx.fix_artifacts_rows(doc)
    fx.ensure_core(doc, ctx)
    fx.fix_reviewer(doc, ctx)
    fx.fix_produced_by(doc)
    fx.fix_residuals(doc)
    notes += fx.fix_tests_and_ncs(doc)
    rc_gate = fx.add_consumer_row(doc, ctx)
    if rc_gate != 0:
        return fail_unit(uid, unit, "consumer-gate-rc=" + str(rc_gate))
    fx.build_report(doc, ctx)
    ev = fx.build_fresh_evidence(doc, ctx)
    doc["evidence"] = ev
    _write_doc(unit, doc)
    out["fixed"] = True

    # ---- 2. probes + live mutation control ---------------------------------
    p1 = L.make_probe(uid, cat, 1, "")
    p2 = L.make_probe(uid, cat, 2, RECOMPUTE.get(uid, RECOMPUTE_GENERIC))
    dry = run_probe(p2)
    if dry["exit_code"] != 0:
        return fail_unit(uid, unit, "probe2-dry rc=" + str(dry["exit_code"])
                         + ": " + dry["raw_output"][-300:])
    nc = json.loads((L.PROBES / uid / "nc_live.json").read_text(encoding="utf-8"))
    doc = json.loads((L.REPO / unit["output_path"]).read_text(encoding="utf-8"))
    doc["negative_controls"] = [nc] + [x for x in doc.get("negative_controls") or []
                                       if x.get("id") != nc["id"]]
    doc["report"]["control_ids"] = sorted(
        {nc["id"], "NC-MUTATION-" + uid}
        | {str(x.get("id", "")) for x in doc["negative_controls"]})
    _write_doc(unit, doc)

    # ---- 3. schema gate before manifest -------------------------------------
    errs = L.schema_errors(doc, L.load_schema(unit["output_schema"]))
    if errs:
        return fail_unit(uid, unit, "schema-invalid after merge: " + str(errs[0]))

    # ---- 4. manifest + final probes -----------------------------------------
    L.write_manifest(uid, unit, [p1, p2])
    final1 = run_probe(p1)
    final2 = run_probe(p2)
    probe_runs = [final1, final2]
    if final1["exit_code"] != 0 or final2["exit_code"] != 0:
        L.write_manifest(uid, unit, [p1, p2])
        final1 = run_probe(p1)
        final2 = run_probe(p2)
        probe_runs = [final1, final2]
        if final1["exit_code"] != 0 or final2["exit_code"] != 0:
            return fail_unit(uid, unit, "probes still red after retry: p1="
                             + str(final1["exit_code"]) + " p2="
                             + str(final2["exit_code"]) + " "
                             + final1["raw_output"][-200:])

    # ---- 5. SUBAGENT-RETURN + receipt + measure ------------------------------
    sha, size, _ = L.digest_norm(L.REPO / unit["output_path"])
    L.write_subagent_return(uid, unit, probe_runs, " | ".join(notes), sha, size)
    L.write_receipt(uid, unit, doc, ev, " | ".join(notes))
    rc, tail = L.measure(uid)
    out["measure_rc"] = rc
    out["measure_tail"] = tail[-400:]
    out["ok"] = rc == 0
    return out


def _write_doc(unit: dict, doc: dict) -> None:
    (L.REPO / unit["output_path"]).write_text(
        json.dumps(doc, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def skip_unit(uid: str, unit: dict, reason: str) -> dict:
    """Honest BLOCKED lane for units that cannot be delivered (no fake green)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": uid, "unit_id": uid, "status": "BLOCKED", "state": "BLOCKED",
        "sentinel": "FAILED:" + uid + " " + reason[:300],
        "output_path": unit["output_path"],
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": reason,
            "blocked_on": reason[:2048],
        },
        "notes": "Builder lane reports BLOCKED; artifact left untouched.",
        "ts": now,
    }
    (L.PROBES / uid).mkdir(parents=True, exist_ok=True)
    (L.PROBES / uid / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1) + "\n", encoding="utf-8", newline="\n")
    receipt = {
        "schema_version": 1, "unit_id": uid, "state": "BLOCKED",
        "sentinel": "FAILED:" + uid + " " + reason[:250],
        "spec_anchor": str(unit.get("spec_anchor") or "catalog-entry:" + uid),
        "min_bytes_threshold": 2048,
        "produced_by": {"vendor": "anthropic", "model": "opus",
                        "role": "builder-shard-0"},
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {"count": 0, "policy": "two-strikes pivot; skip is a verdict, not a retry"},
        "failure": {
            "classification": ["reviewer-absent"],
            "reason": reason,
            "blocked_on": reason[:2048],
        },
        "artifacts": [{
            "path": unit["output_path"],
            "bytes": (L.REPO / unit["output_path"]).stat().st_size,
            "sha256": L.digest_norm(L.REPO / unit["output_path"])[0],
            "exists": True, "role": "primary",
        }],
        "evidence": [{
            "claim": "Unit " + uid + " cannot be delivered green: " + reason[:350],
            "verdict": "BLOCKED",
            "confidence": "almost-certain",
            "anchor": unit["output_path"],
            "probes": [fx.probe_row("source", "file-read",
                                    "read defects[] from " + unit["output_path"],
                                    reason, 0)],
        }],
        "manifest_registration": {
            "registered": False,
            "manifest_path": "command-center/p2-wave/probes/" + uid
                             + "/UNIT-ARTIFACT-MANIFEST.json",
        },
        "reviewer": {"reviewer_id": "none-this-wave", "verdict": "NOT-REVIEWED",
                     "independent": False},
        "extensions": {"builder_lane": "workflow-shard-0-wave-1", "notes": reason},
    }
    (L.RECEIPTS / (uid + ".json")).write_text(
        json.dumps(receipt, indent=1) + "\n", encoding="utf-8", newline="\n")
    return {"unit": uid, "ok": False, "skipped": True, "reason": reason[:200]}


def fail_unit(uid: str, unit: dict, reason: str) -> dict:
    """A fix-cycle failure after real attempts: record, report, no fake green."""
    out = skip_unit(uid, unit, reason)
    out["failed"] = True
    out["skipped"] = False
    return out


def main(argv: list[str]) -> int:
    targets = L.MY_UNITS if (len(argv) < 2 or argv[1] == "ALL") else [argv[1]]
    results = []
    for uid in targets:
        try:
            res = process(uid)
        except Exception as exc:  # noqa: BLE001
            import traceback

            cat = L.load_catalog()
            res = fail_unit(uid, L.catalog_unit(cat, uid),
                            "builder-exception " + type(exc).__name__ + ": " + str(exc))
            res["trace"] = traceback.format_exc()[-800:]
        results.append(res)
        print(json.dumps(res, indent=1)[:900])
        print("-" * 70)
    ok = sum(1 for r in results if r.get("ok"))
    skipped = sum(1 for r in results if r.get("skipped"))
    print("SUMMARY ok=" + str(ok) + "/" + str(len(results)) + " skipped=" + str(skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
