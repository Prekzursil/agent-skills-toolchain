#!/usr/bin/env python3
"""Capture the old-layout fixture from ARC-0007's de-facto repo sample.

That sample is a prior-unit capture of the live estate layout, not a tree
produced by inverting tools/layout/migrate.py.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SOURCE_REL = "command-center/p2-wave/probes/ARC-0007/fixtures/repo"
DEST_REL = "command-center/p2-wave/probes/TST-0256/fixtures/captured-old"
PROV_REL = "command-center/p2-wave/probes/TST-0256/fixtures/PROVENANCE.json"


def lf_digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def capture() -> dict:
    src = REPO / SOURCE_REL
    dest = REPO / DEST_REL
    if not src.is_dir():
        raise SystemExit(f"FAILED:TST-0256 source missing {SOURCE_REL}")
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest)
    files = []
    for path in sorted(p for p in dest.rglob("*") if p.is_file()):
        rel = path.relative_to(dest).as_posix()
        sha, size = lf_digest(path)
        src_path = src / rel
        src_sha, src_size = lf_digest(src_path)
        if sha != src_sha or size != src_size:
            raise SystemExit(f"FAILED:TST-0256 capture mismatch {rel}")
        files.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": size,
                "source_path": f"{SOURCE_REL}/{rel}",
            }
        )
    if len(files) < 8:
        raise SystemExit(f"FAILED:TST-0256 capture too small n={len(files)}")
    migrate = REPO / "tools/layout/migrate.py"
    migrate_sha = hashlib.sha256(migrate.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    doc = {
        "unit_id": "TST-0256",
        "captured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_unit": "ARC-0007",
        "source_root": SOURCE_REL,
        "source_kind": "prior-unit-de-facto-layout-sample",
        "method": "byte-copy of ARC-0007 fixtures/repo; not migrate --inverse",
        "synthesized_from_migration_script": False,
        "migration_script": "tools/layout/migrate.py",
        "migration_script_sha256": migrate_sha,
        "file_count": len(files),
        "files": files,
    }
    (REPO / PROV_REL).write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return doc


def verify() -> dict:
    prov = json.loads((REPO / PROV_REL).read_text(encoding="utf-8"))
    dest = REPO / DEST_REL
    src = REPO / SOURCE_REL
    problems: list[str] = []
    if prov.get("synthesized_from_migration_script") is not False:
        problems.append("provenance claims synthesis")
    if "migrate.py" in prov.get("source_root", ""):
        problems.append("source_root is the migrator")
    for rec in prov.get("files") or []:
        rel = rec["path"]
        cap = dest / rel
        origin = src / rel
        if not cap.is_file():
            problems.append(f"captured missing {rel}")
            continue
        if not origin.is_file():
            problems.append(f"source missing {rel}")
            continue
        cap_sha = hashlib.sha256(cap.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        src_sha = hashlib.sha256(origin.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if cap_sha != rec["sha256"]:
            problems.append(f"captured drifted {rel}")
        if src_sha != rec["sha256"]:
            problems.append(f"source drifted {rel}")
    return {
        "ok": not problems,
        "problems": problems,
        "file_count": len(prov.get("files") or []),
        "source_root": prov.get("source_root"),
        "synthesized_from_migration_script": prov.get(
            "synthesized_from_migration_script"
        ),
    }


def main() -> int:
    doc = capture()
    chk = verify()
    if not chk["ok"]:
        print("FAILED:TST-0256 capture verify", chk["problems"][:8])
        return 1
    print(json.dumps({"captured": doc["file_count"], "verify": chk["ok"]}, sort_keys=True))
    print("SUCCESS:TST-0256 capture")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
