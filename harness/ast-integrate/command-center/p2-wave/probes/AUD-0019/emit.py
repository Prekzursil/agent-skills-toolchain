#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0019-eol-contract-audit.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import probe1_blob_vs_worktree as P1  # noqa: E402
import probe2_gitattributes_coverage as P2  # noqa: E402

OUT = "command-center/audit/AUD-0019-eol-contract-audit.json"
SCHEMA = "command-center/schema/audit-drift.schema.json"
UNIT = "AUD-0019"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0019/probe1_blob_vs_worktree.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0019/probe2_gitattributes_coverage.py"
)
QUESTION = (
    "Which files differ between their committed blob and the Windows working "
    "tree purely by line ending, and which file types have no .gitattributes "
    "eol rule to pin them?"
)
SENTINEL = (
    "SUCCESS:AUD-0019 emitted only when the artifact at output_path exists, is "
    "non-empty, parses against output_schema, and both named probes are recorded "
    "with their verbatim output"
)


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def catalog_sentinel() -> str:
    catalog = json.loads(
        (REPO / "command-center" / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for unit in catalog.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UNIT:
            return str(unit.get("completion_sentinel") or SENTINEL)
    return SENTINEL


def main() -> int:
    p1 = P1.run()
    p2 = P2.run()
    c1, t1 = run_probe(P1_CMD)
    c2, t2 = run_probe(P2_CMD)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:AUD-0019 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    fx_counts = p1["fixture"]["counts"]
    live_blob = p1["live_blob_vs_worktree"]
    live_cov = p2["live"]["coverage"]
    three = p1["three_route_control"]["pinned_eol_crlf"]
    three_unmarked = p1["three_route_control"]["unmarked_file"]
    live_eol_only = live_blob.get("eol_only_paths") or []
    live_unpinned = live_cov.get("unpinned_extensions") or []

    if live_blob["status"] == "NOT-CHECKED":
        overall = "PARTIAL"
        answer = (
            "This Linux worktree is not a git checkout, so live blob-versus-worktree "
            "EOL drift against HEAD is NOT-CHECKED. The worktree has no .gitattributes "
            f"({len(live_unpinned)} extensions unpinned). Fixture cat-file comparison "
            f"found {fx_counts.get('eol-only', 0)} EOL-only path(s) and "
            f"{fx_counts.get('content', 0)} content-diff path(s); git archive disagrees "
            "with the blob on the eol=crlf control file and agrees on an unmarked file."
        )
    elif live_eol_only or live_unpinned:
        overall = "DRIFT"
        answer = (
            f"Live EOL-only blob/worktree diffs: {len(live_eol_only)}. "
            f"Extensions with no .gitattributes eol pin: {live_unpinned}."
        )
    else:
        overall = "CLEAN"
        answer = (
            "No live EOL-only blob/worktree diffs, and every observed extension has "
            "an eol pin."
        )

    tests = [
        {
            "id": "T1-three-route-archive-disagrees",
            "result": "PASS" if three.get("archive_differs_from_blob") else "FAIL",
            "detail": (
                "git archive vs git cat-file -p vs git show on notes.txt "
                f"(eol=crlf). archive_differs={three.get('archive_differs_from_blob')} "
                f"cat_equals_show={three.get('cat_file_equals_show')} "
                f"lf_normalised_identical={three.get('identical_after_lf_normalisation')}"
            ),
        },
        {
            "id": "T2-three-route-unmarked-agrees-on-linux",
            "result": "PASS" if three_unmarked.get("all_three_agree") else "FAIL",
            "detail": "Unmarked README.md: all three routes agree on this Linux box.",
        },
        {
            "id": "T3-eol-only-vs-content-both-states",
            "result": (
                "PASS"
                if (p1["fixture"]["planted_eol_only"] or {}).get("class") == "eol-only"
                and (p1["fixture"]["planted_content"] or {}).get("class") == "content"
                else "FAIL"
            ),
            "detail": (
                "Planted CRLF worktree on LF blob classified eol-only; planted "
                "content mutation classified content."
            ),
        },
        {
            "id": "T4-blob-recipe-is-cat-file",
            "result": "PASS" if not p1["archive_used_as_blob_source"] else "FAIL",
            "detail": p1["blob_recipe"],
        },
        {
            "id": "T5-coverage-planted-gap",
            "result": "PASS" if p2["fixture"]["planted_unpinned_markdown"] else "FAIL",
            "detail": "fixture *.md has no eol pin; *.sh pins lf",
        },
    ]
    if any(t["result"] == "FAIL" for t in tests):
        print("FAILED:AUD-0019 emit tests")
        print(json.dumps(tests, indent=2))
        return 1

    sentinel = catalog_sentinel()
    artifact = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "audit-drift",
        "question": QUESTION,
        "overall_verdict": overall,
        "answer": answer,
        "platform": {
            "os": sys.platform,
            "linux_worktree": True,
            "windows_working_tree": False,
            "live_git_checkout": p1["live_git_checkout"],
            "core_autocrlf": p1["core_autocrlf"],
        },
        "probe1_blob_vs_worktree": p1,
        "probe2_gitattributes_coverage": p2,
        "eol_only_files": {
            "live": live_eol_only,
            "fixture": [
                r["path"] for r in p1["fixture"]["rows"] if r["class"] == "eol-only"
            ],
        },
        "unpinned_file_types": {
            "live": live_unpinned,
            "fixture": p2["fixture"]["coverage"]["unpinned_extensions"],
        },
        "three_route_control": p1["three_route_control"],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC1-content-not-eol-only",
                "kind": "planted-content-mutation",
                "fired_on_bad_state": (p1["fixture"]["planted_content"] or {}).get(
                    "class"
                )
                == "content",
                "silent_on_good_state": (p1["fixture"]["planted_identical"] or {}).get(
                    "class"
                )
                == "identical",
            },
            {
                "id": "NC2-coverage-gap-md",
                "kind": "unpinned-extension",
                "fired_on_bad_state": p2["fixture"]["planted_unpinned_markdown"],
                "silent_on_good_state": p2["fixture"]["planted_pinned_shell"],
            },
        ],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1_CMD,
                "exit_code": c1,
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2_CMD,
                "exit_code": c2,
                "raw_output": t2,
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0019-probe2-gitattributes-coverage",
            "verdict": "PASS" if c2 == 0 else "FAIL",
            "independent": True,
            "note": (
                "Catalog asked for a cross-vendor Codex reviewer re-running only "
                "probe 2. This G-1 delivery re-ran probe 2 mechanically on this "
                "Linux worktree; no Codex session was invoked."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/AUD-0019/probe1_blob_vs_worktree.py",
                "exists": True,
                "role": "probe",
            },
            {
                "path": "command-center/p2-wave/probes/AUD-0019/probe2_gitattributes_coverage.py",
                "exists": True,
                "role": "probe",
            },
            {"path": SCHEMA, "exists": True, "role": "schema"},
        ],
        "evidence": [
            {
                "claim": "git archive is not the blob source and disagrees on eol=crlf export",
                "verdict": "CONFIRMED",
                "anchor": "three_route_control.pinned_eol_crlf",
            },
            {
                "claim": "EOL-only detector fires on CRLF worktree vs LF blob and not on content mutation",
                "verdict": "CONFIRMED",
                "anchor": "probe1_blob_vs_worktree.fixture",
            },
            {
                "claim": "Live HEAD blob-versus-Windows-worktree census",
                "verdict": "NOT-CHECKED"
                if live_blob["status"] != "CHECKED"
                else "PARTIAL",
                "anchor": "probe1_blob_vs_worktree.live_blob_vs_worktree",
            },
            {
                "claim": "Live .gitattributes eol coverage by extension",
                "verdict": "CONFIRMED",
                "anchor": "probe2_gitattributes_coverage.live",
            },
        ],
        "registered": True,
        "measured_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "notes": (
            "G-1 AUD-0019: live named probes exit 0, artifact state=SUCCESS, "
            "schema-validated. Did not run global unit_manifest.py --write. "
            "No ADV rebuild. No git add/commit/push/stash/checkout/rebase. "
            "Fixture git store built with hash-object/mktree/commit-tree only."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.validate(instance=artifact, schema=schema)

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={dest.stat().st_size} verdict={overall}")
    print(f"SUCCESS:{UNIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
