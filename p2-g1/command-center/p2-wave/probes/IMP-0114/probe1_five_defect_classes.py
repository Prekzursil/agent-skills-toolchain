#!/usr/bin/env python3
"""IMP-0114 probe1 (source): the linter finds one planted defect of each of the
five classes and stays silent on a clean index in the same run."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.marketplace.index_linter import lint_index  # noqa: E402


def dig(b: bytes) -> str:
    return hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0114-p1-"))
    try:
        base = work / "registry"
        (base / "blobs").mkdir(parents=True)
        good = b"good blob bytes"
        second = b"second blob bytes"
        (base / "blobs" / "a.bin").write_bytes(good)
        (base / "blobs" / "b.bin").write_bytes(second)
        (base / "blobs" / "orphan.bin").write_bytes(b"unreferenced blob")
        idx = {"packages": [
            {"id": "p@1", "blob": "blobs/a.bin", "digest": dig(good), "dependencies": []},
            {"id": "p@1", "blob": "blobs/gone.bin", "digest": "0" * 64},
            {"id": "q@1", "blob": "blobs/b.bin", "digest": "f" * 64, "dependencies": ["nope@9"]},
        ]}
        findings = lint_index(base, idx)
        codes = sorted({f["code"] for f in findings})
        want = {"DANGLING_BLOB", "ORPHAN_BLOB", "DUPLICATE_ID", "DIGEST_MISMATCH", "UNRESOLVED_DEPENDENCY"}
        clean_idx = {"packages": [
            {"id": "p@1", "blob": "blobs/a.bin", "digest": dig(good), "dependencies": ["q@1"]},
            {"id": "q@1", "blob": "blobs/b.bin", "digest": dig(second)},
        ]}
        (base / "blobs" / "orphan.bin").unlink()
        clean = lint_index(base, clean_idx)
        checks = {
            "all_five_found": want.issubset(set(codes)),
            "clean_control_silent": clean == [],
        }
        print(json.dumps({"codes": codes, "clean_findings": clean, "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0114-probe1 " + json.dumps(checks))
            return 1
        print("SUCCESS:IMP-0114-probe1 five defect classes found; clean index silent")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
