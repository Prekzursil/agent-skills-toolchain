#!/usr/bin/env python3
"""IMP-0114 probe2 (verifier): an independent recomputation of the reference
graph (separate walk, no linter code reused) produces the SAME dangling and
orphan sets as the linter."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.marketplace.index_linter import lint_index, reference_graph  # noqa: E402


def dig(b):
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def independent_sets(base, idx):
    """Hand-rolled second walk of the same document."""
    pkgs = idx.get("packages") or []
    referenced = set()
    ids = set()
    deps = set()
    for pkg in pkgs:
        ids.add(pkg.get("id"))
        blob = str(pkg.get("blob") or "").replace(chr(92), "/")
        referenced.add(blob)
        for dep in pkg.get("dependencies") or []:
            deps.add(dep)
    stored = set()
    for f in base.rglob("*"):
        if f.is_file():
            rel = f.relative_to(base).as_posix()
            if rel != "index.json":
                stored.add(rel)
    return {
        "dangling": sorted(referenced - stored),
        "orphan": sorted(stored - referenced),
        "unresolved": sorted(d for d in deps if d not in ids),
    }


def main():
    work = Path(tempfile.mkdtemp(prefix="imp0114-p2-"))
    try:
        base = work / "registry"
        (base / "blobs").mkdir(parents=True)
        (base / "blobs" / "a.bin").write_bytes(b"aaa")
        (base / "blobs" / "orphan.bin").write_bytes(b"ooo")
        idx = {"packages": [
            {"id": "p@1", "blob": "blobs/a.bin", "digest": dig(b"aaa"), "dependencies": ["ghost@1"]},
            {"id": "p@1", "blob": "blobs/missing.bin", "digest": "0" * 64},
        ]}
        (base / "index.json").write_text(json.dumps(idx), encoding="utf-8")
        findings = lint_index(base, idx)
        linter_dangling = sorted(f["path"] for f in findings if f["code"] == "DANGLING_BLOB")
        linter_orphan = sorted(f["path"] for f in findings if f["code"] == "ORPHAN_BLOB")
        linter_unres = sorted(f["path"] for f in findings if f["code"] == "UNRESOLVED_DEPENDENCY")
        indep = independent_sets(base, idx)
        checks = {
            "dangling_sets_equal": linter_dangling == indep["dangling"],
            "orphan_sets_equal": linter_orphan == indep["orphan"],
            "unresolved_sets_equal": linter_unres == indep["unresolved"],
            "nonempty_dangling": linter_dangling == ["blobs/missing.bin"],
            "nonempty_orphan": linter_orphan == ["blobs/orphan.bin"],
        }
        print(json.dumps({"linter": {"dangling": linter_dangling, "orphan": linter_orphan, "unresolved": linter_unres}, "independent": indep, "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0114-probe2 graph disagreement")
            return 1
        print("SUCCESS:IMP-0114-probe2 independent graph walk matches the linter sets exactly")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
