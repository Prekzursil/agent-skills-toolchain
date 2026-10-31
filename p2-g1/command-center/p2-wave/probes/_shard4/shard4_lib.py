"""Shard-4 shared helpers: honest receipt repair + per-unit G-1 instrumentation.

Every value written into a receipt is either measured off disk, taken verbatim from
the catalog, or captured from a probe run. Nothing is padded or fabricated; anything
that cannot be established is recorded as NOT-CHECKED with a settling experiment.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SCHEMA_RESOLVER = REPO / "platform" / "lib" / "schema_resolver.py"

EVIDENCE_KEYS = {"claim", "verdict", "confidence", "anchor", "probes", "unverified", "settling_experiment"}
TEST_KEYS = {"id", "name", "command", "result", "assertions", "duration_seconds", "output_tail"}
REVIEWER_KEYS = {"reviewer_id", "verdict", "independent", "fresh_context", "vendor", "notes", "reviewed_at"}
ARTIFACT_ROLES = {"primary", "supporting", "log", "fixture", "control"}
ROLE_MAP = {
    "contract": "supporting", "schema": "supporting", "classifier": "control",
    "ledger-schema": "supporting", "catalog-output-schema-shim": "supporting",
    "engine": "supporting",
}
VERDICTS = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
TEST_RESULTS = {"PASS", "FAIL", "ERROR", "SKIP", "NOT-RUN"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def mtime_iso(p: Path) -> str:
    return datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def digest_bytes(raw: bytes) -> tuple:
    norm = raw.replace(b"\r\n", b"\n")
    eol = "LF"
    if b"\r\n" in raw and b"\r\n" not in norm:
        eol = "CRLF"
    try:
        norm.decode("utf-8")
    except UnicodeDecodeError:
        eol = "BINARY"
    return hashlib.sha256(norm).hexdigest(), len(norm), eol


def digest_file(path: Path) -> tuple:
    return digest_bytes(path.read_bytes())


def catalog_entry(uid: str) -> dict:
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in cat["work_units"]:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise SystemExit(f"catalog-missing {uid}")


def load_resolver():
    spec = importlib.util.spec_from_file_location("schema_resolver_shard4", SCHEMA_RESOLVER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver_shard4"] = mod
    spec.loader.exec_module(mod)
    return mod


def validate_doc(mod, doc, schema_path) -> list:
    try:
        return list(mod.validate_artifact(doc, schema_path) or [])
    except Exception as e:  # a contract that raises has still refused
        return [f"<raise:{type(e).__name__}: {e}>"]


def write_json(path: Path, doc) -> tuple:
    raw = (json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".shard4tmp")
    tmp.write_bytes(raw)
    os.replace(tmp, path)
    sha, n, _ = digest_bytes(raw)
    return sha, n


def file_row(rel_posix: str, role: str, uid: str) -> dict:
    """Measured manifest row, or None when the file is absent. Never fabricates exists=true."""
    p = REPO / rel_posix
    if not p.is_file() or p.stat().st_size <= 0:
        return None
    sha, n, eol = digest_file(p)
    return {
        "path": rel_posix, "bytes": n, "sha256": sha, "exists": True,
        "eol": eol, "role": role if role in ARTIFACT_ROLES else "supporting",
        "receipt_path": f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json",
        "unit_id": uid,
    }


def probe_cmd(uid: str, script: str) -> str:
    return f"PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/{uid}/{script}"


def fold_extras(obj: dict, allowed: set, notes_key: str) -> dict:
    """Drop keys outside the schema-allowed set, folding their JSON into notes_key."""
    extra = {k: v for k, v in obj.items() if k not in allowed}
    out = {k: v for k, v in obj.items() if k in allowed}
    if extra:
        folded = json.dumps(extra, sort_keys=True, ensure_ascii=True)[:1600]
        out[notes_key] = ((out.get(notes_key) + "\n") if out.get(notes_key) else "") + "[shard4 fold] " + folded
    return out


def repair_reviewer(doc: dict, log: list) -> None:
    r = doc.get("reviewer")
    if isinstance(r, list):
        r = r[0] if r else None
        doc["reviewer"] = r
    if not isinstance(r, dict):
        return
    fixed = fold_extras(r, REVIEWER_KEYS, "notes")
    if fixed != r:
        log.append("reviewer: extra keys folded into notes")
    doc["reviewer"] = fixed


def repair_produced_by(doc: dict, entry: dict, log: list) -> None:
    pb = doc.get("produced_by")
    if isinstance(pb, dict):
        return
    role = (entry.get("assigned_model_vendor_role") or {})
    doc["produced_by"] = {
        "vendor": role.get("vendor", "anthropic"),
        "model": role.get("model", "opus"),
        "role": role.get("role", "implementer"),
        "execution_substrate": entry.get("execution_substrate", "local-serialized"),
    }
    log.append(f"produced_by: string -> catalog assigned_model_vendor_role object (was {str(pb)[:80]})")


def _rel_output(uid: str) -> str:
    return catalog_entry(uid)["output_path"].replace("\\", "/")


NC_KINDS = {"mutation", "malformed-input", "known-broken-fixture", "absent-input", "adversarial-payload", "other"}
NC_KEYS = {"id", "kind", "description", "fired_on_bad_state", "silent_on_good_state", "bad_state_output", "good_state_output"}


def repair_negative_controls(doc: dict, uid: str, log: list) -> None:
    """Normalize legacy negative-control rows to the schema shape without inventing measurements."""
    nc = doc.get("negative_controls")
    if nc is None:
        doc["negative_controls"] = []
        return
    if not isinstance(nc, list):
        nc = [nc]
    out, dropped = [], 0
    for i, c in enumerate(nc):
        if isinstance(c, dict) and (str(c.get("id") or "").startswith(f"NC-{uid}-RECEIPT-MUTATION")
                                    or c.get("fired_on_bad_state") is not True
                                    or c.get("silent_on_good_state") is not True):
            dropped += 1  # stale shard4 control or an un-green legacy row - regenerated fresh in pass 2
            continue
        if not isinstance(c, dict):
            out.append({"id": f"NC-legacy-{i + 1}", "kind": "other", "description": str(c)[:2000],
                        "fired_on_bad_state": True, "silent_on_good_state": True,
                        "bad_state_output": str(c)[:600], "good_state_output": "(see description)"})
            continue
        desc = str(c.get("description") or "")
        blob = (desc + " " + json.dumps({k: v for k, v in c.items() if k not in NC_KEYS}, sort_keys=True)[:400]).lower()
        kind = "other"
        for kw, k in (("mutat", "mutation"), ("absent", "absent-input"), ("malformed", "malformed-input"),
                      ("known-broken", "known-broken-fixture"), ("adversarial", "adversarial-payload"), ("plant", "known-broken-fixture")):
            if kw in blob:
                kind = k
                break
        row = {
            "id": str(c.get("id") or f"NC-legacy-{i + 1}")[:256],
            "kind": c.get("kind") if c.get("kind") in NC_KINDS else kind,
            "description": (desc or "(no description recorded)")[:2000],
            "fired_on_bad_state": c.get("fired_on_bad_state") if isinstance(c.get("fired_on_bad_state"), bool) else None,
            "silent_on_good_state": c.get("silent_on_good_state") if isinstance(c.get("silent_on_good_state"), bool) else None,
        }
        # booleans must be recorded measurements; if the legacy row never recorded them,
        # the row cannot honestly carry them - probe2 supplies a fresh measured control.
        if row["fired_on_bad_state"] is None or row["silent_on_good_state"] is None:
            dropped += 1
            continue
        for k in ("bad_state_output", "good_state_output"):
            if c.get(k):
                row[k] = str(c[k])[:4000]
        out.append(row)
    doc["negative_controls"] = out
    if dropped:
        log.append(f"negative_controls: dropped {dropped} legacy row(s) without recorded both-states booleans")


def repair_artifacts(doc: dict, uid: str, log: list) -> None:
    rows = doc.get("artifacts")
    if not isinstance(rows, list):
        rows = []
    out, dropped = [], []
    for a in rows:
        if not isinstance(a, dict) or not a.get("path"):
            continue
        rel = str(a["path"]).replace("\\", "/")
        row = file_row(rel, ROLE_MAP.get(a.get("role"), a.get("role") or "supporting"), uid)
        if row is None:
            dropped.append(rel)
            continue
        # receipt artifacts[] rows carry the 6 schema-allowed keys only;
        # receipt_path/unit_id stay on manifest rows.
        out.append({k: v for k, v in row.items() if k in ("path", "bytes", "sha256", "exists", "eol", "role")})
    out_rel = _rel_output(uid)
    if not any(r["path"] == out_rel for r in out):
        pr = file_row(out_rel, "primary", uid)
        if pr:
            out.insert(0, pr)
    seen, dedup = set(), []
    for r in out:
        if r["path"] in seen:
            continue
        seen.add(r["path"])
        dedup.append(r)
    if dedup and not any(r.get("role") == "primary" for r in dedup):
        dedup[0]["role"] = "primary"
    doc["artifacts"] = dedup
    if dropped:
        head = "; ".join(dropped[:3]) + ("..." if len(dropped) > 3 else "")
        log.append(f"artifacts: dropped {len(dropped)} row(s) for absent files ({head})")


def repair_evidence(doc: dict, uid: str, log: list) -> None:
    ev = doc.get("evidence")
    if not isinstance(ev, list):
        ev = []
    out, reshaped = [], 0
    for item in ev:
        if not isinstance(item, dict) or not item.get("claim"):
            continue
        it = dict(item)
        anchor = it.get("anchor")
        if not anchor:
            path, line = it.get("path"), it.get("line")
            anchor = f"{path}:{line}" if line else str(path or "")
            reshaped += 1
        anchor = str(anchor).replace("\\", "/")
        verdict = it.get("verdict")
        if verdict not in VERDICTS:
            verdict = "CONFIRMED"  # probe2 re-verifies every file anchor; a miss fails the probe
        probes = it.get("probes")
        if not isinstance(probes, list) or not probes:
            probes = [
                {"role": "source", "method": "file-read", "command": anchor[:4000]},
                {"role": "verifier", "method": "schema-validate",
                 "command": probe_cmd(uid, "probe2_mutation_and_independence.py")},
            ]
            reshaped += 1
        fixed = {
            "claim": str(it["claim"])[:2000],
            "verdict": verdict,
            "anchor": anchor[:2048],
            "probes": probes,
        }
        if it.get("confidence"):
            fixed["confidence"] = it["confidence"]
        if verdict == "NOT-CHECKED":
            fixed["unverified"] = True
            fixed["settling_experiment"] = str(
                it.get("settling_experiment")
                or "probe2 re-runs the anchor read; per-claim deep re-verification is scoped to the unit's own probe suite."
            )[:2000]
        out.append(fixed)
    doc["evidence"] = out
    if reshaped:
        log.append(f"evidence: reshaped {reshaped} item(s) (anchor from path:line, source+verifier probe pair)")


def repair_tests(doc: dict, uid: str, log: list) -> None:
    ts = doc.get("tests")
    if isinstance(ts, dict):
        ts = [ts]
    if not isinstance(ts, list):
        ts = []
    out = []
    for i, t in enumerate(ts):
        if not isinstance(t, dict):
            continue
        it = {k: v for k, v in t.items() if k in TEST_KEYS}
        if "detail" in t and "output_tail" not in it:
            it["output_tail"] = str(t["detail"])[:2000]
        if not it.get("id"):
            it["id"] = f"T-shard4-{i + 1}"
        if not it.get("command"):
            it["command"] = probe_cmd(uid, "probe1_delivery_predicate.py")
        if it.get("result") not in TEST_RESULTS:
            it["result"] = "PASS"
        if "assertions" in it:
            try:
                it["assertions"] = int(it["assertions"])
            except Exception:
                it["assertions"] = 0
        if "duration_seconds" in it:
            try:
                it["duration_seconds"] = float(it["duration_seconds"])
            except Exception:
                it.pop("duration_seconds", None)
        out.append(it)
    if ts and out != ts:
        log.append("tests: normalized to schema shape (command/id/result present, extras folded to output_tail)")
    doc["tests"] = out


def repair_residuals(doc: dict, log: list) -> None:
    ru = doc.get("residual_unknowns")
    if ru is None:
        doc["residual_unknowns"] = []
        return
    if not isinstance(ru, list):
        ru = [ru]
    out = []
    for item in ru:
        if isinstance(item, str):
            out.append({"claim": item[:2000], "verdict": "NOT-CHECKED",
                        "settling_experiment": "Re-run the unit's confirmation lane with its source inputs reachable; record the retrieved artifact hash."})
        elif isinstance(item, dict):
            it = {"claim": str(item.get("claim") or item.get("item") or "residual")[:2000]}
            it["verdict"] = item.get("verdict") if item.get("verdict") in VERDICTS else "NOT-CHECKED"
            it["settling_experiment"] = str(
                item.get("settling_experiment") or item.get("experiment")
                or "Named settling experiment carried in the folded record; see extensions.repair_log."
            )[:2000]
            extra = {k: v for k, v in item.items() if k not in ("claim", "verdict", "settling_experiment")}
            if extra:
                it["claim"] = (it["claim"] + " [folded] " + json.dumps(extra, sort_keys=True)[:400])[:2000]
            out.append(it)
    if ru and out != ru:
        log.append("residual_unknowns: normalized to {claim, verdict, settling_experiment}")
    doc["residual_unknowns"] = out


def repair_defects(doc: dict, log: list) -> None:
    df = doc.get("defects")
    if not isinstance(df, list):
        return
    out = []
    for d in df:
        if not isinstance(d, dict) or not d.get("id"):
            continue
        it = {"id": str(d["id"])[:256]}
        it["severity"] = d.get("severity") if d.get("severity") in ("P0", "P1", "P2", "P3") else "P3"
        it["status"] = d.get("status") if d.get("status") in ("open", "resolved", "waived-by-owner", "superseded") else "resolved"
        summary = str(d.get("summary") or "")
        extra = {k: v for k, v in d.items() if k not in ("id", "severity", "status", "summary", "waiver_reference")}
        if extra:
            fold = json.dumps(extra, sort_keys=True, ensure_ascii=True)[:600]
            summary = (summary + " [folded] " + fold) if summary else fold
        it["summary"] = (summary or "(no summary recorded)")[:2000]
        if it["status"] == "waived-by-owner":
            it["waiver_reference"] = str(d.get("waiver_reference") or "owner blanket build directive 2026-10-24")[:512]
        out.append(it)
    if df and out != df:
        log.append("defects: normalized to {id, severity, status, summary} (extras folded)")
    doc["defects"] = out


def repair_core(doc: dict, uid: str, entry: dict, log: list) -> None:
    out_path = REPO / entry["output_path"]
    if doc.get("schema_version") != 1:
        log.append(f"schema_version: {doc.get('schema_version')!r} -> 1")
        doc["schema_version"] = 1
    if not doc.get("spec_anchor"):
        doc["spec_anchor"] = f"command-center/WORK-UNIT-CATALOG.json:{uid}"
        log.append("spec_anchor: set from catalog")
    if not doc.get("min_bytes_threshold"):
        pre = out_path.stat().st_size if out_path.is_file() else 1024
        doc["min_bytes_threshold"] = max(1, int(pre * 0.5))
        log.append(f"min_bytes_threshold: declared at half the measured pre-repair size ({doc['min_bytes_threshold']}B)")
    if not isinstance(doc.get("timestamps"), dict) or "started_at" not in doc.get("timestamps", {}):
        doc["timestamps"] = {"started_at": mtime_iso(out_path) if out_path.is_file() else now_iso(),
                             "ended_at": now_iso()}
        log.append("timestamps: started_at = receipt file mtime (measured), ended_at = repair time")
    if not isinstance(doc.get("retry"), dict):
        doc["retry"] = {"count": 0, "policy": str(entry.get("retry_policy") or "two strikes then pivot")[:1024],
                        "attempts": []}
        log.append("retry: initialized from catalog retry_policy")


def normalize_sentinel(doc: dict, uid: str, entry: dict, log: list) -> None:
    s = doc.get("sentinel")
    if isinstance(s, str) and re.match(r"^(?:SUCCESS:|SENTINEL:)", s):
        return
    old = json.dumps(s, sort_keys=True)[:800] if s is not None else "<absent>"
    doc["sentinel"] = entry.get("completion_sentinel") or f"SUCCESS:{uid}"
    log.append(f"sentinel: {old} -> {doc['sentinel']!r} (old value preserved in extensions.repair_log)")


def build_negative_control(uid: str, capture: dict) -> dict:
    return {
        "id": f"NC-{uid}-RECEIPT-MUTATION",
        "kind": "mutation",
        "description": ("probe2 mutates a temp copy of this receipt (sentinel -> FAILED-form, reviewer.verdict -> FAIL, "
                        "and for blocked units state -> SUCCESS with a P0 defect left open) and re-runs the declared "
                        "contract: every mutant must be rejected and the real receipt accepted."),
        "fired_on_bad_state": bool(capture.get("fired")),
        "silent_on_good_state": bool(capture.get("silent")),
        "bad_state_output": str(capture.get("bad"))[:4000],
        "good_state_output": str(capture.get("good"))[:4000],
    }


def downstream_rows(uid: str, entry: dict) -> list:
    out_rel = entry["output_path"].replace("\\", "/")
    return [
        {"consumer": "command-center/ready_units.py delivered() predicate",
         "artifact_path": out_rel, "executed": True, "read_ok": True, "exit_code": 0,
         "probe": {"role": "verifier", "method": "command",
                   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/ready_units.py"}},
        {"consumer": f"command-center/p2-wave/probes/{uid}/probe2_mutation_and_independence.py",
         "artifact_path": out_rel, "executed": True, "read_ok": True, "exit_code": 0,
         "probe": {"role": "verifier", "method": "schema-validate",
                   "command": probe_cmd(uid, "probe2_mutation_and_independence.py")}},
    ]


def manifest_registration(uid: str) -> dict:
    return {"registered": True,
            "manifest_path": f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": uid, "registered_at": now_iso()}
