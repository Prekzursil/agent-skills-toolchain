#!/usr/bin/env python3
"""Diagnose envelope-rest G-1 IDs on the Windows worktree (no measure)."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
WAVE = REPO / "command-center" / "p2-wave"
SHARDS = WAVE / "ovh-monitor" / "g1-shards"
CATALOG = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
BY_ID = {u["id"]: u for u in CATALOG.get("work_units") or [] if isinstance(u, dict) and "id" in u}
JSONL = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_ids() -> list[tuple[str, str]]:
    rows = []
    for name in ("class-other.txt", "class-sha.txt", "class-sentinel.txt", "class-output.txt"):
        p = SHARDS / name
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            uid = ln.strip()
            if uid:
                rows.append((name.replace(".txt", ""), uid))
    return rows


def jsonl_index() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not JSONL.is_file():
        return out
    with JSONL.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            uid = rec.get("id")
            if uid:
                out[uid] = rec
    return out


def diagnose(uid: str) -> dict:
    u = BY_ID.get(uid)
    rec: dict = {"id": uid}
    if u is None:
        rec["reason"] = "catalog-missing"
        return rec
    rel = str(u.get("output_path") or "").replace("\\", "/")
    sent = str(u.get("completion_sentinel") or "")
    rec["output_path"] = rel
    rec["sentinel_len"] = len(sent)
    rec["sentinel_head"] = sent[:80]
    probe_dir = WAVE / "probes" / uid
    rec["probe_dir"] = probe_dir.is_dir()
    rec["has_return"] = (probe_dir / "SUBAGENT-RETURN.json").is_file()
    rec["has_manifest"] = (probe_dir / "UNIT-ARTIFACT-MANIFEST.json").is_file()
    rec["has_probe1"] = bool(list(probe_dir.glob("probe1*.py"))) if probe_dir.is_dir() else False
    rec["has_probe2"] = bool(list(probe_dir.glob("probe2*.py"))) if probe_dir.is_dir() else False
    rec["has_emit"] = any(
        (probe_dir / n).is_file()
        for n in ("emit.py", "emit_artifact.py", "write_receipts.py", "build.py")
    )
    if not rel:
        rec["reason"] = "predicate:absent-no-output_path"
        return rec
    out = REPO / rel
    rec["out_exists"] = out.is_file()
    rec["out_bytes"] = out.stat().st_size if out.is_file() else 0
    if not out.is_file() or out.stat().st_size <= 0:
        rec["reason"] = "predicate:absent-output"
        return rec
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        rec["reason"] = f"unparseable:{type(exc).__name__}"
        rec["sentinel_in_file"] = bool(sent) and sent in out.read_text(encoding="utf-8", errors="replace")
        return rec
    rec["json_type"] = type(doc).__name__
    if isinstance(doc, dict):
        rec["state"] = str(doc.get("state") or "")
        rec["self_declared"] = str(doc.get("state") or "").upper() in NOT_DELIVERING
        rec["doc_keys"] = sorted(list(doc.keys()))[:20]
    rec["sentinel_in_file"] = bool(sent) and sent in text
    if isinstance(doc, dict) and rec.get("self_declared"):
        rec["reason"] = f"self-declared:{str(doc.get('state')).upper()}"
        return rec
    if sent and sent not in text:
        rec["reason"] = "sentinel-absent"
        return rec
    ret_path = probe_dir / "SUBAGENT-RETURN.json"
    man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
    if not ret_path.is_file() or not man_path.is_file():
        rec["reason"] = "predicate:absent-return-or-manifest"
        return rec
    try:
        ret = json.loads(ret_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        rec["reason"] = "return-unparseable"
        return rec
    if isinstance(ret, dict):
        st_ret = str(ret.get("status") or ret.get("state") or "").upper()
        rec["return_status"] = st_ret
        if st_ret in NOT_DELIVERING:
            rec["reason"] = f"return:{st_ret}"
            return rec
        n_named = 0
        for key in ("named_probes", "probes"):
            for item in ret.get(key) or []:
                if isinstance(item, dict) and isinstance(item.get("command"), str) and item["command"].strip():
                    n_named += 1
        rec["named_cmds"] = n_named
        if n_named < 1 and not rec["has_probe1"]:
            rec["reason"] = "named-probes-absent"
            return rec
    try:
        man = json.loads(man_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        rec["reason"] = "per-unit-manifest-unparseable"
        return rec
    rows = [
        a
        for a in (man.get("artifacts") or [])
        if isinstance(a, dict) and a.get("unit_id") == uid
    ]
    if not rows:
        rec["reason"] = "per-unit-manifest-row-absent"
        return rec
    live_sha = digest_file(out)
    rec["live_sha"] = live_sha
    matching = [
        a
        for a in rows
        if str(a.get("path") or "").replace("\\", "/") == rel
        and str(a.get("sha256") or "") == live_sha
        and a.get("present") is True
    ]
    if not matching:
        rec["reason"] = "manifest-sha-mismatch"
        rec["man_paths"] = [
            str(a.get("path") or "") for a in rows if isinstance(a, dict)
        ][:6]
        rec["man_sha_for_rel"] = [
            str(a.get("sha256") or "")[:16]
            for a in rows
            if str(a.get("path") or "").replace("\\", "/") == rel
        ]
        rec["man_present"] = [
            a.get("present")
            for a in rows
            if str(a.get("path") or "").replace("\\", "/") == rel
        ]
        return rec
    rec["reason"] = "envelope-ok-probes-unmeasured"
    return rec


def main() -> int:
    assigned = load_ids()
    jl = jsonl_index()
    reasons = Counter()
    census_cls = Counter()
    rows = []
    for cls_name, uid in assigned:
        d = diagnose(uid)
        d["shard"] = cls_name
        rec = jl.get(uid) or {}
        d["census_cls"] = rec.get("cls")
        d["census_line"] = (rec.get("line") or "")[:180]
        reasons[d.get("reason") or "unknown"] += 1
        census_cls[str(rec.get("cls") or "none")] += 1
        rows.append(d)
    out = {
        "n": len(assigned),
        "reasons": dict(reasons),
        "census_cls": dict(census_cls),
        "samples": {},
    }
    by_reason: dict[str, list] = {}
    for r in rows:
        by_reason.setdefault(r.get("reason") or "unknown", []).append(r)
    for k, vs in by_reason.items():
        out["samples"][k] = vs[:8]
    dest = WAVE / "ovh-monitor" / "g1-shards" / "_envelope_diag.json"
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n": out["n"], "reasons": out["reasons"], "census_cls": out["census_cls"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
