#!/usr/bin/env python3
"""Build ARC-0007 fixtures, run the merge procedure, emit MIGRATION.json."""
from __future__ import annotations

import hashlib
import json
import os
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


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def pad_live(extra_bytes: int, tag: str) -> str:
    chunk = f"LIVE-ONLY {tag} policy line — do not drop on migrate.\n"
    body = ""
    n = 0
    while len(body.encode("utf-8")) < extra_bytes:
        n += 1
        body += f"{chunk.strip()} #{n}\n"
    return body


def wipe(path: Path) -> None:
    if not path.exists():
        return
    for p in sorted(path.rglob("*"), reverse=True):
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            try:
                p.rmdir()
            except OSError:
                pass


def build_trees() -> dict[str, str]:
    wipe(FIX)
    FIX.mkdir(parents=True, exist_ok=True)

    shared_auth = (
        "# Owner ops authorization\n"
        "H1. Do not mutate git history.\n"
        "H2. Do not print secrets.\n"
        "H3. Fail closed on missing evidence.\n"
    )
    write(
        REPO_ROOT / "rules/common/owner-ops-authorization.md",
        shared_auth + "REPO: reconstructed from catalog pin; live copy is larger.\n",
    )
    write(
        LIVE_ROOT / "rules/common/owner-ops-authorization.md",
        shared_auth
        + "LIVE: additional hard bans observed as live-ahead.\n"
        + pad_live(1001, "owner-ops-authorization"),
    )

    shared_perf = "# Performance\nPrefer incremental scans.\nAvoid full-tree reread on each probe.\n"
    write(REPO_ROOT / "rules/common/performance.md", shared_perf)
    write(LIVE_ROOT / "rules/common/performance.md", shared_perf + pad_live(178, "performance"))

    shared_sec = "# Security\nNo wildcard tool grants.\nRe-validate declarations after edit.\n"
    write(REPO_ROOT / "rules/common/security.md", shared_sec)
    write(LIVE_ROOT / "rules/common/security.md", shared_sec + pad_live(97, "security"))

    write(
        REPO_ROOT / "rules/common/agents.md",
        "# Agents\nShared agent contract.\nREPO-ONLY: squash-merge detector pin = 2.\n"
        + ("REPO extra agents context.\n" * 12),
    )
    write(LIVE_ROOT / "rules/common/agents.md", "# Agents\nShared agent contract.\n")

    write(
        REPO_ROOT / "rules/common/hooks.md",
        "# Hooks\nDispatch through hooks/_dispatch/manifest.json only.\n"
        + ("REPO hook inventory line.\n" * 20),
    )
    write(
        LIVE_ROOT / "rules/common/hooks.md",
        "# Hooks\nDispatch through hooks/_dispatch/manifest.json only.\n",
    )

    write(
        REPO_ROOT / "rules/common/ci-hygiene.md",
        "# CI hygiene\nRequire both-states controls.\nREPO-ONLY: fail on stub sentinels.\n"
        + ("x" * 80 + "\n") * 4,
    )
    write(LIVE_ROOT / "rules/common/ci-hygiene.md", "# CI hygiene\nRequire both-states controls.\n")

    write(
        REPO_ROOT / "rules/common/windows-shell.md",
        "# Windows shell\nDrive-qualified paths appear here.\nREPO-ONLY: squash-merge mention count=2.\n",
    )
    write(
        LIVE_ROOT / "rules/common/windows-shell.md",
        "# Windows shell\nDrive-qualified paths appear here.\n",
    )

    write(REPO_ROOT / "skills/repo-tree/skill-alpha.md", "# skill-alpha\nIdentical on both sides.\n")
    write(LIVE_ROOT / "skills/repo-tree/skill-alpha.md", "# skill-alpha\nIdentical on both sides.\n")

    write(
        REPO_ROOT / "skills/repo-tree/skill-beta.md",
        "# skill-beta\nShared intro.\nREPO-ONLY unique capability line: workflow-blueprint-96.\n",
    )
    write(
        LIVE_ROOT / "skills/repo-tree/skill-beta.md",
        "# skill-beta\nShared intro.\nLIVE-ONLY unique capability line: council-preset-64.\n",
    )

    write(
        REPO_ROOT / "hooks/_dispatch/manifest.json",
        json.dumps({"hooks": ["pre-tool", "post-tool"], "mounts": ["fs"]}, indent=2) + "\n",
    )
    write(
        LIVE_ROOT / "hooks/_dispatch/manifest.json",
        json.dumps(
            {
                "hooks": ["pre-tool", "post-tool", "session-start"],
                "mounts": ["fs", "mcp-extra"],
            },
            indent=2,
        )
        + "\n",
    )

    ledger = {
        "rules/common/owner-ops-authorization.md": "2026-07-11T15:02:00Z",
        "rules/common/performance.md": "2026-07-18T09:41:00Z",
        "rules/common/security.md": "2026-07-20T11:08:00Z",
        "rules/common/agents.md": "2026-08-02T08:15:00Z",
        "rules/common/hooks.md": "2026-08-02T08:16:00Z",
        "rules/common/ci-hygiene.md": "2026-08-05T19:22:00Z",
        "rules/common/windows-shell.md": "2026-08-06T04:03:00Z",
        "skills/repo-tree/skill-alpha.md": "2026-06-01T12:00:00Z",
        "skills/repo-tree/skill-beta.md": "2026-06-12T12:00:00Z",
        "hooks/_dispatch/manifest.json": "2026-07-01T00:00:00Z",
    }
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")

    live_base = datetime(2026, 8, 9, 16, 0, 0, tzinfo=timezone.utc).timestamp()
    repo_base = datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc).timestamp()
    for i, rel in enumerate(SAMPLE):
        os.utime(LIVE_ROOT / rel, (live_base + i * 3600, live_base + i * 3600))
        os.utime(REPO_ROOT / rel, (repo_base + i * 3600, repo_base + i * 3600))
    return ledger


