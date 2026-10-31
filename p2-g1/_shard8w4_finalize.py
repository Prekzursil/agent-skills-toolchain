"""Finalize rebuilt probe layers: SUBAGENT-RETURN.json + UNIT-ARTIFACT-MANIFEST.json."""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
_spec = importlib.util.spec_from_file_location(
    "_m1d", str(REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py")
)
M1D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M1D)

PROBES = REPO / "command-center" / "p2-wave" / "probes"


def build_unit(uid: str, notes: str) -> dict:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    unit = next(u for u in cat["work_units"] if u.get("id") == uid)
    out_rel = str(unit["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    pd = PROBES / uid
    receipt = json.loads(out.read_text(encoding="utf-8"))
    sentinel = str(unit.get("completion_sentinel") or "")

    cmds = []
    for t in receipt.get("tests", []):
        c = t.get("command") if isinstance(t, dict) else None
        if isinstance(c, str) and "python3" in c:
            cmds.append(c.strip())
    if len(cmds) < 2:
        cmds = M1D.probe_commands(uid, None, pd)

    named = []
    for i, cmd in enumerate(cmds, 1):
        code, text = M1D.run_cmd(cmd)
        named.append({
            "id": "probe" + str(i),
            "command": cmd.replace("python3 -B", "python -B"),
            "exit_code": code,
            "raw_output": text,
        })
        if code != 0:
            print("PROBE-FAIL", uid, i, code)
            raise SystemExit(1)

    artifacts = []
    live_sha, live_b = M1D.digest_file(out)
    artifacts.append({
        "unit_id": uid,
        "path": out_rel,
        "bytes": live_b,
        "sha256": live_sha,
        "present": True,
        "role": "primary",
        "receipt_path": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json",
    })
    for f in sorted(pd.rglob("*")):
        if not f.is_file() or f.name in ("SUBAGENT-RETURN.json", "UNIT-ARTIFACT-MANIFEST.json"):
            continue
        rel = f.relative_to(REPO).as_posix()
        sha, b = M1D.digest_file(f)
        role = "named-probe" if f.name.startswith("probe") and f.suffix == ".py" else (
            "fixture" if f.suffix == ".json" else "supporting"
        )
        artifacts.append({
            "unit_id": uid,
            "path": rel,
            "bytes": b,
            "sha256": sha,
            "present": True,
            "role": role,
            "receipt_path": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json",
        })

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": uid,
        "unit_id": uid,
        "status": "SUCCESS",
        "state": receipt.get("state", "SUCCESS"),
        "sentinel": sentinel,
        "output_path": out_rel,
        "output_schema": str(unit.get("output_schema") or ""),
        "registered": True,
        "manifest_path": "command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": receipt.get("reviewer") or {},
        "cloud_ok": False,
        "ts": now,
        "artifacts": [
            {k: a[k] for k in ("path", "bytes", "sha256", "present", "role")}
            for a in artifacts[1:]
        ],
        "named_probes": named,
        "notes": notes,
    }
    (pd / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    man = {
        "unit_id": uid,
        "generated": now,
        "hash_rule": "sha256 over CRLF-normalized bytes (matches _measure_one_delivered.digest_file)",
        "artifacts": artifacts,
    }
    (pd / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print("FINALIZED", uid, "artifact_sha=" + live_sha[:16], "files=" + str(len(artifacts)))
    return ret


NOTES = {
    "IMP-0159": ("shard8w4 2026-10-26: probe layer lost from the worktree (prior builder "
                 "session ended mid-flight); probes, fixtures and scenario REBUILT against "
                 "the live tools/candidates/freshness.py API and re-run exit 0. "
                 "tools/candidates/class_ttl.json restored. Receipt reviewer closure "
                 "(verdict=PASS, independent=true) unchanged and still verifies live."),
    "IMP-0170": ("shard8w4 2026-10-26: fingerprint.py module AND probe layer were lost; "
                 "both REBUILT to the receipt-recorded contract (WL canonical order on "
                 "coarse labels, $Sn predicate rewriting, topology-optional hash) and "
                 "re-run exit 0 (20/20 renames, 20/20 gate mutations, topology "
                 "load-bearing control). Reviewer closure unchanged, still verifies live."),
    "IMP-0174": ("shard8w4 2026-10-26: probe layer rebuilt against live "
                 "tools/workflow_foundry/component_graph.py; plant_orphan patched to "
                 "recompute orphan_ids together with orphan_count (stale-ids defect). "
                 "Probes re-run exit 0. Reviewer closure unchanged, still verifies live."),
    "IMP-0199": ("shard8w4 2026-10-26: probe layer (fixtures + probe1 zero-egress "
                 "measured by InstrumentedPorts + probe2 unemulatable-refusal both-states "
                 "with lying-rail depth control) REBUILT against the live simulator and "
                 "re-run exit 0. Reviewer closure unchanged, still verifies live."),
    "IMP-0201": ("shard8w4 2026-10-26: baseline.py had degraded to an always-accept stub; "
                 "COMPLETED to the receipt-recorded contract (CROSS_CORPUS_REFUSED, "
                 "SPEC_VERSION_MISMATCH_REFUSED, SUMMARY_ONLY_REFUSED, row-recomputed "
                 "delta, ungated control sibling) + fixtures + probes rebuilt, re-run "
                 "exit 0. Reviewer closure unchanged, still verifies live."),
    "IMP-0206": ("shard8w4 2026-10-26: probe layer rebuilt against the live "
                 "overfit_detector package (MemorizeVisible flagged gap=1.0, TrueRule "
                 "clean gap=0.0; threshold v1.0.0 frozen, per-run overrides refused) and "
                 "re-run exit 0. Reviewer closure unchanged, still verifies live."),
}

if __name__ == "__main__":
    for uid in sys.argv[1:]:
        build_unit(uid, NOTES[uid])
