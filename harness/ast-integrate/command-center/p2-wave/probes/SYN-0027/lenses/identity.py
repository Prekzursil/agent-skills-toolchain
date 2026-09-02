"""Prove the self-audit runner imports the canonical lens files unmodified.

If an upstream unit (SYN-0014/0015/0017/0022) later ships a lens file, that
file must be byte-identical to the copy imported here. A rewritten fork fails.
When no upstream file exists, this unit is the first ship: identity still
requires imported __file__ bytes == the canonical files in this directory.
"""
from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]

LENS_MODULES = {
    "SYN-0014": "syn_0014",
    "SYN-0015": "syn_0015",
    "SYN-0017": "syn_0017",
    "SYN-0022": "syn_0022",
}

UPSTREAM_CANDIDATES = {
    "SYN-0014": [
        "command-center/p2-wave/probes/SYN-0014/lens.py",
        "command-center/p2-wave/probes/SYN-0014/unsupported_certainty.py",
        "command-center/p2-wave/probes/SYN-0014/syn_0014.py",
        "tools/meta_review/syn_0014.py",
    ],
    "SYN-0015": [
        "command-center/p2-wave/probes/SYN-0015/lens.py",
        "command-center/p2-wave/probes/SYN-0015/quantifier_overclaim.py",
        "command-center/p2-wave/probes/SYN-0015/syn_0015.py",
        "tools/meta_review/syn_0015.py",
    ],
    "SYN-0017": [
        "command-center/p2-wave/probes/SYN-0017/lens.py",
        "command-center/p2-wave/probes/SYN-0017/mechanism_dedup.py",
        "command-center/p2-wave/probes/SYN-0017/syn_0017.py",
        "tools/meta_review/syn_0017.py",
    ],
    "SYN-0022": [
        "command-center/p2-wave/probes/SYN-0022/lens.py",
        "command-center/p2-wave/probes/SYN-0022/premise_reprobe.py",
        "command-center/p2-wave/probes/SYN-0022/syn_0022.py",
        "tools/meta_review/syn_0022.py",
    ],
}


def sha256_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def check() -> dict[str, Any]:
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    rows: list[dict[str, Any]] = []
    mismatches: list[str] = []
    upstream_present: list[dict[str, Any]] = []
    for lid, modname in LENS_MODULES.items():
        canonical = HERE / f"{modname}.py"
        mod = importlib.import_module(modname)
        imported = Path(getattr(mod, "__file__", "")).resolve()
        c_sha = sha256_file(canonical)
        i_sha = sha256_file(imported) if imported.is_file() else ""
        identical = imported == canonical.resolve() and i_sha == c_sha
        if not identical:
            mismatches.append(lid)
        up_hits = []
        for rel in UPSTREAM_CANDIDATES[lid]:
            p = REPO / rel
            if p.is_file():
                u_sha = sha256_file(p)
                up_hits.append(
                    {
                        "path": rel,
                        "sha256": u_sha,
                        "matches_canonical": u_sha == c_sha,
                    }
                )
                if u_sha != c_sha:
                    mismatches.append(f"{lid}:upstream-diff:{rel}")
        if up_hits:
            upstream_present.extend({"id": lid, **h} for h in up_hits)
        rows.append(
            {
                "id": lid,
                "canonical_path": canonical.relative_to(REPO).as_posix(),
                "imported_path": imported.relative_to(REPO).as_posix()
                if REPO in imported.parents or imported == REPO
                else str(imported),
                "canonical_sha256": c_sha,
                "imported_sha256": i_sha,
                "upstream_files": up_hits,
            }
        )
    return {
        "byte_identical": not mismatches,
        "mismatches": mismatches,
        "lenses": rows,
        "upstream_present": upstream_present,
        "upstream_absent": not upstream_present,
        "first_ship_note": (
            "No SYN-0014/0015/0017/0022 lens files exist elsewhere on this worktree. "
            "These four files are the canonical implementations; the runner imports "
            "them by path. A later upstream copy must match these bytes."
            if not upstream_present
            else "Upstream lens files were found and compared byte-for-byte."
        ),
    }