def validate_or_die(doc: dict) -> None:
    import jsonschema

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:ARC-0007 schema accepts garbage")


def fixtures_present() -> bool:
    if not LEDGER_PATH.is_file():
        return False
    return all((REPO_ROOT / rel).is_file() and (LIVE_ROOT / rel).is_file() for rel in SAMPLE)


def main() -> int:
    # Resume: never wipe an existing 10-file sample. build_trees() is only for a
    # missing fixtures/ tree. Downstream units (TST-0256) copy these bytes.
    if fixtures_present():
        ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
        if not SNAP_ROOT.is_dir() or not any(SNAP_ROOT.rglob("*")):
            P.snapshot_tree(REPO_ROOT, SNAP_ROOT)
    else:
        ledger = build_trees()
        P.snapshot_tree(REPO_ROOT, SNAP_ROOT)
        wipe(MIG_ROOT)
    MIG_ROOT.mkdir(parents=True, exist_ok=True)

    records = [
        P.measure_file(rel, REPO_ROOT, LIVE_ROOT, ledger, MIG_ROOT) for rel in SAMPLE
    ]
    sample_rows = []
    queue = []
    failed_preserve = []
    live_larger_n = 0
    git_ok = False
    for rec in records:
        d = P.record_to_dict(rec)
        sample_rows.append(
            {
                "path": d["path"],
                "target_path": d["target_path"],
                "classification": d["classification"],
                "decision": d["decision"],
                "repo_exists": d["repo_exists"],
                "live_exists": d["live_exists"],
                "repo_bytes": d["repo_bytes"],
                "live_bytes": d["live_bytes"],
                "live_larger": d["live_larger"],
                "repo_sha256": d["repo_sha256"],
                "live_sha256": d["live_sha256"],
                "signal1_git_log_cI": d["signal1_git_log_cI"],
                "signal2_live_mtime_plus_diff": d["signal2_live_mtime_plus_diff"],
                "unique_lines_preserved": d["unique_lines_preserved"],
                "migrated_sha256": d["migrated_sha256"],
                "refused_overwrite": d["refused_overwrite"],
                "reason": d["reason"],
            }
        )
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
        return 1
    if failed_preserve:
        print("FAILED:ARC-0007 content preservation failed:", failed_preserve)
        return 1
    if live_larger_n < 1:
        print("FAILED:ARC-0007 sample missing live-larger file")
        return 1
    have = {r.path for r in records}
    for must in P.LIVE_LARGER_NAMES:
        if must not in have:
            print("FAILED:ARC-0007 missing pinned live-larger path", must)
            return 1

    named = [r.path for r in records if r.live_larger]
    estate_live = Path("/root/.claude").is_dir()
    estate_rules = (REPO / "rules").is_dir()

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "migration-plan",
        "title": "Content-preserving migration into the config-first layout",
        "question": (
            "Design the migration from today's de-facto layout (repo rules/, live rules, "
            "two skills trees, hooks/_dispatch/manifest.json) into the config-first layout "
            "WITHOUT destroying content, given that the divergence is two-directional."
        ),
        "sentinel": "SUCCESS:ARC-0007 content-preserving procedure proved on a 10-file sample",
        "source_layout": {
            "roots": [
                "rules/ (repo)",
                "rules/ (live)",
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
                "Signal 1 is git log -1 --format=%cI on the repo path. Signal 2 is live "
                "mtime plus the LF-normalised line diff. Classification is by line-set "
                "inclusion, not by which clock is newer. A unique line on either side "
                "forbids taking the other side as a one-directional overwrite."
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
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "notes": (
                "Catalog asks an independent reviewer to confirm both-direction preservation "
                "before scoring. This implement worker did not delegate that review and "
                "does not self-certify it."
            ),
        },
        "cloud_ok": False,
        "registered": False,
    }

    validate_or_die(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size} live_larger={live_larger_n} queue={len(queue)}")
    print("SUCCESS:ARC-0007-build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
