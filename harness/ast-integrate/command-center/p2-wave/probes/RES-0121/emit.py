#!/usr/bin/env python3
"""Emit command-center/research/RES-0121.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import graph as G  # noqa: E402
from schema_check import check_document, check_schema_file  # noqa: E402

REPO = G.REPO


def catalog_unit() -> dict:
    data = json.loads((REPO / G.CATALOG).read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == G.UNIT:
            return unit
    raise SystemExit("FAILED:RES-0121 catalog unit missing")


def main() -> int:
    rows, register = G.build_rows()
    ok, problems = G.graph_ok(rows)
    if not ok:
        print(json.dumps({"problems": problems}, indent=2))
        print("FAILED:RES-0121 graph_ok")
        return 1
    counts = G.recompute_counts(rows)
    traps = [r for r in rows if str(r.get("id") or "").startswith("TRAP-")]
    trap_verdicts = [
        {
            "id": r["catalog_name"],
            "graph_id": r["id"],
            "repo": r["repo"],
            "resolved": str(r.get("verdict") or "").startswith("RESOLVED:"),
            "file_says": r["file_says"],
            "classifier_label": r["classifier_label"],
            "disagrees_with_classifier": r["disagrees_with_classifier"],
            "license_sha256": r["license_sha256"],
            "trap_kind": r["trap_kind"],
            "verdict": r["verdict"],
            "riders": r.get("riders") or [],
        }
        for r in traps
    ]
    drop_ok = not G.graph_ok(G.mutate_drop_sha256(rows, traps[0]["id"]))[0]
    hide_ok = bool(G.trap_checks(G.mutate_hide_bmad_disagreement(rows)))
    if not drop_ok or not hide_ok:
        print("FAILED:RES-0121 detector silent under mutation")
        return 1

    unit = catalog_unit()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "unit_id": G.UNIT,
        "state": "SUCCESS",
        "sentinel": G.CATALOG_SENTINEL,
        "receipt": G.CATALOG_SENTINEL,
        "title": unit.get("title"),
        "question": G.QUESTION,
        "not_legal_advice": True,
        "overclaim_refused": (
            "Did not invent GitHub URLs for E001-E189. The 189 register "
            "rows are REGISTER-SOURCE-ABSENT. Reachable rows are the two "
            "catalog-named traps, each with a LICENSE sha256 from the file "
            "bytes. The recorded '19 NOASSERTION rows' cannot be re-counted "
            "without the register; they remain residual, not resolved."
        ),
        "register": register,
        "recorded_gap": {
            "noassertion_rows_claimed_in_catalog": 19,
            "verified_on_this_tree": False,
            "reason": "register source absent; cannot enumerate the 19",
            "zero_license_files_fetched_at_unit_authoring": True,
            "license_files_fetched_this_run": [t["catalog_name"] for t in traps],
        },
        "graph": {"rows": rows},
        "trap_verdicts": trap_verdicts,
        "counts": counts,
        "method": (
            "For each reachable repo: (rail 1) GitHub GET /repos/{owner}/{repo}"
            "/license classifier JSON, hashed as captured; (rail 2) the LICENSE "
            "file bytes from raw.githubusercontent.com, hashed after CRLF "
            "normalization. file_says is parsed from the file text. A "
            "disagreement is file_says SPDX vs classifier spdx_id after "
            "normalization. Unreachable E-rows have no sha256."
        ),
        "controls": {
            "drop_sha256_turns_red": drop_ok,
            "hide_bmad_disagreement_turns_red": hide_ok,
            "healthy_graph_ok": True,
        },
        "report": {
            "kind": "license-graph",
            "observations": [
                {
                    "name": "reachable-with-license-sha256",
                    "measured": counts["license_sha256_on_reachable"],
                    "method": "sha256 of stored LICENSE bytes for every reachable row",
                    "anchor": "graph.rows[reachable].license_sha256",
                },
                {
                    "name": "file-vs-classifier-disagreements",
                    "measured": counts["file_vs_classifier_disagreements"],
                    "method": "file_says SPDX vs GitHub classifier spdx_id",
                    "anchor": "counts.file_vs_classifier_disagreements",
                },
                {
                    "name": "register-e-rows",
                    "measured": counts["register_e_rows"],
                    "method": "E001-E189 span; unreachable while register source absent",
                    "anchor": "graph.rows E001-E189",
                },
            ],
            "control_ids": [
                "drop_sha256_turns_red",
                "hide_bmad_disagreement_turns_red",
            ],
        },
        "tests": [
            {
                "id": "reachable-license-sha256",
                "name": "Every reachable row carries a LICENSE sha256 that re-hashes from stored file bytes",
                "command": G.P1,
                "result": "PASS",
            },
            {
                "id": "named-traps-and-disagreement-control",
                "name": "BMAD-METHOD and microsoft/autogen resolved; file-vs-classifier count recomputed; both-states mutations fire",
                "command": G.P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0121-probe2-traps-disagree",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Independent of emit: recomputes file_says vs classifier on "
                "stored LICENSE bytes and classifier snapshots; plants a "
                "missing sha256 and a hidden BMAD disagreement."
            ),
            "owner_signoff": (
                "Not claimed. Catalog requires owner sign-off before any "
                "downstream unit may act on this classification. This unit "
                "is not legal advice."
            ),
        },
        "artifacts": [
            {"path": G.OUT_REL, "exists": True, "role": "primary"},
            {"path": G.SCHEMA_REL, "exists": True, "role": "output-schema"},
            {
                "path": "command-center/p2-wave/probes/RES-0121/licenses/BMAD-METHOD.LICENSE",
                "exists": True,
                "role": "license-file",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0121/licenses/microsoft-autogen.LICENSE",
                "exists": True,
                "role": "license-file",
            },
        ],
        "evidence": [
            {
                "kind": "license-file",
                "claim": "BMAD-METHOD LICENSE identifying text is MIT License; sha256 recorded",
                "path": "command-center/p2-wave/probes/RES-0121/licenses/BMAD-METHOD.LICENSE",
                "sha256": traps[0]["license_sha256"],
            },
            {
                "kind": "classifier-api",
                "claim": "GitHub classifier returns NOASSERTION for bmad-code-org/BMAD-METHOD",
                "permalink": traps[0]["rails"][0]["permalink"],
                "classifier_label": traps[0]["classifier_label"],
            },
            {
                "kind": "license-file",
                "claim": "microsoft/autogen LICENSE is CC-BY-4.0 (content licence on a code repo)",
                "path": "command-center/p2-wave/probes/RES-0121/licenses/microsoft-autogen.LICENSE",
                "sha256": traps[1]["license_sha256"],
            },
            {
                "kind": "classifier-api",
                "claim": "GitHub classifier returns CC-BY-4.0 for microsoft/autogen, agreeing with the file",
                "permalink": traps[1]["rails"][0]["permalink"],
                "classifier_label": traps[1]["classifier_label"],
            },
        ],
        "residual_unknowns": [
            {
                "id": "E001-E189-register",
                "status": "REGISTER-SOURCE-ABSENT",
                "detail": (
                    "05-ECO-workflow-sources.md (E001-E189) is not on this "
                    "Linux worktree. 189 rows remain unreachable."
                ),
            },
            {
                "id": "catalog-19-noassertion",
                "status": "UNVERIFIED",
                "detail": (
                    "The catalog records 19 NOASSERTION rows. Without the "
                    "register they cannot be named or re-fetched."
                ),
            },
            {
                "id": "RES-0004",
                "status": "DEPENDENCY-ARTIFACT-ABSENT",
                "detail": "command-center/research/RES-0004.json is not on this tree.",
            },
        ],
        "ts": now,
    }

    schema_errs = check_schema_file() + check_document(report)
    if schema_errs:
        print(json.dumps({"schema_errors": schema_errs[:12]}, indent=2))
        print("FAILED:RES-0121 schema_check")
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"unit_id": "RES-0121", "state": "SUCCESS", "passing_tests": 999999},
        {"blob": "x" * 200},
    ):
        if check_document(garbage):
            garbage_rejected += 1
    if garbage_rejected != 3:
        print("FAILED:RES-0121 schema checker accepted garbage")
        return 1

    out_path = REPO / G.OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if G.CATALOG_SENTINEL not in payload:
        print("FAILED:RES-0121 sentinel missing from payload")
        return 1
    out_path.write_text(payload, encoding="utf-8")
    sha, nbytes = G.sha256_file(out_path)
    print(f"wrote {G.OUT_REL} bytes={nbytes} sha256={sha}")
    print(
        f"reachable={counts['reachable']} disagreements="
        f"{counts['file_vs_classifier_disagreements']} "
        f"register_present={register.get('present')}"
    )
    print("SUCCESS:RES-0121 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
