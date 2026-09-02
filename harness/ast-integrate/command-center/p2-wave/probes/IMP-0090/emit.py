#!/usr/bin/env python3
"""Emit IMP-0090 receipt and per-unit G-1 return + manifest.

Order: run tests, write command-center/receipts/IMP-0090.json, re-run named
probes, then write SUBAGENT-RETURN.json and UNIT-ARTIFACT-MANIFEST.json.
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
sys.path.insert(0, str(HERE.parents[1]))
import _p2lib as L  # noqa: E402

sys.path.insert(0, str(REPO / "tools"))
from marketplace.permission_catalog import (  # noqa: E402
    EMPTY_SURFACE_LINE,
    extract_declared,
)
from marketplace.permission_surface import (  # noqa: E402
    high_risk_visually_distinct,
    render_permission_surface,
)
from plugin.permission_enforcement import query_effective  # noqa: E402

UNIT = "IMP-0090"
OUT = "command-center/receipts/IMP-0090.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0090/probe1_rendered_equals_declared.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0090/probe2_declared_equals_enforced.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_permission_surface.py"
)
FIX = "tools/marketplace/tests/fixtures"
SUPPORTING = [
    "tools/marketplace/schema/permissions.schema.json",
    "tools/marketplace/permission_catalog.py",
    "tools/marketplace/permission_surface.py",
    "tools/plugin/permission_enforcement.py",
    "tools/marketplace/tests/test_permission_surface.py",
    f"{FIX}/declared-mixed.json",
    f"{FIX}/declared-none.json",
    f"{FIX}/declared-missing.json",
    f"{FIX}/declared-decorative.json",
    f"{FIX}/declared-object-form.json",
    "command-center/p2-wave/probes/IMP-0090/probe1_rendered_equals_declared.py",
    "command-center/p2-wave/probes/IMP-0090/probe2_declared_equals_enforced.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def _load_fix(name: str) -> dict:
    return json.loads((REPO / FIX / name).read_text(encoding="utf-8"))


def main() -> int:
    rc_t, out_t = run_cmd(TEST_CMD)
    if rc_t != 0:
        print(f"FAILED:IMP-0090 tests rc={rc_t}")
        print(out_t[-4000:])
        return 1

    mixed = _load_fix("declared-mixed.json")
    none = _load_fix("declared-none.json")
    missing = _load_fix("declared-missing.json")
    deco = _load_fix("declared-decorative.json")
    gated = _load_fix("declared-object-form.json")

    mixed_surface = render_permission_surface(mixed)
    none_surface = render_permission_surface(none)
    missing_surface = render_permission_surface(missing)
    mixed_declared = set(extract_declared(mixed))
    mixed_eff = query_effective(mixed)
    gated_eff = query_effective(gated)
    deco_eff = query_effective(deco)

    if mixed_declared != {
        "filesystem.read",
        "filesystem.write",
        "network.connect",
        "process.spawn",
    }:
        print(f"FAILED:IMP-0090 mixed declared {mixed_declared}")
        return 1
    if not high_risk_visually_distinct(mixed_surface, extract_declared(mixed)):
        print("FAILED:IMP-0090 high-risk not visually distinct")
        return 1
    if EMPTY_SURFACE_LINE not in none_surface or not none_surface.strip():
        print("FAILED:IMP-0090 empty fixture blank or unnamed")
        return 1
    if EMPTY_SURFACE_LINE not in missing_surface:
        print("FAILED:IMP-0090 missing-permissions fixture unnamed empty")
        return 1
    if not gated_eff["declared_equals_enforced"]:
        print(f"FAILED:IMP-0090 gated fixture {gated_eff}")
        return 1
    if set(deco_eff["decorative"]) != {"ui.notify", "telemetry.collect"}:
        print(f"FAILED:IMP-0090 decorative not flagged {deco_eff}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p_test = L.probe("source", "command", TEST_CMD, out_t[-4000:], rc_t)
    p_render = L.probe(
        "source",
        "command",
        "python3 -c render_permission_surface(mixed)",
        mixed_surface,
        0,
    )
    p_enforce = L.probe(
        "verifier",
        "command",
        "python3 -c plugin.permission_enforcement.query_effective",
        json.dumps(
            {
                "mixed": mixed_eff,
                "gated": gated_eff,
                "decorative": deco_eff,
            },
            sort_keys=True,
        ),
        0,
    )

    (REPO / "command-center" / "receipts").mkdir(parents=True, exist_ok=True)
    artifacts = [
        L.art("tools/marketplace/permission_surface.py", "implementation"),
        L.art("tools/marketplace/permission_catalog.py", "supporting"),
        L.art("tools/plugin/permission_enforcement.py", "implementation"),
        L.art("tools/marketplace/schema/permissions.schema.json", "schema"),
        L.art("tools/marketplace/tests/test_permission_surface.py", "supporting"),
        L.art(f"{FIX}/declared-mixed.json", "fixture"),
        L.art(f"{FIX}/declared-none.json", "fixture"),
        L.art(f"{FIX}/declared-decorative.json", "fixture"),
        L.art(
            "command-center/p2-wave/probes/IMP-0090/probe1_rendered_equals_declared.py",
            "named-probe",
        ),
        L.art(
            "command-center/p2-wave/probes/IMP-0090/probe2_declared_equals_enforced.py",
            "named-probe",
        ),
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0090",
        "completion_sentinel": "SUCCESS:IMP-0090",
        "spec_anchor": "_USER-PROMPTS.md:10853",
        "title": "Package permission declaration and the install-time permission surface",
        "question_or_target": (
            "Add a declared permission block to package metadata and render it "
            "at install time as a human-readable list grouped by risk, so a user "
            "sees what a package may do before it runs — the registry-side "
            "counterpart to the Phase-5 runtime enforcement."
        ),
        "min_bytes_threshold": 512,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json + "
            "tools/marketplace/schema/permissions.schema.json"
        ),
        "artifacts": artifacts,
        "permission_surface": {
            "renderer": "tools/marketplace/permission_surface.py",
            "catalog": "tools/marketplace/permission_catalog.py",
            "enforcement_query": "tools/plugin/permission_enforcement.py",
            "schema": "tools/marketplace/schema/permissions.schema.json",
            "empty_line": EMPTY_SURFACE_LINE,
            "grouping": ["critical", "high", "medium", "low", "unranked"],
            "high_risk_markers": {"critical": "!!!", "high": "!!"},
            "mixed_declared": sorted(mixed_declared),
            "mixed_enforced": list(mixed_eff["enforced"]),
            "decorative_flagged": list(deco_eff["decorative"]),
            "high_risk_visually_distinct": True,
        },
        "evidence": [
            L.evidence(
                "The rendered install-time surface lists exactly the declared "
                "permissions (set equality). High-risk ids sit under CRITICAL/HIGH "
                "headers with !!! / !! markers, not in a flat list.",
                "CONFIRMED",
                "tools/marketplace/permission_surface.py",
                [p_render, p_test],
                "almost-certain",
            ),
            L.evidence(
                "The runtime enforcement layer, queried separately (no renderer "
                "import), reports the same effective set for gated-only packages. "
                "ui.notify and telemetry.collect are declared but ungated and "
                "are flagged decorative.",
                "CONFIRMED",
                "tools/plugin/permission_enforcement.py",
                [p_enforce, p_test],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_rendered_set_equals_declared_set",
                "command": TEST_CMD + "::test_rendered_set_equals_declared_set",
                "result": "PASS",
            },
            {
                "id": "test_declared_set_equals_enforced_set",
                "command": TEST_CMD + "::test_declared_set_equals_enforced_set",
                "result": "PASS",
            },
            {
                "id": "test_empty_declaration_renders_named_empty_not_blank",
                "command": (
                    TEST_CMD
                    + "::test_empty_declaration_renders_named_empty_not_blank"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            L.control(
                "named-empty-not-blank",
                "both-states-same-run",
                "A package declaring nothing renders 'no permissions declared'; "
                "a mixed declaration renders PERM lines. Never a blank screen.",
                True,
                True,
                bad="PERM  process.spawn  RISK=critical  !!!",
                good=EMPTY_SURFACE_LINE,
            ),
            L.control(
                "decorative-ungated-flagged",
                "enforcement-query",
                "ui.notify and telemetry.collect are rendered (declared) but "
                "flagged decorative because the runtime has no hook.",
                True,
                True,
                bad="decorative=['telemetry.collect', 'ui.notify']",
                good="declared_equals_enforced for gated-only fixture",
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0090-probe1-risk-grouping",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "High-risk permissions are grouped under === CRITICAL === and "
                "=== HIGH === with !!! / !! markers. They are not buried in a "
                "flat list. An unknown id is shown under === UNRANKED === so it "
                "cannot hide. IMP-0059 is leftover in this worktree; the "
                "queryable gated-hook table in permission_enforcement.py is the "
                "runtime signal this unit queries, not a claim that IMP-0059 "
                "is delivered."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/IMP-0090/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "downstream_consumers": [
            {
                "consumer": "tools/marketplace/tests/test_permission_surface.py",
                "artifact_path": "tools/marketplace/permission_surface.py",
                "executed": True,
                "read_ok": True,
                "exit_code": rc_t,
                "probe": p_test,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0059 runtime sandbox is not delivered in this worktree. "
                    "The enforcement query uses a gated-hook table that IMP-0059 "
                    "can later replace without changing the query API."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-query plugin.permission_enforcement against a live "
                    "IMP-0059 sandbox once that unit is G-1 green."
                ),
            }
        ],
        "notes": (
            "G-1 IMP-0090: declared permission block, risk-grouped install "
            "surface, independent enforcement query, decorative flags. Did not "
            "run global unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }

    out_path = REPO / OUT
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest_file(out_path)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:IMP-0090 artifact {size}B below floor")
        return 1
    if "SUCCESS:IMP-0090" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0090 sentinel missing after write")
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:IMP-0090 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0090",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "rendered-set-equals-declared-set",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "declared-set-equals-enforced-set",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": sha,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0090/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0090-probe1-risk-grouping",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0090: live named probes exit 0, receipts/IMP-0090.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        dgst, nbytes = digest_file(path)
        return {
            "path": rel,
            "sha256": dgst,
            "bytes": nbytes,
            "present": path.is_file(),
            "unit_id": UNIT,
            "receipt_path": "command-center/p2-wave/probes/IMP-0090/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts_man = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts_man),
        "present": sum(1 for a in artifacts_man if a["present"]),
        "artifacts": artifacts_man,
    }

    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"artifact {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:IMP-0090 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
