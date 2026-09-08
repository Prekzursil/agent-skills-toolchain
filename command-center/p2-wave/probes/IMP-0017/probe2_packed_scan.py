#!/usr/bin/env python3
"""IMP-0017 probe2: packed artifact extracted .sh bytes scanned for 0x0D."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import eol_policy as eol  # noqa: E402
import pack as pack_mod  # noqa: E402

PROBE = Path(__file__).resolve().parent
WORK = PROBE / "work" / "probe2"
OUT = WORK / "plugin-pack.zip"
RAW = PROBE / "probe2-packed-scan.raw.txt"
MEAS = PROBE / "probe2-measurement.json"


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [
        "NAMED PROBE 2: PACKED ARTIFACT EXTRACTED SHELL CR SCAN",
        "PROBE-2-BEGIN:IMP-0017",
        f"repo={REPO}",
        "prefix=tools/plugin",
        "signal=packed-zip-member-bytes (post-emit)",
    ]
    result = pack_mod.pack(
        repo=REPO,
        rev="HEAD",
        allowlist=REPO / "tools/plugin/payload-allowlist.json",
        out=OUT,
        prefix="tools/plugin",
        use_real_mtimes=False,
    )
    lines.append(f"pack_sha256={result.sha256}")
    lines.append(f"member_count={len(result.members)}")
    shells = [m for m in result.members if eol.is_shell_path(m)]
    lines.append(f"packed_shell_count={len(shells)}")
    lines.append(f"packed_shells={json.dumps(shells)}")

    per_file: list[dict] = []
    total_cr = 0
    with zipfile.ZipFile(OUT) as zf:
        for name in shells:
            data = zf.read(name)
            cr = eol.count_cr(data)
            total_cr += cr
            # Cross-check vs cat-file blob for the same path.
            blob = eol.git_cat_file_blob(REPO, "HEAD", f"tools/plugin/{name}")
            row = {
                "path": name,
                "packed_bytes": len(data),
                "packed_cr": cr,
                "blob_bytes": len(blob),
                "blob_cr": eol.count_cr(blob),
                "packed_equals_blob": data == blob,
            }
            per_file.append(row)
            lines.append(
                f"packed path={name} bytes={len(data)} cr={cr} "
                f"equals_blob={data == blob} "
                f"sha12={hashlib.sha256(data).hexdigest()[:12]}"
            )

    findings = eol.scan_packed_shells(OUT)
    ok = total_cr == 0 and len(shells) >= 1 and not findings
    # Ensure every packed shell equals its cat-file blob (no archive rewrite).
    equals_all = all(r["packed_equals_blob"] for r in per_file) if per_file else False
    ok = ok and equals_all

    meas = {
        "pack_sha256": result.sha256,
        "packed_shell_count": len(shells),
        "total_cr": total_cr,
        "zero_cr": total_cr == 0,
        "packed_equals_blob_all": equals_all,
        "per_file": per_file,
        "used_git_archive": False,
        "probe_2_confirmed": ok,
    }
    MEAS.write_text(json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines.extend(
        [
            f"total_cr={total_cr}",
            f"packed_equals_blob_all={equals_all}",
            f"probe_2_confirmed={ok}",
            "PROBE-2-COMPLETE:IMP-0017",
            "SUCCESS:IMP-0017-probe2" if ok else "FAILED:IMP-0017-probe2",
        ]
    )
    raw = "\n".join(lines) + "\n"
    RAW.write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
