#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
IDS = [
    ln.strip()
    for ln in (Path(__file__).with_name("shard-01.txt")).read_text(encoding="utf-8").splitlines()
    if ln.strip()
]


def main() -> None:
    cat = json.loads((REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    by = {u["id"]: u for u in cat["work_units"]}
    rows = []
    for uid in IDS:
        u = by.get(uid, {})
        pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
        out_rel = str(u.get("output_path") or "").replace("\\", "/")
        out = REPO / out_rel if out_rel else None
        py = sorted(p.name for p in pdir.glob("*.py")) if pdir.is_dir() else []
        emit = [n for n in py if n.startswith("emit") or n.startswith("write")]
        froms: list[str] = []
        if pdir.is_dir():
            for p in sorted(pdir.glob("probe*.py")):
                try:
                    tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
                except SyntaxError:
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        froms.append(
                            f"{p.name}:{node.module}:{[a.name for a in node.names]}"
                        )
        rec = {
            "id": uid,
            "title": (u.get("title") or "")[:90],
            "out": out_rel,
            "out_exists": bool(out and out.is_file()),
            "out_bytes": out.stat().st_size if out and out.is_file() else 0,
            "py": py,
            "emit": emit,
            "froms": froms[:16],
            "ret": (pdir / "SUBAGENT-RETURN.json").is_file(),
            "man": (pdir / "UNIT-ARTIFACT-MANIFEST.json").is_file(),
        }
        rows.append(rec)
        print(
            f"{uid} out={rec['out_exists']} {rec['out_bytes']:7d} emit={emit} npy={len(py)}"
        )
    dest = Path(__file__).with_name("_s01_inv.json")
    dest.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("wrote", dest, "n=", len(rows))
    checks = [
        "command-center/p2-wave/_measure_one_delivered.py",
        "command-center/confirmation/CNF-0028-clean-venv-install.json",
        "command-center/confirmation/CNF-0037-doc-command-conformance.json",
        "command-center/confirmation/CNF-0064-license-provenance.json",
        "command-center/schema/refutation-record.schema.json",
    ]
    print("--- ADV-0006 files ---")
    for c in checks:
        p = REPO / c
        print(c, p.is_file(), p.stat().st_size if p.is_file() else 0)
        if p.is_file() and "schema" in c:
            text = p.read_text(encoding="utf-8")
            print("  named_probes in schema", '"named_probes"' in text)
        if p.is_file() and "_measure" in c:
            text = p.read_text(encoding="utf-8")
            print("  SUCCESS:delivered in measure", "SUCCESS:delivered" in text)


if __name__ == "__main__":
    main()
