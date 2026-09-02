#!/usr/bin/env python3
"""Probe 2: independent re-hash (sha256sum) + independent tree-location (test -d).

Different measurement from probe 1's hashlib/pathlib walk. On this Linux host
there is no PowerShell 7; /bin/sh `test -d` is the second shell.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from control_trees import ensure_control_trees  # noqa: E402
from locate import locate_trees, probe_path  # noqa: E402
from partition import sha256_file  # noqa: E402
from relevance import is_research_relevant  # noqa: E402
from schema_local import registry_of  # noqa: E402

ART = REPO / "command-center" / "research" / "RES-0127.json"


def fail(msg: str) -> int:
    print(f"FAILED:RES-0127-probe2 {msg}")
    return 1


def sha256sum_file(path: Path) -> str:
    try:
        proc = subprocess.run(
            ["sha256sum", str(path)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        proc = None
        err = exc
    else:
        err = None
    if proc is None or proc.returncode != 0:
        try:
            proc = subprocess.run(
                ["openssl", "dgst", "-sha256", str(path)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"no sha256sum/openssl: {err or exc}") from exc
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or "openssl failed")
        # SHA256(path)= digest
        text = (proc.stdout or "").strip()
        if "=" in text:
            return text.split("=", 1)[1].strip()
        return text.split()[-1]
    return (proc.stdout or "").split()[0]


def research_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if is_research_relevant(rel):
            out.append(path)
    return sorted(out)


def main() -> int:
    ctrl_a, ctrl_b = ensure_control_trees()
    mismatches = []
    hashed = 0
    for root in (ctrl_a, ctrl_b):
        for path in research_files(root):
            lib, _n = sha256_file(path)
            ext = sha256sum_file(path)
            hashed += 1
            if lib != ext:
                mismatches.append(
                    {
                        "path": str(path),
                        "hashlib": lib,
                        "sha256sum": ext,
                    }
                )
    if hashed < 6:
        return fail(f"too few control files hashed {hashed}")
    if mismatches:
        return fail(f"hashlib/sha256sum mismatch {mismatches}")

    a_ren = sha256_file(ctrl_a / "renamed-same-bytes-a.md")[0]
    b_ren = sha256_file(ctrl_b / "renamed-same-bytes-b.md")[0]
    if a_ren != b_ren:
        return fail("renamed pair bytes drifted")
    a_ident = sha256_file(ctrl_a / "control-identical.md")[0]
    b_ident = sha256_file(ctrl_b / "control-identical.md")[0]
    if a_ident != b_ident:
        return fail("identical pair bytes drifted")
    a_diff = sha256_file(ctrl_a / "control-different.md")[0]
    b_diff = sha256_file(ctrl_b / "control-different.md")[0]
    if a_diff == b_diff:
        return fail("different pair unexpectedly identical")

    located = locate_trees()
    disagree = (
        located["platform_redesign"]["disagreeing_signals"]
        + located["harness_restore"]["disagreeing_signals"]
    )
    if disagree:
        return fail(f"location signals disagree {disagree}")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    registry = registry_of(doc)
    trees = registry.get("live_trees") or {}
    for key in ("platform_redesign", "harness_restore"):
        pub = trees.get(key) or {}
        live = located[key]
        if bool(pub.get("present")) != bool(live["present"]):
            return fail(f"{key} present flag dishonest")
        pub_paths = [row.get("path") for row in pub.get("searched") or []]
        live_paths = [row["path"] for row in live["searched"]]
        if pub_paths != live_paths:
            return fail(f"{key} search list drifted")
        for prow, lrow in zip(pub.get("searched") or [], live["searched"]):
            if bool(prow.get("present")) != bool(lrow["present"]):
                return fail(f"{key} candidate {lrow['path']} present drifted")
            # re-probe this candidate independently
            again = probe_path(Path(lrow["path"]))
            if again["present"] != lrow["present"]:
                return fail(f"{key} re-probe drifted {lrow['path']}")

    cited = (registry.get("union_manifest") or {}).get("catalog_cited_unhashed") or {}
    if str(cited.get("verdict") or "").upper() != "NOT-CHECKED":
        return fail("catalog citations overclaimed as hashed")

    payload = {
        "pass": True,
        "probe": "probe2-independent-rehash",
        "control_files_rehashed": hashed,
        "sha256sum_agrees": True,
        "location_signals_agree": True,
        "live_both_present": located["both_present"],
        "renamed_same_bytes": True,
        "different_pair_differs": True,
        "hashlib_sha256": hashlib.sha256(b"IDENTICAL-BYTES-RES-0127\n").hexdigest(),
        "file_identical_sha256": a_ident,
    }
    print(json.dumps(payload, indent=1, sort_keys=True))
    print(
        f"rehashed={hashed} sha256sum_agrees=True "
        f"live_both_present={located['both_present']}"
    )
    print("SUCCESS:RES-0127-probe2 independent rehash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
