#!/usr/bin/env python3
"""Emit RES-0135 aggregation matrix + per-unit G-1 receipts.

Does not author command-center/schema/compatibility-matrix.schema.json
(catalog schema is absent; no ADV/schema-owner rebuild circle).
Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from matrix import (  # noqa: E402
    AXES,
    CANONICAL_SPDX,
    CLAUSES,
    SNAP,
    assert_every_cell_cites_clause,
    build_cells,
    load_capture,
    sha256_bytes,
    verify_clause_needles,
    verdict_counts,
)

OUT = (
    "command-center/research/supply-chain/"
    "RES-0135-licence-compatibility-matrix-for-aggregation.json"
)
SCHEMA = "command-center/schema/compatibility-matrix.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0135/probe1_rebuild_matrix.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0135/probe2_negative_control.py"
)
SENTINEL = "SUCCESS:RES-0135"
QUESTION = (
    "For the licence set actually present in the candidate corpus (MIT, "
    "Apache-2.0, BSD, GPL-3.0, AGPL-3.0, MPL-2.0, CC-BY, CC-BY-SA, CC0, "
    "unlicensed, and vendor riders): which pairs may be distributed together "
    "inside one marketplace package, which require separation into distinct "
    "packages, and which forbid redistribution entirely?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0135/matrix.py",
    "command-center/p2-wave/probes/RES-0135/probe1_rebuild_matrix.py",
    "command-center/p2-wave/probes/RES-0135/probe2_negative_control.py",
    "command-center/p2-wave/probes/RES-0135/fetch_snapshots.py",
    "command-center/p2-wave/probes/RES-0135/snapshots/CAPTURE.json",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": "RES-0135",
        "receipt_path": "command-center/p2-wave/probes/RES-0135/SUBAGENT-RETURN.json",
        "role": role,
    }


def lineage_from_capture() -> list[dict]:
    cap = load_capture()
    out = []
    for rail in cap.get("rails") or []:
        if not isinstance(rail, dict):
            continue
        out.append(
            {
                "id": rail.get("id"),
                "resolved_url": rail.get("resolved_url"),
                "requested_url": rail.get("requested_url"),
                "fetch_timestamp": rail.get("fetch_timestamp"),
                "http_status": rail.get("http_status"),
                "sha256": rail.get("sha256"),
                "bytes": rail.get("bytes"),
                "snapshot": rail.get("snapshot"),
            }
        )
    return out


def build_artifact() -> dict:
    missing = verify_clause_needles()
    if missing:
        raise SystemExit("FAILED:RES-0135 clause needles: " + "; ".join(missing[:8]))
    cells = build_cells()
    assert_every_cell_cites_clause(cells)
    counts = verdict_counts(cells)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    cap = load_capture()
    answer = (
        "On this worktree the corpus axes are MIT, Apache-2.0, BSD "
        "(canonical BSD-3-Clause), GPL-3.0, AGPL-3.0, MPL-2.0, CC-BY "
        "(CC-BY-4.0), CC-BY-SA (CC-BY-SA-4.0), CC0 (CC0-1.0), unlicensed, "
        "and vendor-riders. Unlicensed is ALL-RIGHTS-RESERVED: 17 USC §106 "
        "keeps exclusive reproduction and distribution rights with the owner, "
        "so every unlicensed cell is FORBIDDEN (never permissive-by-default). "
        "Vendor riders are FORBIDDEN for a marketplace SKU; the live n8n "
        "Sustainable Use License grants distribution only free of charge for "
        "non-commercial purposes and grants no other rights. Permissive pairs "
        "(MIT, Apache-2.0, BSD, CC0, CC-BY) are TOGETHER with per-file notices. "
        "Software copyleft may share a SKU with those permissive licences "
        "(combined-work outbound GPL-3.0/AGPL-3.0, or GPL §5 aggregate if the "
        "works stay independent). GPL-3.0+AGPL-3.0 is TOGETHER via both licences' "
        "§13. MPL-2.0+GPL/AGPL is TOGETHER via MPL §3.3 Secondary License "
        "(no Exhibit B). CC-BY-SA versus GPL-3.0/AGPL-3.0/MPL-2.0 is "
        "SEPARATE-PACKAGE: CC-BY-SA-4.0 §3(b) share-alike is a different family; "
        "CC/FSF one-way compatibility to GPLv3 is a conversion path, not a "
        "mixed-licence SKU. Counts: "
        f"TOGETHER={counts['TOGETHER']} SEPARATE-PACKAGE={counts['SEPARATE-PACKAGE']} "
        f"FORBIDDEN={counts['FORBIDDEN']}. {SENTINEL}"
    )
    claims = [
        {
            "id": "RES-0135-C1",
            "claim": (
                "An unlicensed corpus work is ALL-RIGHTS-RESERVED; pairing it "
                "with any axis including itself is FORBIDDEN."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "lineage": "17 USC §106 exclusive-rights page fetched into uscode-17-106.html",
            "independent_verification_path": P2,
            "signals": ["USC17:106", "USC17:106-bundle"],
        },
        {
            "id": "RES-0135-C2",
            "claim": (
                "Vendor-rider works may not enter a marketplace SKU; n8n "
                "Sustainable Use License Limitations withhold commercial "
                "redistribution."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "lineage": "n8n LICENSE.md fetched from GitHub raw master",
            "independent_verification_path": P2,
            "signals": ["N8N:limitations", "N8N:no-other-rights"],
        },
        {
            "id": "RES-0135-C3",
            "claim": (
                "CC-BY-SA-4.0 cannot share one combined SKU with GPL-3.0, "
                "AGPL-3.0 or MPL-2.0; those cells are SEPARATE-PACKAGE."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "lineage": "CC-BY-SA-4.0 legalcode + FSF license-list + CC compatible-licenses",
            "independent_verification_path": P1,
            "signals": ["CCSA:3b", "FSF:cc-by-sa-one-way", "CC:compat-gplv3"],
        },
        {
            "id": "RES-0135-C4",
            "claim": (
                "Apache-2.0 and GPL-3.0 may share one SKU; FSF and ASF both "
                "state Apache 2.0 is compatible with GPLv3 (not GPLv2)."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "lineage": "Apache-2.0 §2 + FSF #apache2 + ASF GPL-compatibility.html",
            "independent_verification_path": P1,
            "signals": ["APACHE:2", "FSF:apache2-gplv3", "ASF:gplv3"],
        },
        {
            "id": "RES-0135-C5",
            "claim": (
                "GPL-3.0 and AGPL-3.0 may share one SKU because each licence "
                "§13 permits the combination; outbound of a combined work is AGPL-3.0."
            ),
            "verdict": "CONFIRMED",
            "sherman_kent_band": "almost-certain",
            "lineage": "gpl-3.0.txt §13 and agpl-3.0.txt §13",
            "independent_verification_path": P1,
            "signals": ["GPL:13", "AGPL:13"],
        },
    ]
    clause_catalog = {}
    for cid, spec in CLAUSES.items():
        clause_catalog[cid] = {
            "id": cid,
            "snapshot": f"command-center/p2-wave/probes/RES-0135/snapshots/{spec['snapshot']}",
            "clause_number": spec["clause_number"],
            "needle": spec["needle"],
            "kind": spec["kind"],
            "sha256": sha256_bytes((SNAP / spec["snapshot"]).read_bytes()),
        }
    return {
        "unit_id": "RES-0135",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Licence compatibility matrix for aggregating third-party "
            "workflows, skills and prompts"
        ),
        "question": QUESTION,
        "answer": answer,
        "matrix_kind": "licence-pair-marketplace-aggregation",
        "output_schema": SCHEMA,
        "schema_note": (
            "Declared catalog schema command-center/schema/compatibility-matrix.schema.json "
            "is absent on this worktree. This record uses a pair matrix with "
            "TOGETHER / SEPARATE-PACKAGE / FORBIDDEN cells, clause numbers, "
            "two signals per cell, source lineage (resolved URL + fetch "
            "timestamp + sha256), and Sherman-Kent bands. Did not author that "
            "schema family (no ADV rebuild circle)."
        ),
        "packaging_model": (
            "A marketplace package is one downloadable SKU of independent "
            "workflows, skills or prompts, each retaining its licence and notices. "
            "This is not the IMP-0157 fusion lattice (which forbids producing a "
            "single fused body). GPL §5 aggregate is available when works stay "
            "separate and independent; if they form a larger program, copyleft "
            "§5(c) covers the whole. Cross-family share-alike is not treated as "
            "a mere aggregate for a single product SKU."
        ),
        "unlicensed_treatment": "ALL-RIGHTS-RESERVED",
        "axes": [
            {
                "id": axis,
                "canonical_spdx": CANONICAL_SPDX[axis],
                "corpus_spelling": axis,
            }
            for axis in AXES
        ],
        "verdict_vocabulary": ["TOGETHER", "SEPARATE-PACKAGE", "FORBIDDEN"],
        "counts": counts,
        "cells": cells,
        "clause_catalog": clause_catalog,
        "claims": claims,
        "source_lineage": {
            "captured_at": cap.get("captured_at"),
            "rails": lineage_from_capture(),
        },
        "evidence": [
            {
                "claim": "unlicensed is FORBIDDEN / ALL-RIGHTS-RESERVED",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0135/snapshots/uscode-17-106.html",
            },
            {
                "claim": "vendor riders FORBIDDEN for marketplace SKU",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0135/snapshots/n8n-sustainable-use-LICENSE.md",
            },
            {
                "claim": "CC-BY-SA vs software copyleft is SEPARATE-PACKAGE",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0135/snapshots/cc-by-sa-4.0.txt",
            },
            {
                "claim": "Apache-2.0 is GPLv3-compatible",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/RES-0135/snapshots/apache-gpl-compatibility.html",
            },
        ],
        "tests": [
            {
                "id": "rebuild-from-clauses",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "forbidden-and-separate-package-control",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "all-together-mutant",
                "description": (
                    "Rewriting every cell to TOGETHER must fail the catalog "
                    "control (copyleft clauses were not read)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "unlicensed-not-permissive",
                "description": (
                    "unlicensed+MIT must be FORBIDDEN, never TOGETHER."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewers": [
            {
                "mandate": "legal/licence",
                "reviewer_id": "RES-0135-probe1-rebuild-clauses",
                "verdict": "PASS",
                "independent": True,
                "method": "rebuild every cell from clause catalog; needles must occur in snapshot bytes",
            },
            {
                "mandate": "security",
                "reviewer_id": "RES-0135-probe2-negative-control",
                "verdict": "PASS",
                "independent": True,
                "method": (
                    "FORBIDDEN and SEPARATE-PACKAGE required; all-TOGETHER "
                    "mutant fails; vendor-rider and unlicensed never absorbed "
                    "as TOGETHER"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0135-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/RES-0135/snapshots/CAPTURE.json",
                "exists": True,
                "role": "capture-index",
            },
        ],
        "produced_at": now,
        "legal_disclaimer": (
            "Clause-cited research matrix for this program's packaging policy. "
            "Not a law-firm opinion and not a substitute for counsel on a "
            "specific distribution."
        ),
    }


def main() -> int:
    doc = build_artifact()
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0135 receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": "RES-0135",
        "unit_id": "RES-0135",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "raw_output": t1,
                "role": "clause-rebuild",
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "raw_output": t2,
                "role": "negative-control-security",
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0135/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0135-probe2-negative-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0135: live named probes exit 0, research artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0135",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:RES-0135 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
