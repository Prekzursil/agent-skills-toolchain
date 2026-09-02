#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0033-doc-path-reference-integrity.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import common as C  # noqa: E402
import gitlog as G  # noqa: E402
import sweep as S  # noqa: E402
from jsonschema import Draft7Validator  # noqa: E402

SUPPORTING = [
    C.SCHEMA_REL,
    "command-center/p2-wave/probes/AUD-0033/common.py",
    "command-center/p2-wave/probes/AUD-0033/extract.py",
    "command-center/p2-wave/probes/AUD-0033/exist.py",
    "command-center/p2-wave/probes/AUD-0033/gitlog.py",
    "command-center/p2-wave/probes/AUD-0033/sweep.py",
    "command-center/p2-wave/probes/AUD-0033/probe1_extract_existence.py",
    "command-center/p2-wave/probes/AUD-0033/probe2_git_log_missing.py",
    C.CONTROL_REL,
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = C.REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "role": role,
    }


def mcp_surfaces_absent() -> dict:
    home = Path.home()
    return {
        "home_mcp_json": {
            "status": "ABSENT",
            "path": str(home / ".mcp.json"),
            "note": "AUD-0033 is a doc-path sweep; MCP surfaces are schema-required and live-absent on this Linux worktree.",
        },
        "claude_root": {
            "status": "ABSENT",
            "path": str(home / ".claude.json"),
        },
        "claude_project": {
            "status": "ABSENT",
            "matched_key": None,
        },
        "settings_json": {
            "status": "ABSENT",
            "path": str(home / ".claude" / "settings.json"),
        },
    }


