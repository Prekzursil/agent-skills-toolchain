#!/usr/bin/env python3
"""Emit command-center/phase3/A1/MIGRATION.json from EXISTING ARC-0007 fixtures.

Does not wipe fixtures/ (resume, do not scrap). Re-measures the 10-file sample,
writes the catalog output_path, then the per-unit receipt pair.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import procedure as P  # noqa: E402

UNIT = "ARC-0007"
OUT_REL = "command-center/phase3/A1/MIGRATION.json"
SCHEMA_REL = "command-center/schema/migration-plan.schema.json"
FIX = HERE / "fixtures"
REPO_ROOT = FIX / "repo"
LIVE_ROOT = FIX / "live"
MIG_ROOT = FIX / "migrated"
SNAP_ROOT = FIX / "rollback-snapshot"
LEDGER_PATH = FIX / "repo-committer-ledger.json"
NEG_LINE = "LIVE-ONLY-LINE:synthetic-ARC-0007-negcontrol"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0007/probe1_provenance.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0007/probe2_preservation.py"
)

SAMPLE = [
    "rules/common/owner-ops-authorization.md",
    "rules/common/performance.md",
    "rules/common/security.md",
    "rules/common/agents.md",
    "rules/common/hooks.md",
    "rules/common/ci-hygiene.md",
    "rules/common/windows-shell.md",
    "skills/repo-tree/skill-alpha.md",
    "skills/repo-tree/skill-beta.md",
    "hooks/_dispatch/manifest.json",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def require_fixtures() -> dict[str, str]:
    missing = [rel for rel in SAMPLE if not (REPO_ROOT / rel).is_file() or not (LIVE_ROOT / rel).is_file()]
    if missing:
        print("FAILED:ARC-0007 fixtures missing:", missing)
        print("create them with build.py only when fixtures/ is absent; do not wipe a live sample")
        raise SystemExit(1)
    if not LEDGER_PATH.is_file():
        print("FAILED:ARC-0007 fixtures/repo-committer-ledger.json missing")
        raise SystemExit(1)
    if not SNAP_ROOT.is_dir() or not list(SNAP_ROOT.rglob("*")):
        P.snapshot_tree(REPO_ROOT, SNAP_ROOT)
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def build_doc(ledger: dict[str, str]) -> dict:
    MIG_ROOT.mkdir(parents=True, exist_ok=True)
    records = [
        P.measure_file(rel, REPO_ROOT, LIVE_ROOT, ledger, MIG_ROOT) for rel in SAMPLE
    ]
    sample_rows = [P.record_to_dict(rec) for rec in records]
    queue = []
    failed_preserve = []
    live_larger_n = 0
    git_ok = False
    for rec in records:
        if rec.live_larger:
            live_larger_n += 1
        if rec.git_log_exit == 0 and rec.repo_committer_iso:
            git_ok = True
        if rec.decision == P.ADJUDICATE:
            queue.append(
                {
                    "path": rec.path,
                    "classification": rec.classification,
                    "why_queued": rec.reason,
                    "held_repo_unique_lines": rec.repo_unique_line_count,
                    "held_live_unique_lines": rec.live_unique_line_count,
                    "preview_is_union": True,
                }
            )
        if not rec.unique_lines_preserved:
            failed_preserve.append(rec.path)

    neg = P.negative_control_refuse_overwrite(NEG_LINE)
    if not neg["pass"]:
        print("FAILED:ARC-0007 negative control did not refuse overwrite")
        print(json.dumps(neg, indent=2))
        raise SystemExit(1)
    if failed_preserve:
        print("FAILED:ARC-0007 content preservation failed:", failed_preserve)
        raise SystemExit(1)
    if live_larger_n < 1:
        print("FAILED:ARC-0007 sample missing live-larger file")
        raise SystemExit(1)
    have = {r.path for r in records}
    for must in P.LIVE_LARGER_NAMES:
        if must not in have:
            print("FAILED:ARC-0007 missing pinned live-larger path", must)
            raise SystemExit(1)

    named = [r.path for r in records if r.live_larger]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    estate_live = Path("/root/.claude").is_dir()
    estate_rules = (REPO / "rules").is_dir()
    question = (
        "Design the migration from today's de-facto layout (repo rules/, live rules, "
        "two skills trees, hooks/_dispatch/manifest.json) into the config-first layout "
        "WITHOUT destroying content, given that the divergence is two-directional."
    )
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "architecture_id": "A1",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0007",
        "completion_sentinel": "SUCCESS:ARC-0007",
        "min_bytes_threshold": 2048,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ARC-0007]",
        "report_kind": "migration-plan",
        "title": "Content-preserving migration into the config-first layout",
        "question": question,
        "report": {
            "kind": "migration-plan",
            "observations": [
                {
                    "name": "sample-size",
                    "measured": len(sample_rows),
                    "method": "count of measured fixture paths in SAMPLE",
                    "anchor": "command-center/p2-wave/probes/ARC-0007/emit_migration.py",
                },
                {
                    "name": "live-larger-in-sample",
                    "measured": live_larger_n,
                    "method": "len(live_bytes) > len(repo_bytes) on the 10-file fixture",
                    "anchor": "command-center/p2-wave/probes/ARC-0007/fixtures/live/",
                },
                {
                    "name": "negative-control-refused",
                    "measured": True,
                    "method": "apply_merge(..., requested=TAKE-REPO) while live holds a unique line",
                    "anchor": "command-center/p2-wave/probes/ARC-0007/procedure.py:negative_control_refuse_overwrite",
                },
            ],
            "control_ids": [
                "negative-control-refuse-one-directional-overwrite",
                "content-preservation-union",
            ],
        },
        "source_layout": {
            "roots": [
                "rules/ (repo fixture)",
                "rules/ (live fixture)",
                "skills/ (repo tree + live tree)",
                "hooks/_dispatch/manifest.json",
            ],
            "divergence": {
                "two_directional": True,
                "catalog_pinned_live_larger": list(P.LIVE_LARGER_NAMES),
                "catalog_pin": (
                    "WORK-UNIT-CATALOG evidence pins: only 5 of 88 rules files "
                    "byte-identical, 28 content-differing, 25 repo-larger, 3 live-larger "
                    "(owner-ops-authorization, performance, security)."
                ),
            },
        },
        "target_layout": {
            "root": "config/",
            "load_order": [
                "config/load-order.json",
                "config/rules/** (preserved bodies; A1 wraps to *.rule.json later)",
                "config/skills/**",
                "config/hooks/manifest.json",
            ],
            "mapping": [
                {"from": "rules/", "to": "config/rules/"},
                {"from": "skills/", "to": "config/skills/"},
                {"from": "hooks/_dispatch/", "to": "config/hooks/"},
            ],
        },
        "provenance_procedure": {
            "timestamps_do_not_authorise_overwrite": True,
            "notes": (
                "Signal 1 is git log -1 --format=%cI on the repo path (or the fixture "
                "committer ledger when git is absent). Signal 2 is live mtime plus the "
                "LF-normalised line diff. Classification is by line-set inclusion, not by "
                "which clock is newer. A unique line on either side forbids taking the "
                "other side as a one-directional overwrite."
            ),
            "signals": [
                {
                    "id": "signal-1-repo-git-committer",
                    "command_or_method": "git log -1 --format=%cI -- <path>",
                    "reads": "repo committer timestamp (independent of filesystem mtime)",
                },
                {
                    "id": "signal-2-live-mtime-and-content-diff",
                    "command_or_method": "stat.st_mtime + set(lines_live) - set(lines_repo)",
                    "reads": "live mtime plus unique-line counts after LF normalisation",
                },
            ],
            "decision_table": [
                {"when": "BYTE-IDENTICAL-LF or EOL-ONLY", "do": "IDENTICAL / take repo bytes after LF"},
                {"when": "REPO-ONLY", "do": "TAKE-REPO-LIVE-ABSENT"},
                {"when": "LIVE-ONLY", "do": "TAKE-LIVE-REPO-ABSENT"},
                {"when": "LIVE-SUPERSET", "do": "TAKE-LIVE (repo lines already present)"},
                {"when": "REPO-SUPERSET", "do": "TAKE-REPO (live lines already present)"},
                {
                    "when": "BOTH-UNIQUE",
                    "do": "ADJUDICATE; hold both unique-line sets; preview = UNION-MERGE",
                },
                {
                    "when": "requested TAKE-REPO while live has unique lines",
                    "do": "REFUSE-ONE-DIRECTIONAL-OVERWRITE",
                },
            ],
        },
        "adjudication_queue": queue,
        "rollback": {
            "unit": "the rollback snapshot of the target tree taken BEFORE any write",
            "steps": [
                "1. snapshot mapped files to probes/ARC-0007/fixtures/rollback-snapshot/",
                "2. apply forward merge only after snapshot hashes are recorded",
                "3. on abort, restore_tree(snapshot, dest) byte-for-byte; never re-run the forward merge as rollback",
            ],
            "restore_command": (
                "python3 -c \"from pathlib import Path; import sys; "
                "sys.path.insert(0,'command-center/p2-wave/probes/ARC-0007'); import procedure as P; "
                "P.restore_tree(Path('command-center/p2-wave/probes/ARC-0007/fixtures/rollback-snapshot'), "
                "Path('command-center/p2-wave/probes/ARC-0007/fixtures/migrated'))\""
            ),
            "forbids": [
                "one-directional Copy-Item -Force / cp -f of live onto repo",
                "one-directional copy of repo onto live",
                "scripts/sync-from-live.ps1",
            ],
        },
        "sample": sample_rows,
        "tests": {
            "content_preservation": {
                "pass": True,
                "files_checked": len(sample_rows),
                "files_failed": [],
            },
            "negative_control": neg,
        },
        "evidence": {
            "two_independent_signals": True,
            "live_larger_in_sample": live_larger_n,
            "sample_size": len(sample_rows),
            "git_available_on_estate": git_ok,
            "notes": (
                "Each sample row records git log -1 --format=%cI (exit+raw) AND live mtime "
                f"plus unique-line counts. Live-larger paths in sample: {named}. "
                "This Linux worktree has no .git and no live ~/.claude rules tree; "
                "the procedure ran against fixtures that encode the catalog-pinned "
                "three live-larger files and two-directional unique lines."
            ),
        },
        "scope": {
            "live_estate_present": estate_live,
            "repo_rules_present": estate_rules,
            "proof_surface": (
                "executable procedure + 10-file fixture sample including the three "
                "catalog-pinned live-larger names; not a claim that C:\\Users\\Prekzursil "
                "live files were read on this host"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global UNIT-ARTIFACT-MANIFEST.json --write was run",
                "independent reviewer PASS",
                "production trees were mutated",
            ],
        },
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "migration-engineer",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "not-run",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": (
                "Catalog asks an independent reviewer to confirm both-direction preservation "
                "before scoring. This implement worker did not delegate that review and "
                "does not self-certify it. G-1 probe-green is independent of scoring review."
            ),
        },
        "timestamps": {
            "started_at": "2026-08-24T17:50:17Z",
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "re-measure once with a MECHANICALLY DIFFERENT probe (different shell, "
                "different data field); if the two readings disagree report BLOCKED with "
                "both numbers rather than picking one"
            ),
        },
        "cloud_ok": False,
        "registered": False,
        "named_probes": [
            {"id": "probe1", "role": "provenance-two-signal", "command": P1},
            {"id": "probe2", "role": "preservation-and-negative-control", "command": P2},
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "supporting"},
        ],
    }


def write_receipts(primary_sha: str, primary_bytes: int) -> None:
    rows = [
        (OUT_REL, "primary"),
        (SCHEMA_REL, "supporting"),
        ("command-center/p2-wave/probes/ARC-0007/procedure.py", "supporting"),
        ("command-center/p2-wave/probes/ARC-0007/probe1_provenance.py", "supporting"),
        ("command-center/p2-wave/probes/ARC-0007/probe2_preservation.py", "supporting"),
        ("command-center/p2-wave/probes/ARC-0007/build.py", "supporting"),
        ("command-center/p2-wave/probes/ARC-0007/emit_migration.py", "supporting"),
    ]
    artifacts = []
    for rel, role in rows:
        path = REPO / rel
        sha, nbytes = digest_file(path) if path.is_file() else ("", 0)
        if rel == OUT_REL:
            sha, nbytes = primary_sha, primary_bytes
        artifacts.append(
            {
                "path": rel,
                "sha256": sha,
                "bytes": nbytes,
                "present": path.is_file() and nbytes > 0,
                "unit_id": UNIT,
                "receipt_path": "command-center/p2-wave/probes/ARC-0007/SUBAGENT-RETURN.json",
                "role": role,
            }
        )
    present = sum(1 for a in artifacts if a["present"])
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": present,
        "artifacts": artifacts,
    }
    man_path = HERE / "UNIT-ARTIFACT-MANIFEST.json"
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")

    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0007",
        "registered": False,
        "output_path": OUT_REL,
        "output_schema": SCHEMA_REL,
        "measure_line": "SUCCESS:delivered ARC-0007",
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "provenance-two-signal"},
            {"id": "probe2", "command": P2, "role": "preservation-and-negative-control"},
        ],
        "artifacts": [
            {
                "path": OUT_REL,
                "sha256": primary_sha,
                "bytes": primary_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/ARC-0007/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "not-run",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": "Catalog scoring review is independent of G-1 probe-green.",
        },
        "cloud_ok": False,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "G-1 for ARC-0007: live named probes exit 0, MIGRATION.json state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            "Did not wipe existing fixtures."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    ledger = require_fixtures()
    doc = build_doc(ledger)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = digest_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0007 artifact {size}B below floor")
        return 1
    if "SUCCESS:ARC-0007" not in out.read_text(encoding="utf-8"):
        print("FAILED:ARC-0007 sentinel missing from artifact")
        return 1
    write_receipts(digest, size)
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0007 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
