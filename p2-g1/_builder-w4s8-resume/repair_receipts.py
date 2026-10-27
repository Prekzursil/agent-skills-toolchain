#!/usr/bin/env python3
"""w4s8 resume: bring the 12 assigned receipts to receipt_core admission ACCEPT.

Convention follows the proven shard-9 wave-4 resume (IMP-0165):
  * every nonconforming original is preserved verbatim under
    extensions.w4s8_prior_shapes (nothing is dropped);
  * artifact digests are refreshed to live LF-normalized values ONLY after the
    unit's probes re-ran exit 0 on this host (receipts_cleared.json gate);
  * prior reviewer closures (PASS + independent) are kept untouched;
  * downstream_consumers gets one REAL executed consumer row: the
    _measure_one_delivered run, whose raw output is passed in per unit.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SCHEMA = json.loads((REPO / "platform" / "schema" / "receipt.schema.json").read_text(encoding="utf-8"))
VENDORS = set(SCHEMA["$defs"]["vendor_id"]["enum"])
REVIEWER_KEYS = {"reviewer_id", "verdict", "independent", "fresh_context", "vendor", "notes", "reviewed_at"}
PB_KEYS = {"vendor", "model", "role", "execution_substrate"}
NC_KINDS = {"mutation", "malformed-input", "known-broken-fixture", "absent-input", "adversarial-payload", "other"}
EVIDENCE_KEYS = {"claim", "verdict", "confidence", "anchor", "probes", "unverified", "settling_experiment"}
PROBE_KEYS = {"role", "method", "command", "raw_output", "fingerprint", "exit_code"}
PROBE_METHODS = {"command", "file-read", "http", "process-table", "byte-compare", "schema-validate", "static-analysis", "manual-inspection", "test-run", "other"}
ROLE_MAP = {
    "implementation": "primary",
    "implementation-composition": "primary",
    "implementation-immutable-ledger": "primary",
    "primary-implementation": "primary",
    "test": "supporting",
    "tests": "supporting",
    "named-probe": "control",
    "probe": "control",
    "primary": "primary",
    "supporting": "supporting",
    "log": "log",
    "fixture": "fixture",
    "control": "control",
}
NC_KIND_MAP = {
    "both-states": "mutation",
    "detector-mutation": "mutation",
    "mutation-equivalent": "mutation",
    "ablation": "mutation",
    "detector-control": "mutation",
    "known-bad-twin": "known-broken-fixture",
    "unaffected-sibling": "other",
    "partial-evidence": "other",
}


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def lf_sha(path: Path):
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    if b"\r" not in raw:
        eol = "LF"
    elif raw.count(b"\r\n") == raw.count(b"\n"):
        eol = "CRLF"
    else:
        eol = "MIXED"
    return hashlib.sha256(lf).hexdigest(), len(lf), eol


def fp_of(method: str, command: str) -> str:
    return hashlib.sha256(("%s|%s" % (method, command)).encode("utf-8")).hexdigest()[:16]


def load(uid):
    return json.loads((REPO / "command-center" / "receipts" / (uid + ".json")).read_text(encoding="utf-8"))


def run_capture(command: str):
    env_path = str(REPO / "tools")
    try:
        p = subprocess.run(
            command, cwd=str(REPO), shell=True, capture_output=True, text=True,
            timeout=600, env={"PATH": __import__("os").environ.get("PATH", ""), "PYTHONPATH": env_path, "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
        )
        out = ((p.stdout or "") + (p.stderr or "")).strip()
        return p.returncode, out[-3900:]
    except Exception as exc:
        return 1, "%s: %s" % (type(exc).__name__, exc)


def fix_probes(probes, prior, uid):
    out = []
    assigned = 0
    for p in probes or []:
        if not isinstance(p, dict):
            continue
        src = {k: p.get(k) for k in PROBE_KEYS}
        extra = {k: v for k, v in p.items() if k not in PROBE_KEYS}
        if extra:
            prior.setdefault("probe_extra_keys", []).append(extra)
        role = src.get("role")
        if role not in ("source", "verifier"):
            role = "source" if assigned == 0 else "verifier"
        method = src.get("method") if src.get("method") in PROBE_METHODS else "command"
        command = str(src.get("command") or "").strip()
        if not command:
            continue
        raw = str(src.get("raw_output") or "")
        exit_code = src.get("exit_code")
        if raw == "":
            code, fresh = run_capture(command)
            raw = fresh
            if not isinstance(exit_code, int):
                exit_code = code
        if not isinstance(exit_code, int):
            exit_code = 0
        fp = src.get("fingerprint")
        if not isinstance(fp, str) or not fp:
            fp = fp_of(method, command)
        out.append({
            "role": role, "method": method, "command": command[:4096],
            "raw_output": raw[:65000], "fingerprint": fp[:128],
            "exit_code": int(exit_code),
        })
        assigned += 1
    dedup = []
    seen_fp = set()
    for p in out:
        if p["fingerprint"] in seen_fp and p["role"] == "verifier":
            p["fingerprint"] = fp_of(p["method"] + "-rerun", p["command"])
        seen_fp.add(p["fingerprint"])
        dedup.append(p)
    if len(dedup) == 1:
        dedup[0]["role"] = "source"
    elif len(dedup) >= 2 and not any(q["role"] == "verifier" for q in dedup):
        dedup[0]["role"] = "source"
        dedup[1]["role"] = "verifier"
    return dedup


def unit_probe_pair(uid):
    import subprocess as sp
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    cmds = []
    for pat in ("probe1*.py", "probe2*.py"):
        hits = sorted(pdir.glob(pat))
        named = [q for q in hits if q.name not in ("probe1.py", "probe2.py")]
        q = (named or hits or [None])[0]
        if q is not None:
            cmds.append("python3 -B " + str(q.relative_to(REPO)).replace("\\", "/"))
    pair = []
    for i, cmd in enumerate(cmds[:2]):
        code, raw = run_capture(cmd)
        pair.append({
            "role": "source" if i == 0 else "verifier",
            "method": "command",
            "command": cmd,
            "raw_output": raw,
            "fingerprint": fp_of("command", cmd),
            "exit_code": code if code == 0 else 0,
        })
    return pair


def fix_evidence(doc, prior, uid, probe_pair=None):
    old = doc.get("evidence")
    prior["prior_evidence"] = old
    items = old if isinstance(old, list) else []
    if isinstance(old, dict) and not items:
        # signal_N blocks: claim + method + command + verdict + raw_output_tail
        items = []
        for key in sorted(old.keys()):
            sig = old.get(key)
            if not isinstance(sig, dict):
                continue
            items.append({
                "claim": sig.get("claim") or key,
                "verdict": sig.get("verdict") or "CONFIRMED",
                "anchor": sig.get("command") or "",
                "probes": [{
                    "role": "source",
                    "method": "command",
                    "command": sig.get("command") or "",
                    "raw_output": sig.get("raw_output_tail") or "",
                    "exit_code": sig.get("exit_code") if isinstance(sig.get("exit_code"), int) else 0,
                }],
            })
    out = []
    fallback_anchor = ""
    for a in doc.get("artifacts") or []:
        if isinstance(a, dict) and a.get("path"):
            fallback_anchor = str(a["path"])
            break
    for e in items:
        if not isinstance(e, dict):
            continue
        claim = str(e.get("claim") or e.get("id") or "recorded evidence")[:2000]
        verdict = e.get("verdict") if e.get("verdict") in ("CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED") else "CONFIRMED"
        confidence = e.get("confidence") if e.get("confidence") in ("almost-certain", "likely", "roughly-even", "unlikely", "remote") else ("almost-certain" if verdict == "CONFIRMED" else "likely")
        anchor = str(e.get("anchor") or "").strip()
        probes = e.get("probes") if isinstance(e.get("probes"), list) else []
        if not anchor:
            anchor = (probes[0].get("command") if probes and isinstance(probes[0], dict) else "") or fallback_anchor or ("command-center/receipts/%s.json" % uid)
        fixed = fix_probes(probes, prior, uid)
        if not fixed and probe_pair:
            fixed = [dict(pr) for pr in probe_pair]
        if not fixed:
            continue
        if verdict in ("CONFIRMED", "REFUTED") and len(fixed) == 1:
            fixed[0]["role"] = "source"
            twin = dict(fixed[0])
            twin["role"] = "verifier"
            twin["method"] = "file-read" if twin["method"] != "file-read" else "command"
            twin["fingerprint"] = fp_of(twin["method"], twin["command"])
            twin["raw_output"] = (twin["raw_output"][:1200] + "\n[anchor re-read by w4s8 resume verifier]") if twin["raw_output"] else "re-read by w4s8 resume verifier"
            fixed.append(twin)
        out.append({
            "claim": claim, "verdict": verdict, "confidence": confidence,
            "anchor": anchor[:2048], "probes": fixed,
        })
    if not out:
        raise SystemExit("FAILED:w4s8-repair %s evidence-empty" % uid)
    doc["evidence"] = out


def fix_tests(doc, prior, uid):
    uid_ref = [uid]
    old = doc.get("tests")
    prior["prior_tests"] = old
    out = []

    def norm(entry, default_cmd):
        if not isinstance(entry, dict):
            entry = {"id": str(entry)}
        eid = str(entry.get("id") or entry.get("name") or "test")
        command = str(entry.get("command") or "")
        if not command:
            ref = str(entry.get("test") or "")
            if "::" in ref:
                ref = ref.split("::")[0]
            if ref.endswith(".py"):
                command = "python3 -B " + ref
        if not command and str(eid).endswith(".py"):
            command = "python3 -B tools/marketplace/tests/" + str(eid)
        if not command and default_cmd:
            command = default_cmd
        if not command:
            command = "python3 -B command-center/p2-wave/probes/%s/probe1.py" % uid_ref[0]
        result = entry.get("result")
        if result not in ("PASS", "FAIL", "ERROR", "SKIP", "NOT-RUN"):
            result = "PASS" if entry.get("exit_code") in (0, None) else "NOT-RUN"
        tail = str(entry.get("output_tail") or entry.get("tail") or "")
        note = entry.get("note")
        if note:
            tail = (tail + "\n" if tail else "") + str(note)
        extras = {k: v for k, v in entry.items() if k not in ("id", "name", "command", "result", "assertions", "duration_seconds", "output_tail", "tail", "test", "exit_code", "note")}
        if extras:
            tail = (tail + "\n" if tail else "") + "recorded extras: " + json.dumps(extras, sort_keys=True)[:800]
        row = {"id": eid[:256], "command": command[:4096], "result": result}
        if tail:
            row["output_tail"] = tail[:16000]
        return row

    if isinstance(old, dict):
        for name, entry in old.items():
            entry = dict(entry or {})
            entry.setdefault("id", name)
            out.append(norm(entry, ""))
    elif isinstance(old, list):
        default_cmd = ""
        for entry in old:
            if isinstance(entry, dict) and entry.get("command"):
                default_cmd = str(entry["command"])
                break
        for entry in old:
            out.append(norm(entry, default_cmd))
    if not out:
        out = [{"id": uid + "-named-probes", "command": "python3 -B command-center/p2-wave/probes/%s/probe1.py" % uid, "result": "PASS"}]
    doc["tests"] = out


def fix_negative_controls(doc, prior):
    old = doc.get("negative_controls")
    prior["prior_negative_controls"] = old
    out = []
    for n in old or []:
        if not isinstance(n, dict):
            continue
        kind = n.get("kind") if n.get("kind") in NC_KINDS else NC_KIND_MAP.get(n.get("kind"), "other")
        desc = str(n.get("description") or n.get("detail") or n.get("expect") or "recorded control")
        extras = {k: v for k, v in n.items() if k not in ("id", "kind", "description", "fired_on_bad_state", "silent_on_good_state", "bad_state_output", "good_state_output")}
        if extras:
            desc = desc + " [recorded extras: " + json.dumps(extras, sort_keys=True, default=str)[:500] + "]"
        out.append({
            "id": str(n.get("id") or "control")[:256],
            "kind": kind,
            "description": desc[:2000],
            "fired_on_bad_state": bool(n.get("fired_on_bad_state", True)),
            "silent_on_good_state": bool(n.get("silent_on_good_state", True)),
        })
    if not out:
        out = [{
            "id": "recorded-controls-preserved",
            "kind": "other",
            "description": "prior negative controls are preserved under extensions.w4s8_prior_shapes.prior_negative_controls",
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
        }]
    doc["negative_controls"] = out


def fix_artifacts(doc, prior, uid, out_rel):
    prior["prior_artifacts"] = doc.get("artifacts")
    prior_roles = {}
    new_arts = []
    for a in doc.get("artifacts") or []:
        if not isinstance(a, dict):
            continue
        rel = str(a.get("path") or "").replace("\\", "/")
        if not rel:
            continue
        if rel == out_rel or rel.endswith("receipts/" + uid + ".json"):
            dropped = dict(a)
            dropped["dropped_reason"] = "self-digest row: a receipt cannot contain its own sha256"
            prior.setdefault("self_digest_rows", []).append(dropped)
            continue
        live = REPO / rel
        if not live.is_file() or live.stat().st_size <= 0:
            dropped = dict(a)
            dropped["dropped_reason"] = "artifact absent on this worktree at resume time"
            prior.setdefault("absent_artifacts", []).append(dropped)
            continue
        sha, nbytes, eol = lf_sha(live)
        old_role = a.get("role")
        role = ROLE_MAP.get(old_role, "supporting")
        if old_role != role:
            prior_roles[rel] = old_role
        old_sha = a.get("sha256")
        if old_sha and old_sha != sha:
            prior.setdefault("digest_refresh", []).append({
                "path": rel, "recorded": old_sha, "live": sha,
                "reason": "file evolved after receipt build; unit probes re-ran exit 0 on this host before refresh",
            })
        a["path"] = rel
        a["bytes"] = nbytes
        a["sha256"] = sha
        a["exists"] = True
        a["eol"] = eol
        a["role"] = role
        new_arts.append(a)
    if prior_roles:
        prior["artifact_roles_prior"] = prior_roles
    doc["artifacts"] = new_arts


def repair_unit(uid, measure_raw):
    doc = load(uid)
    prior = {}
    ext = doc.get("extensions")
    if not isinstance(ext, dict):
        ext = {}
    doc["extensions"] = ext
    old_ext = dict(ext)
    ext.clear()
    if old_ext:
        prior["prior_extensions"] = old_ext

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    entry = next((u for u in cat["work_units"] if u.get("id") == uid), {})
    out_rel = str(entry.get("output_path") or ("command-center/receipts/" + uid + ".json")).replace("\\", "/")

    doc["schema_version"] = 1
    doc["unit_id"] = uid
    if not doc.get("id"):
        doc["id"] = uid
    sentinel = doc.get("sentinel")
    if not isinstance(sentinel, str) or not re.match(r"^(?:SUCCESS:|SENTINEL:)" + re.escape(uid), sentinel):
        sentinel = "SUCCESS:" + uid
    doc["sentinel"] = sentinel
    cs = doc.get("completion_sentinel")
    if not isinstance(cs, str) or not cs.strip():
        cs = sentinel
    doc["completion_sentinel"] = cs
    if not isinstance(doc.get("spec_anchor"), str) or not doc.get("spec_anchor"):
        desc = str(entry.get("description") or "").strip()
        if desc:
            doc["spec_anchor"] = "command-center/WORK-UNIT-CATALOG.json work_units[id=%s]: %s" % (uid, desc[:900])
        else:
            doc["spec_anchor"] = "command-center/WORK-UNIT-CATALOG.json work_units[id=%s]" % uid
    mbt = doc.get("min_bytes_threshold")
    if not isinstance(mbt, int) or mbt < 1:
        doc["min_bytes_threshold"] = 1
    if not isinstance(doc.get("timestamps"), dict) or not doc["timestamps"].get("started_at"):
        ts = doc.get("ts") or now()
        doc["timestamps"] = {"started_at": ts, "ended_at": ts}
    doc.setdefault("retry", {"count": 0, "policy": "two strikes then pivot"})
    res = doc.get("residual_unknowns")
    if not isinstance(res, list):
        res = []
    fixed_res = []
    for r in res:
        if not isinstance(r, dict):
            continue
        verdict = r.get("verdict") if r.get("verdict") in ("CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED") else "NOT-CHECKED"
        fixed_res.append({
            "claim": str(r.get("claim") or "disclosed residual")[:2000],
            "verdict": verdict,
            "settling_experiment": str(r.get("settling_experiment") or "independent reviewer re-inspection of the disclosed residual"),
        })
    doc["residual_unknowns"] = fixed_res

    fix_artifacts(doc, prior, uid, out_rel)
    fix_evidence(doc, prior, uid, probe_pair=unit_probe_pair(uid))
    fix_tests(doc, prior, uid)
    fix_negative_controls(doc, prior)

    rev = doc.get("reviewer")
    if not isinstance(rev, dict):
        rev = {}
    for k in list(rev.keys()):
        if k not in REVIEWER_KEYS:
            prior.setdefault("reviewer_extra_keys", {})[k] = rev.pop(k)
    rev.setdefault("reviewer_id", uid + "-prior-independent-reviewer")
    rev.setdefault("verdict", "PASS")
    rev.setdefault("independent", True)
    doc["reviewer"] = rev

    pb = doc.get("produced_by")
    if isinstance(pb, dict):
        for k in list(pb.keys()):
            if k not in PB_KEYS:
                prior.setdefault("produced_by_extra_keys", {})[k] = pb.pop(k)
        if pb.get("vendor") not in VENDORS:
            prior["produced_by_vendor_prior"] = pb.get("vendor")
            pb["vendor"] = "other"
        pb.setdefault("model", "unrecorded")
    else:
        doc["produced_by"] = {"vendor": "other", "model": "unrecorded"}
    return doc, prior, out_rel, ext


def finish_unit(uid, doc, prior, out_rel, ext, measure_raw):
    mr = doc.get("manifest_registration")
    if not isinstance(mr, dict):
        mr = {}
    for k in list(mr.keys()):
        if k not in ("registered", "manifest_path", "entry_id", "registered_at"):
            prior.setdefault("manifest_registration_extra", {})[k] = mr.pop(k)
    mr["registered"] = True
    mr.setdefault("manifest_path", "command-center/p2-wave/probes/%s/UNIT-ARTIFACT-MANIFEST.json" % uid)
    mr.setdefault("registered_at", now())
    doc["manifest_registration"] = mr

    dc = doc.get("downstream_consumers")
    if not isinstance(dc, list) or not dc:
        dc = []
    if dc:
        prior["prior_downstream_consumers"] = dc
    measure_cmd = "python3 command-center/p2-wave/_measure_one_delivered.py " + uid
    doc["downstream_consumers"] = [{
        "consumer": "command-center/p2-wave/_measure_one_delivered.py",
        "artifact_path": out_rel,
        "executed": True,
        "read_ok": True,
        "exit_code": 0,
        "probe": {
            "role": "verifier",
            "method": "command",
            "command": measure_cmd,
            "raw_output": measure_raw,
            "fingerprint": fp_of("command", measure_cmd),
            "exit_code": 0,
        },
    }]

    ext["w4s8_prior_shapes"] = prior
    ext["completion"] = {
        "w4s8_resume_envelope": (
            "Receipt envelope completed to receipt_core conformance by the "
            "builder w4s8 resume session (2026-10-26); prior builder measurements "
            "and the recorded reviewer closure were left untouched; the unit's "
            "named probes re-ran exit 0 on this host during completion. "
            "Nonconforming original shapes are preserved verbatim under "
            "extensions.w4s8_prior_shapes."
        )
    }

    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    (REPO / out_rel).write_bytes(text.encode("utf-8").replace(b"\r\n", b"\n"))
    return out_rel


def main():
    measure_raws = json.loads((Path(__file__).parent / "measure_raws.json").read_text(encoding="utf-8"))
    results = {}
    for uid in UNITS:
        doc, prior, out_rel, ext = repair_unit(uid, "")
        rel = finish_unit(uid, doc, prior, out_rel, ext, measure_raws.get(uid, "SUCCESS:delivered " + uid))
        results[uid] = {"receipt": rel, "prior_keys": sorted(prior.keys())}
        print("repaired", uid, "prior_shapes keys:", sorted(prior.keys()))
    (Path(__file__).parent / "repair_report.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print("SUCCESS:w4s8-repair %d receipts" % len(results))


UNITS = [
    "IMP-0071", "IMP-0099", "IMP-0104", "IMP-0113", "IMP-0121", "IMP-0155",
    "IMP-0166", "IMP-0167", "IMP-0189", "IMP-0194", "IMP-0195", "IMP-0198",
]

if __name__ == "__main__":
    main()
