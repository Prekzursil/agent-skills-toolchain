#!/usr/bin/env python3
"""Diagnose assigned envelope-class G-1 IDs (catalog + jsonl + live files)."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WAVE = REPO / "command-center" / "p2-wave"
SHARDS = WAVE / "ovh-monitor" / "g1-shards"
JSONL = WAVE / "ovh-monitor" / "g1-local-full.jsonl"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
PROBES = WAVE / "probes"
OUT = SHARDS / "_diag_envelope.json"


def ids_from(name: str) -> list[str]:
    p = SHARDS / name
    if not p.is_file():
        return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    files = {
        "predicate": ids_from("class-predicate.txt"),
        "sha": ids_from("class-sha.txt"),
        "sentinel": ids_from("class-sentinel.txt"),
        "output": ids_from("class-output.txt"),
    }
    assigned: list[str] = []
    seen = set()
    for group, uids in files.items():
        for uid in uids:
            if uid not in seen:
                assigned.append(uid)
                seen.add(uid)

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_id = {u["id"]: u for u in cat.get("work_units") or [] if isinstance(u, dict) and "id" in u}

    jsonl: dict[str, dict] = {}
    if JSONL.is_file():
        with JSONL.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                uid = rec.get("id")
                if uid in seen:
                    jsonl[uid] = rec

    rows = []
    cls_c = Counter()
    live_c = Counter()
    for uid in assigned:
        unit = by_id.get(uid) or {}
        rec = jsonl.get(uid) or {}
        rel = str(unit.get("output_path") or "").replace("\\", "/")
        sent = str(unit.get("completion_sentinel") or "")
        schema = str(unit.get("output_schema") or "")
        out = REPO / rel if rel else None
        probe_dir = PROBES / uid
        ret_path = probe_dir / "SUBAGENT-RETURN.json"
        man_path = probe_dir / "UNIT-ARTIFACT-MANIFEST.json"
        info = {
            "id": uid,
            "jsonl_ok": rec.get("ok"),
            "jsonl_cls": rec.get("cls"),
            "jsonl_line": rec.get("line"),
            "output_path": rel,
            "completion_sentinel": sent,
            "output_schema": schema,
            "out_exists": bool(out and out.is_file()),
            "out_bytes": out.stat().st_size if out and out.is_file() else 0,
            "probe_dir": probe_dir.is_dir(),
            "return_exists": ret_path.is_file(),
            "manifest_exists": man_path.is_file(),
            "probe1": sorted(p.name for p in probe_dir.glob("probe1*.py")) if probe_dir.is_dir() else [],
            "probe2": sorted(p.name for p in probe_dir.glob("probe2*.py")) if probe_dir.is_dir() else [],
        }
        live = "ok"
        if not unit:
            live = "catalog-missing"
        elif not probe_dir.is_dir():
            live = "predicate:absent-probe-dir"
        elif not rel:
            live = "predicate:absent-no-output_path"
        elif not out or not out.is_file() or out.stat().st_size <= 0:
            live = "predicate:absent-output"
        else:
            try:
                text = out.read_text(encoding="utf-8")
                doc = json.loads(text)
            except Exception as exc:
                live = f"unparseable:{type(exc).__name__}"
                doc = None
                text = ""
            if live == "ok":
                if isinstance(doc, dict):
                    st = str(doc.get("state") or "").upper()
                    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
                        live = f"self-declared:{st}"
                    elif sent and sent not in text:
                        live = "sentinel-absent"
                if live == "ok" and (not ret_path.is_file() or not man_path.is_file()):
                    live = "predicate:absent-return-or-manifest"
                if live == "ok":
                    try:
                        ret = json.loads(ret_path.read_text(encoding="utf-8"))
                    except Exception:
                        ret = None
                    if not isinstance(ret, dict):
                        live = "return-unparseable"
                    else:
                        st_ret = str(ret.get("status") or ret.get("state") or "").upper()
                        if st_ret in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
                            live = f"return:{st_ret}"
                if live == "ok":
                    try:
                        man = json.loads(man_path.read_text(encoding="utf-8"))
                    except Exception:
                        man = None
                    if not isinstance(man, dict):
                        live = "per-unit-manifest-unparseable"
                    else:
                        rows_m = [
                            a
                            for a in (man.get("artifacts") or [])
                            if isinstance(a, dict) and a.get("unit_id") == uid
                        ]
                        if not rows_m:
                            live = "per-unit-manifest-row-absent"
                        else:
                            live_sha = digest(out)
                            info["live_sha"] = live_sha
                            matching = [
                                a
                                for a in rows_m
                                if str(a.get("path") or "").replace("\\", "/") == rel
                                and str(a.get("sha256") or "") == live_sha
                                and a.get("present") is True
                            ]
                            if not matching:
                                live = "manifest-sha-mismatch"
                                info["man_sha"] = [
                                    a.get("sha256")
                                    for a in rows_m
                                    if str(a.get("path") or "").replace("\\", "/") == rel
                                ]
                if live == "ok":
                    named = False
                    if isinstance(ret, dict):
                        for item in (ret.get("named_probes") or []) + (ret.get("probes") or []):
                            if isinstance(item, dict) and item.get("command"):
                                named = True
                    if not named:
                        p1 = list(probe_dir.glob("probe1*.py"))
                        p2 = list(probe_dir.glob("probe2*.py"))
                        named = bool(p1 and p2) or (probe_dir / "run_probes.py").is_file()
                    if not named:
                        live = "named-probes-absent"
        info["live"] = live
        live_c[live] += 1
        cls_c[str(rec.get("cls") or rec.get("line") or "NO-JSONL")] += 1
        if rec.get("line"):
            info["fail_line"] = rec.get("line")
        if rec.get("tail"):
            info["tail_head"] = str(rec.get("tail"))[:400]
        rows.append(info)

    payload = {
        "n_assigned": len(assigned),
        "by_file": {k: len(v) for k, v in files.items()},
        "jsonl_cls": cls_c.most_common(),
        "live": live_c.most_common(),
        "rows": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n_assigned": len(assigned), "jsonl_cls": cls_c.most_common(), "live": live_c.most_common()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
