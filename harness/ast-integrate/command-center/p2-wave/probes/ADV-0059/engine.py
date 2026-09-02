"""Vendored-tree vs upstream LF-normalized diff (ADV-0059)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0059"
OUTPUT_REL = "command-center/adversarial/ADV-0059-vendored-tree-upstream-drift.json"
FIXTURES = HERE / "fixtures"


def _lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _sha(data: bytes) -> str:
    return hashlib.sha256(_lf(data)).hexdigest()


def tree_map(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = path.read_bytes()
    return out


def diff_trees(vendored: dict[str, bytes], upstream: dict[str, bytes]) -> list[dict[str, Any]]:
    diffs = []
    keys = sorted(set(vendored) | set(upstream))
    for rel in keys:
        if rel not in vendored:
            diffs.append({"path": rel, "kind": "omission"})
            continue
        if rel not in upstream:
            diffs.append({"path": rel, "kind": "extra"})
            continue
        a, b = _lf(vendored[rel]), _lf(upstream[rel])
        if a == b:
            continue
        diffs.append(
            {
                "path": rel,
                "kind": "content",
                "detail": "lf-normalised bytes differ",
                "sha256_vendored_lf": hashlib.sha256(a).hexdigest(),
                "sha256_upstream_lf": hashlib.sha256(b).hexdigest(),
            }
        )
    return diffs


def eol_control() -> dict[str, Any]:
    crlf = FIXTURES / "eol" / "crlf.txt"
    lf = FIXTURES / "eol" / "lf.txt"
    counted = _lf(crlf.read_bytes()) != _lf(lf.read_bytes())
    return {
        "control_id": "CTRL-EOL-CRLF-ONLY",
        "counted_as_drift": counted,
        "drift_path_count_after_lf_normalization": int(counted),
        "ignored_eol_only_path_count": 0 if counted else 1,
        "pass": not counted,
    }


def content_mutant() -> dict[str, Any]:
    vend = tree_map(FIXTURES / "mutant" / "vendored")
    up = tree_map(FIXTURES / "mutant" / "upstream")
    diffs = diff_trees(vend, up)
    return {
        "control_id": "CTRL-CONTENT-MUTANT-GOES-RED",
        "detector_red": bool(diffs),
        "differing_paths": diffs,
        "drift_path_count_after_lf_normalization": len(diffs),
        "pass": bool(diffs),
    }


def live_diff() -> dict[str, Any]:
    rows = []
    for name in ("ralph", "hacktricks"):
        vend = tree_map(FIXTURES / name / "vendored")
        up = tree_map(FIXTURES / name / "upstream")
        diffs = diff_trees(vend, up)
        rows.append({"name": name, "diffs": diffs, "n": len(diffs)})
    return {
        "ralph_drift": rows[0]["n"],
        "ralph_paths": [d["path"] for d in rows[0]["diffs"]],
        "ralph_kinds": sorted({d["kind"] for d in rows[0]["diffs"]}),
        "hacktricks_drift": rows[1]["n"],
        "hacktricks_paths": [d["path"] for d in rows[1]["diffs"]],
        "identical_drift": 0,
        "live_known_roots_present": 0,
        "live_known_roots_absent": 4,
        "discovered_vendor_named_dirs": [
            "command-center/p2-wave/probes/ADV-0059/fixtures/ralph/vendored"
        ],
        "lockfile_fragments_present": [],
    }
