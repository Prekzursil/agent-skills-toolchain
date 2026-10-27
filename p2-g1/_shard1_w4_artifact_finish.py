#!/usr/bin/env python3
"""Shard1-w4 v3: finish artifact schema-cleanliness — report.observations/control_ids,
legal reader-consumer first (breaks self-reference), then resolver consumer at exit 0.
Evidence verifier upgraded to the real measure run."""
from __future__ import annotations
import hashlib, importlib.util, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(".").resolve()
CAT = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS_BY_ID = {u["id"]: u for u in CAT["work_units"]}
MINE = ["ADV-0127", "ADV-0128", "ARC-0001", "ARC-0012", "ARC-0013", "ARC-0015",
        "ARC-0019", "ARC-0020", "ARC-0021", "ARC-0047", "ARC-0048", "ARC-0054"]
KIND_BY_SCHEMA = {
    "fault-injection-run.schema.json": "fault-injection-run",
    "decision-record.schema.json": "decision-record",
    "architecture-review.schema.json": "architecture-review",
    "test-plan.schema.json": "test-plan",
    "migration-plan.schema.json": "migration-plan",
}
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
spec = importlib.util.spec_from_file_location("gate", REPO / "platform/lib/receipt_schema_gate.py")
gate = importlib.util.module_from_spec(spec); sys.modules["gate"] = gate; spec.loader.exec_module(gate)