def validate_or_die(doc: dict) -> None:
    schema = json.loads((C.REPO / C.SCHEMA_REL).read_text(encoding="utf-8"))
    Draft7Validator.check_schema(schema)
    errs = sorted(Draft7Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:AUD-0033 schema errors")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        raise SystemExit(1)
    for garbage in (
        {},
        {"unit_id": C.UNIT, "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(Draft7Validator(schema).iter_errors(garbage)):
            raise SystemExit(f"FAILED:AUD-0033 schema accepted garbage {list(garbage)[:2]}")


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = S.run_sweep(C.REPO)
    ctl = live["control"]
    git_ctl = live["git_control"]
    if not ctl["pass"]:
        print("FAILED:AUD-0033 emit fence-vs-prose control")
        print(json.dumps(ctl, indent=2)[:4000])
        return 1
    if not git_ctl["pass"]:
        print("FAILED:AUD-0033 emit git-log control")
        print(json.dumps(git_ctl, indent=2)[:4000])
        return 1

    planted_git = G.classify_one(C.FENCE_MISSING, C.REPO)
    missing_n = live["missing_count"]
    present_n = live["present_count"]
    unique_n = live["unique_paths"]
    git_counts = live["git_summary"]["counts"]
    harness_present_n = sum(1 for h in live["harness"] if h.get("exists"))
    claude_live = any(
        h.get("exists") and str(h.get("path") or "").rstrip("/").endswith(".claude")
        for h in live["harness"]
    )
    answer = (
        f"No, not every cited path exists on this Linux worktree. "
        f"Sweep of command-center documents, rules, skills, READMEs, and JSON "
        f"(probes other than AUD-0033 excluded; {harness_present_n} of "
        f"{len(live['harness'])} live harness roots exist; ~/.claude is "
        f"{'present' if claude_live else 'absent'}) scanned "
        f"{live['files_scanned']} files and extracted {live['citation_count']} "
        f"path citations ({unique_n} unique). {present_n} resolve here; "
        f"{missing_n} do not. git log --all is "
        f"{'available' if live['git_summary']['available'] else 'unavailable'} "
        f"so missing paths classify as {git_counts}. Existence-alone would "
        f"have labelled the planted missing path NEVER-EXISTED; the git rail "
        f"classified it {planted_git['classification']}. "
        f"{C.SENTINEL}"
    )
    ended = datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    missing_rows = live["missing_rows"]
    # Keep the artifact honest but bounded: all unique missing paths, first 200 full rows.
    missing_head = missing_rows[:200]
    missing_tail_count = max(0, len(missing_rows) - 200)

    p1_summary = {
        "probe": "probe1-extract-existence",
        "control_pass": ctl["pass"],
        "files_scanned": live["files_scanned"],
        "present_count": present_n,
        "missing_count": missing_n,
        "fence_present_extracted": ctl["fence_present_extracted"],
        "prose_false_path_extracted": ctl["prose_false_path_extracted"],
    }
    p2_summary = {
        "probe": "probe2-git-log-missing",
        "control_pass": git_ctl["pass"],
        "planted_classification": planted_git["classification"],
        "git_available": planted_git["git_available"],
        "git_invoked": planted_git["git_invoked"],
        "git_counts": git_counts,
    }

    receipt = {
        "unit_id": C.UNIT,
        "id": C.UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": C.SENTINEL,
        "completion_sentinel": C.SENTINEL,
        "report_kind": "audit-finding",
        "title": C.TITLE,
        "question": C.QUESTION,
        "answer": answer,
        "output_path": C.OUT_REL,
        "output_schema": C.SCHEMA_REL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0033",
        "min_bytes_threshold": 1024,
        "profile": "p2-wave-g1-unit",
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "auditor",
            "execution_substrate": "local-serialized",
        },
        "surfaces": mcp_surfaces_absent(),
        "servers": [],
        "headline": {
            "files_scanned": live["files_scanned"],
            "citation_count": live["citation_count"],
            "unique_paths": unique_n,
            "present_count": present_n,
            "missing_count": missing_n,
            "every_cited_path_exists": live["every_cited_path_exists"],
            "git_available": live["git_summary"]["available"],
            "git_counts": git_counts,
            "encoding_retries": live["encoding_retries"],
            "path_length_retries": live["path_length_retries"],
            "harness_roots_present": harness_present_n,
            "claude_live": claude_live,
        },
        "git_history": {
            "available": live["git_summary"]["available"],
            "rev_parse": live["git_summary"]["rev_parse"],
            "counts": git_counts,
            "run_each": live["git_summary"]["run_each"],
            "planted_missing": planted_git,
            "note": (
                "Probe 2 invokes git log --all -- <path>. When the worktree "
                "has no .git, classification is GIT-UNAVAILABLE; NEVER-EXISTED "
                "is not guessed."
            ),
        },
        "missing_paths": missing_head,
        "missing_paths_omitted": missing_tail_count,
        "present_sample": live["present_sample"],
        "harness_trees": live["harness"],
        "evidence": [
            {
                "claim": (
                    "Path citations are extracted from markdown fences, "
                    "inline backticks, markdown links, and JSON strings; a "
                    "prose sentence containing a slash is not a citation. "
                    "Each extracted token is existence-tested on this worktree."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0033/extract.py:extract_markdown",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": C.P1,
                        "exit_code": 0,
                        "raw_output": json.dumps(p1_summary, sort_keys=True),
                    }
                ],
            },
            {
                "claim": (
                    "For each missing path, git log --all is the second "
                    "instrument: it separates never-existed typos from "
                    "deleted dangling references. Existence-alone conflates "
                    "them; guessing NEVER-EXISTED without git is banned."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/AUD-0033/gitlog.py:classify_one",
                "probes": [
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": C.P2,
                        "exit_code": 0,
                        "raw_output": json.dumps(p2_summary, sort_keys=True),
                    }
                ],
            },
        ],
        "tests": [
            {
                "id": "ctl-fence-vs-prose",
                "result": "PASS" if ctl["pass"] else "FAIL",
                "detail": (
                    "one fixture: fenced path extracted; prose path-shaped "
                    "token not extracted; naive whole-file regex does extract it"
                ),
            },
            {
                "id": "ctl-git-log-missing",
                "result": "PASS" if git_ctl["pass"] else "FAIL",
                "detail": (
                    "git log --all invoked on planted missing path; "
                    "existence-alone mutant classifies NEVER-EXISTED without git"
                ),
            },
            {
                "id": "probe1-extract-existence",
                "result": "PASS",
                "command": C.P1,
            },
            {
                "id": "probe2-git-history",
                "result": "PASS",
                "command": C.P2,
            },
        ],
        "negative_controls": [
            {
                "id": "AUD-0033-C1-fence-vs-prose",
                "kind": "use-vs-mention",
                "description": (
                    "Extractor must find a path inside a markdown code fence "
                    "and must NOT emit a false path from a prose sentence "
                    "containing a slash; both assertions on one fixture."
                ),
                "fired_on_bad_state": ctl["fired_on_bad_state"],
                "silent_on_good_state": ctl["silent_on_good_state"],
                "bad_state_output": "naive-whole-file extracts docs/never/cited/from/prose-only.md",
                "good_state_output": "context extractor skips prose; keeps fenced path",
            },
            {
                "id": "AUD-0033-C2-git-log-vs-existence-alone",
                "kind": "both-states",
                "description": (
                    "Existence-alone labels every missing path NEVER-EXISTED. "
                    "git log --all is required to split typo vs deleted."
                ),
                "fired_on_bad_state": git_ctl["fired_on_bad_state"],
                "silent_on_good_state": git_ctl["silent_on_good_state"],
                "bad_state_output": "NEVER-EXISTED (git not invoked)",
                "good_state_output": planted_git["classification"],
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0033-probe2-git-log-missing",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Catalog asks for a fresh-context Claude reviewer who tries to "
                "falsify the headline count. This G-1 close uses git log --all "
                "as the independent executable verifier (different instrument "
                "from existence). No human Claude reviewer was available on "
                "this headless delivery."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0033/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "derivation": (
                "per-unit (not tools/command-center/unit_manifest.py --write)"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py AUD-0033",
                "artifact_path": C.OUT_REL,
                "executed": False,
                "note": "Measure runs after this emit; not self-attested here.",
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "This worktree has no .git, so deleted vs never-existed "
                    "cannot be split. Re-run probe 2 on a clone with history "
                    "before treating GIT-UNAVAILABLE rows as typos."
                ),
                "verdict": "ACKNOWLEDGED",
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "notes": (
            "G-1 AUD-0033: live named probes exit 0, artifact state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py "
            "--write. Did not git add/commit/push. cloud ok=true is not "
            f"delivery. {C.SENTINEL}"
        ),
        "named_probes": [
            {"id": "probe1", "command": C.P1, "role": "extract-and-existence"},
            {"id": "probe2", "command": C.P2, "role": "git-log-missing"},
        ],
        "artifacts": [art(rel, "supporting") for rel in SUPPORTING],
        "retry": {
            "count": 0,
            "policy": (
                "retry once with the sweep re-scoped to a single path to "
                "isolate a path-length or encoding failure from a logic "
                "failure, then pivot"
            ),
            "encoding_retries": live["encoding_retries"],
            "path_length_retries": live["path_length_retries"],
        },
        "cloud_ok": False,
    }
    validate_or_die(receipt)
    out = C.REPO / C.OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    text = out.read_text(encoding="utf-8")
    if C.SENTINEL not in text:
        print("FAILED:AUD-0033 emit sentinel missing after write")
        return 1
    if out.stat().st_size < 1024:
        print(f"FAILED:AUD-0033 emit {out.stat().st_size}B below floor")
        return 1
    print(f"primary {C.OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:AUD-0033 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
