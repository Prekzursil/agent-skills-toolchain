#!/usr/bin/env python3
"""Shard0-w2 drive: per-unit probes -> manifest -> return -> measure -> receipt.

Resume-don't-restart: artifacts are NOT rebuilt (content is prior-wave work
verified against the live contract); this completes the missing builder-side
chain (predicate + independent recheck probes, per-unit manifest, SUBAGENT-
RETURN, receipts) and re-measures each unit with the official gate.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MEASURE = REPO / "command-center" / "p2-wave" / "_measure_one_delivered.py"
PROBES = REPO / "command-center" / "p2-wave" / "probes"
RECEIPTS = REPO / "command-center" / "receipts"
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
UNITS = {u.get("id"): u for u in CATALOG.get("work_units", []) if isinstance(u, dict)}

TRIO = {"ADV-0019", "ADV-0028", "ADV-0029"}
IDS = ["ADV-0005", "ADV-0010", "ADV-0014", "ADV-0015", "ADV-0018", "ADV-0019",
       "ADV-0022", "ADV-0023", "ADV-0024", "ADV-0028", "ADV-0029"]

BUILDER = "shard0 wave-2 builder (resume) 2026-10-25"
PRIOR = "prior builder attempt died mid-flight; artifacts verified against the live contract, not rebuilt"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def lf_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def run(cmd):
    import os
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if isinstance(cmd, str):
        # measure-style "VAR=value python3 -B ..." prefixes: shell handles them;
        # python3 resolves via the seed-stage wrapper PATH convention? No: on
        # Windows bare python3 may be absent, so route through measure's own
        # adaptation by invoking it per-command instead. Simplest honest route:
        # strip the env prefix and swap python3 for the live interpreter.
        import re as _re
        while True:
            m = _re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s+", cmd)
            if m is None:
                break
            env[m.group(1)] = m.group(2).strip('"').strip("'")
            cmd = cmd[m.end():]
        cmd = cmd.replace("python3", sys.executable.replace("\\", "/"), 1)
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO),
                           timeout=2700, shell=True, env=env)
    else:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO),
                           timeout=2700, env=env)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def rel_probe(uid: str, name: str) -> str:
    return f"command-center/p2-wave/probes/{uid}/{name}"


def cmd_str(uid: str, name: str) -> str:
    return f"PYTHONDONTWRITEBYTECODE=1 python3 -B {rel_probe(uid, name)}"


# ---------------------------------------------------------------- receipts

RECEIPT_NOTES = {
    "ADV-0005": "No prior receipt file existed. Builder-side delivery complete "
                "and verified live this session (artifact parses, sentinel present, "
                "predicate + independent recheck probes exit 0, manifest sha matches).",
    "ADV-0010": "Prior receipt carried state=SUCCESS with an independent reviewer "
                "closure (grok-p2-wave-ADV-0010-independent, PASS, independent=true) "
                "bound to bytes=184217/sha256=fe59b729ec23c8b2..., but the live artifact "
                "differs, so the closure does not bind the live artifact and SUCCESS is "
                "unavailable to it. Prior closure preserved verbatim under "
                "extensions.prior_closure; artifacts row refreshed to the live bytes/sha.",
    "ADV-0014": "Prior pointer receipt carried reviewer_verdict=PASS and "
                "reviewer_independent=true with no artifact byte/sha binding and no "
                "re-live-verifiable evidence, so the closure does not verify live. "
                "All prior fields preserved in place; state set to the honest builder "
                "terminal pending an independent reviewer.",
    "ADV-0015": "Prior receipt carried an independent closure (grok-p2-deliver-adv0015-linux, "
                "PASS, independent=true) bound to bytes=30765/sha256=c48d88ef157dd14e..., but "
                "the live artifact differs, so the closure does not bind the live artifact. "
                "Prior closure preserved verbatim under extensions.prior_closure; artifacts "
                "row refreshed to the live bytes/sha.",
    "ADV-0018": "No prior receipt file existed. Builder-side delivery complete and "
                "verified live this session.",
    "ADV-0019": "Prior pointer receipt carried state=SUCCESS with no reviewer closure "
                "(reviewer fields None); SUCCESS without a closure is forbidden by "
                "receipt_core, so the state is set to the honest builder terminal. "
                "All prior fields preserved in place.",
    "ADV-0022": "Prior pointer receipt carried reviewer_verdict=PASS and "
                "reviewer_independent=true (grok-p2-wave-adv0022-linux-raw-refuter) with "
                "disk_sha256=5c0c498ccc9259db..., but the live artifact sha differs, so the "
                "closure does not bind the live artifact. disk_sha256 refreshed to the live "
                "value; prior value preserved under extensions.prior_closure. All prior "
                "fields preserved in place.",
    "ADV-0023": "Receipt was already the honest BLOCKED pointer (open P0 defect "
                "ADV-0023-D1 is owner-rotation-gated; no token names recorded). Added the "
                "missing failure.classification reviewer-absent per program contract. "
                "Pointer shape preserved (no unit_id/artifacts added so global discovery "
                "does not double-count).",
    "ADV-0024": "Prior pointer receipt carried reviewer_verdict=NOT-REVIEWED and "
                "reviewer_independent=false; SUCCESS without a closure is forbidden by "
                "receipt_core. All prior fields preserved in place.",
    "ADV-0028": "No prior receipt file existed. Builder-side delivery complete and "
                "verified live this session.",
    "ADV-0029": "Prior pointer receipt carried state=SUCCESS with no reviewer closure; "
                "SUCCESS without a closure is forbidden by receipt_core. All prior fields "
                "preserved in place.",
}


def new_receipt(uid: str, out_rel: str, live_sha: str, live_bytes: int,
                probes_out: list[tuple[str, str]]) -> dict:
    return {
        "schema_version": 1,
        "unit_id": uid,
        "state": "BLOCKED",
        "sentinel": (f"SENTINEL:{uid}:BUILT-AWAITING-INDEPENDENT-REVIEW builder-side "
                     f"delivery verified live (artifact + probes exit 0 + manifest sha "
                     f"match); SUCCESS withheld: reviewer-absent"),
        "spec_anchor": str(UNITS[uid].get("spec_anchor") or UNITS[uid].get("spec_anchor") or UNITS[uid].get("spec_anchor") or ""),
        "min_bytes_threshold": 1024,
        "artifacts": [{"path": out_rel, "bytes": live_bytes, "sha256": live_sha,
                       "exists": True, "eol": "LF", "role": "primary"}],
        "evidence": [{"role": f"probe{i}", "method": "live-probe-rerun", "command": cmd,
                      "raw_output": out[-2000:], "fingerprint": hashlib.sha256((cmd + out).encode()).hexdigest()[:32]}
                     for i, (cmd, out) in enumerate(probes_out, 1)],
        "timestamps": {"started_at": now(), "ended_at": now(), "duration_seconds": 0},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "failure": {"classification": ["reviewer-absent"],
                    "reason": RECEIPT_NOTES[uid]},
        "reviewer": None,
        "manifest_registration": {"registered": True,
                                  "manifest_path": rel_probe(uid, "UNIT-ARTIFACT-MANIFEST.json"),
                                  "entry_id": uid, "registered_at": now()},
        "produced_by": {"vendor": "anthropic", "model": "claude-opus-5-5",
                        "role": "builder-shard0-w2", "execution_substrate": "local-windows-pwsh7"},
        "extensions": {"builder": BUILDER, "prior_builder": PRIOR},
    }


def write_receipt(uid: str, out_rel: str, live_sha: str, live_bytes: int,
                  probes_out: list[tuple[str, str]]) -> str:
    rp = RECEIPTS / f"{uid}.json"
    prior = {}
    if rp.is_file():
        prior = json.loads(rp.read_text(encoding="utf-8"))
    if uid in ("ADV-0010", "ADV-0015"):
        prior["state"] = "BLOCKED"
        prior_cls = prior.get("extensions") or {}
        pc = prior_cls
        pc["prior_closure"] = prior.get("reviewer")
        pc["prior_closure_note"] = (
            "Independent reviewer closure preserved verbatim; it does not bind the "
            "live artifact (bytes/sha differ), so state=SUCCESS was unavailable.")
        prior["extensions"] = pc
        prior["reviewer"] = None
        prior["failure"] = {"classification": ["reviewer-absent"],
                            "reason": RECEIPT_NOTES[uid]}
        for a in prior.get("artifacts") or []:
            if str(a.get("path") or "").replace("\\", "/") == out_rel:
                a["bytes"] = live_bytes
                a["sha256"] = live_sha
        rp.write_text(json.dumps(prior, indent=1, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
        return f"receipt rewritten (closure preserved, state=BLOCKED)"
    if uid == "ADV-0023":
        prior["failure"] = {"classification": ["reviewer-absent"],
                            "reason": RECEIPT_NOTES[uid]}
        rp.write_text(json.dumps(prior, indent=1, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
        return "receipt updated (failure.classification added; pointer shape kept)"
    if prior:  # pointer receipts 0014/0019/0022/0024/0029
        prior["state"] = "BLOCKED"
        prior["failure"] = {"classification": ["reviewer-absent"],
                            "reason": RECEIPT_NOTES[uid]}
        ext = prior.get("extensions") or {}
        if uid == "ADV-0022":
            ext["prior_closure"] = {"disk_sha256": prior.get("disk_sha256"),
                                    "reviewer_verdict": prior.get("reviewer_verdict"),
                                    "reviewer_independent": prior.get("reviewer_independent"),
                                    "reviewer_id": prior.get("reviewer_id")}
            prior["disk_sha256"] = live_sha
        elif uid == "ADV-0014":
            ext["prior_closure"] = {"reviewer_verdict": prior.get("reviewer_verdict"),
                                    "reviewer_independent": prior.get("reviewer_independent"),
                                    "review_probe": prior.get("review_probe")}
        prior["extensions"] = ext
        rp.write_text(json.dumps(prior, indent=1, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
        return "receipt rewritten (prior fields preserved, state=BLOCKED)"
    rec = new_receipt(uid, out_rel, live_sha, live_bytes, probes_out)
    rp.write_text(json.dumps(rec, indent=1, ensure_ascii=False) + "\n",
                  encoding="utf-8", newline="\n")
    return "receipt written (new, state=BLOCKED)"


# ---------------------------------------------------------------- per-unit

def write_manifest(uid: str, out_rel: str, live_sha: str, live_bytes: int,
                   p1: Path, p2: Path) -> None:
    man_p = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    rows = []
    prior_rows = []
    if man_p.is_file():
        try:
            old = json.loads(man_p.read_text(encoding="utf-8"))
            prior_rows = [a for a in (old.get("artifacts") or [])
                          if isinstance(a, dict)
                          and str(a.get("role")) not in ("primary", "supporting-predicate",
                                                          "supporting-recheck")]
        except Exception:
            prior_rows = []
    rows.append({"unit_id": uid, "path": out_rel, "bytes": live_bytes,
                 "sha256": live_sha, "exists": True, "eol": "LF",
                 "role": "primary", "present": True,
                 "receipt_path": rel_probe(uid, "SUBAGENT-RETURN.json")})
    for name, role in ((p1.name, "supporting-predicate"), (p2.name, "supporting-recheck")):
        p = PROBES / uid / name
        rows.append({"unit_id": uid, "path": rel_probe(uid, name),
                     "bytes": p.stat().st_size,
                     "sha256": hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
                     "exists": True, "eol": "LF", "role": role, "present": True,
                     "receipt_path": rel_probe(uid, "SUBAGENT-RETURN.json")})
    rows.extend(prior_rows)
    man_p.write_text(json.dumps({
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": uid,
        "verified_on_disk": True,
        "expected": len(rows), "present": len(rows),
        "artifacts": rows,
    }, indent=1) + "\n", encoding="utf-8", newline="\n")


def write_return(uid: str, out_rel: str, live_sha: str, live_bytes: int,
                 named: list[dict], note_extra: str = "") -> None:
    note = (f"{BUILDER}: builder-side chain completed on live contract "
            f"(predicate + independent recheck probes exit 0, manifest sha matches live). "
            f"{PRIOR}. {note_extra} Receipt BLOCKED/reviewer-absent; only the independent "
            f"reviewer closes.")
    ret = {
        "id": uid, "unit_id": uid,
        "status": "DELIVERED", "state": "BLOCKED",
        "sentinel": (f"FAILED:{uid} builder-side delivery COMPLETE (artifact + live "
                     f"probes + manifest sha verified); SUCCESS withheld: reviewer-absent"),
        "output_path": out_rel,
        "named_probes": named,
        "artifacts": [{"path": out_rel, "bytes": live_bytes, "sha256": live_sha,
                       "exists": True, "role": "primary"}],
        "manifest_path": rel_probe(uid, "UNIT-ARTIFACT-MANIFEST.json"),
        "failure": {"classification": ["reviewer-absent"],
                    "reason": ("Independent reviewer closure unavailable in builder "
                               "shard; artifact + named probes + manifest sha all "
                               "verify live this session.")},
        "notes": note,
        "extensions": {"builder": BUILDER, "prior_builder": PRIOR},
        "ts": now(),
    }
    (PROBES / uid / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")


def drive_unit(uid: str) -> tuple[str, str]:
    u = UNITS[uid]
    out_rel = str(u["output_path"]).replace("\\", "/")
    out = REPO / out_rel
    live_sha = lf_sha(out)
    live_bytes = out.stat().st_size
    p1 = PROBES / uid / "probe1_delivery_predicate.py"
    p2 = PROBES / uid / "probe2_independent_recheck.py"

    rc1, o1 = run([sys.executable, "-B", str(p1)])
    print(f"{uid} probe1 rc={rc1}")
    if rc1 != 0:
        return "FAIL", f"probe1: {o1[-300:]}"

    write_manifest(uid, out_rel, live_sha, live_bytes, p1, p2)

    rc2, o2 = run([sys.executable, "-B", str(p2)])
    print(f"{uid} probe2 rc={rc2}")
    if rc2 != 0:
        return "FAIL", f"probe2: {o2[-300:]}"

    named = [
        {"id": "probe1", "command": cmd_str(uid, "probe1_delivery_predicate.py"),
         "exit_code": rc1, "role": "delivery-predicate", "raw_output": o1[-6000:]},
        {"id": "probe2", "command": cmd_str(uid, "probe2_independent_recheck.py"),
         "exit_code": rc2, "role": "independent-recheck", "raw_output": o2[-6000:]},
    ]

    extra_note = ""
    if uid in TRIO:
        old_ret_p = PROBES / uid / "SUBAGENT-RETURN.json"
        old_cmds = []
        if old_ret_p.is_file():
            try:
                old = json.loads(old_ret_p.read_text(encoding="utf-8"))
                for p in old.get("named_probes") or []:
                    c = str(p.get("command") or "")
                    if c and "probe1_delivery_predicate" not in c and "probe2_independent_recheck" not in c:
                        old_cmds.append(c)
            except Exception:
                old_cmds = []
        for i, c in enumerate(old_cmds, 1):
            rc, o = run(c)  # measure-style env prefix handled by shell? no: run via shell
            print(f"{uid} content-probe rc={rc}")
            if rc != 0:
                return "FAIL", f"content-probe {i}: {o[-300:]}"
            named.append({"id": f"content{i}", "command": c, "exit_code": rc,
                          "role": "content-probe-preserved", "raw_output": o[-6000:]})
        extra_note = (f"Preserved prior content probes verbatim in named_probes "
                      f"({len(old_cmds)} re-run exit 0). ")

    write_return(uid, out_rel, live_sha, live_bytes, named, extra_note)

    mrc, mout = run([sys.executable, str(MEASURE), uid])
    tail = mout.strip().splitlines()[-1] if mout.strip() else ""
    print(f"{uid} measure rc={mrc} {tail}")
    if mrc != 0:
        return "FAIL", f"measure: {tail}"

    receipt_line = write_receipt(uid, out_rel, live_sha, live_bytes,
                                 [(n["command"], n["raw_output"]) for n in named[:2]])
    print(f"{uid} {receipt_line}")
    return "OK", f"measure SUCCESS; live_sha={live_sha[:16]} bytes={live_bytes}; {receipt_line}"


def main() -> int:
    bad = []
    for uid in IDS:
        try:
            status, detail = drive_unit(uid)
        except Exception as exc:
            status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
        print(f"== {uid}: {status} {detail}")
        if status != "OK":
            bad.append(uid)
    print("NOT-GREEN: " + ",".join(bad) if bad else "ALL-GREEN: " + ",".join(IDS))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