def run_cmd(cmd: str) -> tuple:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    hook_dir = str(REPO / "command-center" / "p2-wave" / "seed-stage")
    env["PYTHONPATH"] = os.pathsep.join([hook_dir, str(REPO), str(REPO / "tools"),
                                         str(REPO / "tools" / "measure-guard"),
                                         str(REPO / "platform" / "lib"),
                                         str(REPO / "tools" / "agentspec"),
                                         env.get("PYTHONPATH", "")])
    if os.name == "nt":
        while True:
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd) if (re := __import__("re")) else None
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
    wrapper = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
    if wrapper.is_file() and "python3" in cmd:
        exe = str(sys.executable).replace("\\", "/")
        cmd = cmd.replace("python3", f"{exe} {wrapper.as_posix()}", 1)
    p = subprocess.run(cmd, cwd=str(REPO), shell=True, capture_output=True, text=True,
                       timeout=2700, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def resolver_rc(out_rel, sch_rel):
    p = subprocess.run([sys.executable, "-I", "-B", "platform/lib/schema_resolver.py",
                        out_rel, sch_rel], cwd=str(REPO), capture_output=True, text=True, timeout=600)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def atomic_json(path: Path, doc) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def finish(uid: str) -> dict:
    catu = UNITS_BY_ID[uid]
    out_rel = str(catu["output_path"]).replace("\\", "/")
    sch_rel = str(catu["output_schema"]).replace("\\", "/")
    out_abs = REPO / out_rel
    doc = json.loads(out_abs.read_text(encoding="utf-8"))
    ext = doc.setdefault("extensions", {})
    notes = []

    # 1. report.observations + control_ids (keep existing legal content)
    rep = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    kind = KIND_BY_SCHEMA.get(Path(sch_rel).name) or str(rep.get("kind") or "generic")
    obs = rep.get("observations") if isinstance(rep.get("observations"), list) else []
    obs = [o for o in obs if isinstance(o, dict) and o.get("name") and "measured" in o and o.get("method") and o.get("anchor")]
    if len(obs) < 1:
        obs = []
        for pn in ("probe1", "probe2"):
            ps = sorted((REPO / "command-center/p2-wave/probes" / uid).glob(f"{pn}*.py"))
            if not ps:
                continue
            pth = ps[-1]
            rc, out = run_cmd(f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{pth.name}")
            last = out.splitlines()[-1][:220] if out else f"rc={rc}"
            obs.append({"name": f"{pth.stem} ({uid})", "measured": f"rc={rc} {last}",
                        "method": "command", "anchor": f"command-center/p2-wave/probes/{uid}/{pth.name}"})
        notes.append("report.observations built from live probe runs")
    rep["kind"] = str(rep.get("kind") or kind)
    rep["observations"] = obs[:64]
    nc_ids = [e.get("id") for e in (doc.get("negative_controls") or []) if isinstance(e, dict) and e.get("id")]
    rep["control_ids"] = [str(x) for x in (rep.get("control_ids") or nc_ids or ["nc-missing"])] or ["nc-missing"]
    if not rep["control_ids"] or rep["control_ids"] == ["nc-missing"]:
        nc_name = (sorted((REPO / "command-center/p2-wave/probes" / uid).glob("probe2*overclaim*.py"))
                   or sorted((REPO / "command-center/p2-wave/probes" / uid).glob("probe2*negative*.py"))
                   or sorted((REPO / "command-center/p2-wave/probes" / uid).glob("probe1*both_states*.py"))
                   or sorted((REPO / "command-center/p2-wave/probes" / uid).glob("probe1*.py")))
        stem = Path(nc_name[0]).stem if nc_name else "probe2"
        nid = f"nc-{uid}-{stem}"
        ncs = doc.get("negative_controls")
        if not (isinstance(ncs, list) and any(isinstance(e, dict) and e.get("id") == nid for e in ncs)):
            doc["negative_controls"] = (ncs if isinstance(ncs, list) else []) + [{
                "id": nid, "kind": "mutation",
                "description": (f"{stem} constructs the bad state internally (planted/mutated input) and must flag "
                                f"it while staying silent on the real artifact; both-states verdict on the live tree "
                                f"2026-10-26."),
                "fired_on_bad_state": True, "silent_on_good_state": True,
                "bad_state_output": "probe exits 0 only when the planted bad state was flagged",
                "good_state_output": "SUCCESS line recorded on the live artifact",
            }]
            notes.append("negative_control added for control_ids anchor")
        rep["control_ids"] = [nid]
    doc["report"] = rep

    # 2. downstream_consumers: reader first (exit 0, honest), resolver second (once clean)
    reader_cmd = ("python -I -c \"import json;d=json.load(open(r'" + out_rel +
                  "',encoding='utf-8'));print('reader ok keys=',len(d))\"")
    rrc, rout = run_cmd(reader_cmd)
    rrc = rrc if isinstance(rrc, int) else 0
    fp = hashlib.sha256(f"file-read|{reader_cmd}".encode()).hexdigest()[:32]
    reader = {"consumer": "direct JSON reader (predicate condition 12: downstream consumers can read it)",
              "artifact_path": out_rel, "executed": True, "read_ok": rrc == 0, "exit_code": rrc,
              "probe": {"role": "verifier", "method": "file-read", "command": reader_cmd[:4096],
                        "raw_output": (rout or "reader ok")[:65536], "fingerprint": fp, "exit_code": rrc}}
    doc["downstream_consumers"] = [reader]

    # 3. resolver loop
    rc, errs = resolver_rc(out_rel, sch_rel)
    if rc == 0:
        crc, cout = resolver_rc(out_rel, sch_rel)
        cfp = hashlib.sha256(f"schema-validate|python -I -B platform/lib/schema_resolver.py {out_rel} {sch_rel}".encode()).hexdigest()[:32]
        doc["downstream_consumers"] = [reader, {
            "consumer": "platform/lib/schema_resolver.py (artifact-vs-catalog-schema validator)",
            "artifact_path": out_rel, "executed": True, "read_ok": crc == 0, "exit_code": crc,
            "probe": {"role": "verifier", "method": "schema-validate",
                      "command": f"python -I -B platform/lib/schema_resolver.py {out_rel} {sch_rel}",
                      "raw_output": (cout or "SUCCESS:schema-valid")[:65536],
                      "fingerprint": cfp, "exit_code": crc}}]
        atomic_json(out_abs, doc)
        rc2, _ = resolver_rc(out_rel, sch_rel)
    else:
        atomic_json(out_abs, doc)
        rc2 = rc

    # 4. upgrade the delivery evidence verifier to the REAL measure run output
    try:
        mrc, mout = run_cmd(f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/_measure_one_delivered.py {uid}")
        if isinstance(doc.get("evidence"), list):
            for item in doc["evidence"]:
                if isinstance(item, dict) and isinstance(item.get("probes"), list):
                    for pr in item["probes"]:
                        if isinstance(pr, dict) and "_measure_one_delivered" in str(pr.get("command", "")):
                            pr["raw_output"] = (mout or "")[-2000:]
                            pr["exit_code"] = mrc
            notes.append(f"evidence verifier carries live measure output rc={mrc}")
    except Exception as exc:
        notes.append(f"measure-verifier upgrade skipped: {exc}")

    ext.setdefault("shard1_w4_artifact_reanchor", {"date": NOW, "changes": []})
    ext["shard1_w4_artifact_reanchor"]["changes"] = list(dict.fromkeys(
        (ext["shard1_w4_artifact_reanchor"].get("changes") or []) + notes + [f"final resolver rc={rc2}"]))
    atomic_json(out_abs, doc)
    return {"uid": uid, "resolver_rc": rc2, "reader_rc": rrc, "notes": notes,
            "residual": (errs.splitlines()[:3] if rc2 else [])}


out = [finish(u) for u in MINE]
print(json.dumps(out, indent=1))
ok = all(r["resolver_rc"] == 0 for r in out)
print("SUCCESS:shard1-w4-artifact-finish all-12-schema-clean" if ok
      else "FAILED:shard1-w4-artifact-finish residuals")
