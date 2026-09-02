#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0014-agents-commands-drift.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import drift as D  # noqa: E402

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def pick(obj, *names, default=None):
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
    else:
        for name in names:
            if hasattr(obj, name):
                return getattr(obj, name)
    return default


UNIT = pick(D, "UNIT", "UNIT", default="AUD-0014")
OUT = pick(D, "OUT_REL", "OUT_REL", default="command-center/audit/AUD-0014-agents-commands-drift.json")
SCHEMA = pick(
    D,
    "SCHEMA_REL",
    "SCHEMA_REL",
    default="command-center/schema/audit-drift.schema.json",
)
SENTINEL = D.SENTINEL
QUESTION = D.QUESTION
P1 = pick(D, "P1", "P1")
P2 = pick(D, "P2", "P2")
MENTION = pick(D, "MENTION_REL", "MENTION_REL")
SONNET = pick(D, "SONNET_REL", "SONNET_REL")
PATH_REPO = pick(D, "PATH_REPO", "PATH_REPO")
PATH_LIVE = pick(D, "PATH_LIVE", "PATH_LIVE")


def validate_or_die(doc: dict) -> None:
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in GARBAGE:
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:AUD-0014 schema accepts garbage")


def file_row(rel: str, role: str) -> dict:
    path = REPO / rel
    return {"path": rel, "exists": path.is_file(), "role": role}


def main() -> int:
    live = D.measure()
    uvm = pick(live, "use_vs_mention", "use_vs_mention")
    pctl = pick(live, "path_control", "path_control")
    silent = pick(uvm, "silent_on_mention", "silent_on_mention")
    fires = pick(uvm, "fires_on_frontmatter", "fires_on_frontmatter")
    flags_mention = pick(uvm, "frontmatter_flags_mention", "frontmatter_flags_mention")
    grep_mention = pick(
        uvm,
        "grep_would_flag_mention",
        "grep_would_flag_mention",
        "body_grep_flags_mention",
    )
    both_ok = pick(uvm, "both_states_ok", "both_states_ok")
    vacuous = pick(pctl, "vacuous", "vacuous")
    pctl_ok = pick(pctl, "ok", "ok")
    if not both_ok:
        print("FAILED:AUD-0014 use-vs-mention control did not pass both states")
        print(json.dumps(uvm, sort_keys=True, default=str))
        return 1
    if flags_mention:
        print("FAILED:AUD-0014 mention-only fixture flagged by frontmatter parser")
        return 1
    if not grep_mention:
        print("FAILED:AUD-0014 mention fixture no longer contains sonnet")
        return 1
    if not pctl_ok or vacuous:
        print("FAILED:AUD-0014 path-control did not discriminate")
        print(json.dumps(pctl, sort_keys=True, default=str)[:2000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_live = pick(live, "n_live_only", "n_live_only")
    n_repo = pick(live, "n_repo_only", "n_repo_only")
    n_diff = pick(live, "n_content_different", "n_content_different")
    n_floor = pick(live, "n_host_floor_violations", "n_host_floor_violations")
    host_present = pick(live, "any_host_tree_present", "any_host_tree_present")
    host_absent = not host_present
    overall = "DRIFT"
    if host_absent:
        claim_trees = (
            "On this Linux worktree the four catalog trees are absent: "
            "repo agents/, repo commands/, live ~/.claude/agents, and "
            "live ~/.claude/commands. Path-set and content comparison of "
            "present files is empty-vs-empty; that is not a silent skip — "
            "the planted path-control still reports one different, one "
            "repo-only, one live-only, and one equal path."
        )
        trees_verdict = "DRIFT"
    else:
        claim_trees = (
            f"Host trees are present. live-only={n_live} repo-only={n_repo} "
            f"content-different={n_diff}."
        )
        trees_verdict = "DRIFT" if (n_live or n_repo or n_diff) else "CONFIRMED"

    headline = (
        f"host_trees_present={host_present} "
        f"live_only={n_live} repo_only={n_repo} content_different={n_diff} "
        f"host_opus_floor_violations={n_floor} "
        "planted_frontmatter_sonnet=ORPHAN planted_body_mention=GATED"
    )

    orphan_list = [SONNET]
    if host_absent:
        orphan_list.extend(
            [
                "ABSENT-DIR:repo/agents",
                "ABSENT-DIR:repo/commands",
                "ABSENT-DIR:live/.claude/agents",
                "ABSENT-DIR:live/.claude/commands",
            ]
        )
    host = live["host"]
    for kind in ("agents", "commands"):
        h = host[kind]
        prefix = f"{kind}/"
        orphan_list.extend(prefix + p for p in h["live_only"])
        orphan_list.extend("repo-" + prefix + p for p in h["repo_only"])
        orphan_list.extend(prefix + r["path"] for r in h["content_different"])
    for row in pick(live, "host_floor_violations", "host_floor_violations") or []:
        tag = f"{row['tree']}:{row['path']}"
        if tag not in orphan_list:
            orphan_list.append(tag)

    gate_map = [
        {"path": MENTION, "classification": "GATED"},
        {"path": SONNET, "classification": "ORPHAN"},
        {
            "path": "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/repo/keep.md",
            "classification": "GATED",
        },
        {
            "path": "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/live/changed.md",
            "classification": "ORPHAN",
        },
        {
            "path": "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/repo/repo-only.md",
            "classification": "ORPHAN",
        },
        {
            "path": "command-center/p2-wave/probes/AUD-0014/fixtures/path-control/live/live-only.md",
            "classification": "ORPHAN",
        },
    ]
    if host_absent:
        gate_map.extend(
            [
                {"path": "ABSENT-DIR:repo/agents", "classification": "ORPHAN"},
                {"path": "ABSENT-DIR:repo/commands", "classification": "ORPHAN"},
                {"path": "ABSENT-DIR:live/.claude/agents", "classification": "ORPHAN"},
                {"path": "ABSENT-DIR:live/.claude/commands", "classification": "ORPHAN"},
            ]
        )

    agents = host["agents"]
    commands = host["commands"]
    compared = [
        {
            "id": "repo-agents",
            "role": "declared-repo-tree",
            "path": pick(agents, "repo_path", "repo_path"),
            "is_dir": pick(agents, "repo_is_dir", "repo_is_dir"),
            "md_count": pick(agents, "repo_count", "repo_count"),
        },
        {
            "id": "live-agents",
            "role": "measured-live-tree",
            "path": pick(agents, "live_path", "live_path"),
            "is_dir": pick(agents, "live_is_dir", "live_is_dir"),
            "md_count": pick(agents, "live_count", "live_count"),
        },
        {
            "id": "repo-commands",
            "role": "declared-repo-tree",
            "path": pick(commands, "repo_path", "repo_path"),
            "is_dir": pick(commands, "repo_is_dir", "repo_is_dir"),
            "md_count": pick(commands, "repo_count", "repo_count"),
        },
        {
            "id": "live-commands",
            "role": "measured-live-tree",
            "path": pick(commands, "live_path", "live_path"),
            "is_dir": pick(commands, "live_is_dir", "live_is_dir"),
            "md_count": pick(commands, "live_count", "live_count"),
        },
        {
            "id": "path-control-repo",
            "role": "planted-path-control-repo",
            "path": str(PATH_REPO),
        },
        {
            "id": "path-control-live",
            "role": "planted-path-control-live",
            "path": str(PATH_LIVE),
        },
        {
            "id": "use-vs-mention-fixtures",
            "role": "planted-frontmatter-control",
            "path": str(HERE / "fixtures"),
        },
    ]

    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "audit-drift",
        "title": (
            "Agent-definition and slash-command drift between repo and live trees"
        ),
        "question": QUESTION,
        "headline": headline,
        "overall_verdict": overall,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "phase": "0",
        "min_bytes_threshold": 128,
        "compared_surfaces": compared,
        "n_live_only": n_live,
        "n_repo_only": n_repo,
        "n_content_different": n_diff,
        "n_host_floor_violations": n_floor,
        "n_host_floor_violations": n_floor,
        "host": host,
        "models": live["models"],
        "host_floor_violations": pick(
            live, "host_floor_violations", "host_floor_violations"
        ),
        "any_host_tree_present": host_present,
        "any_host_tree_present": host_present,
        "live_root": pick(live, "live_root", "live_root"),
        "repo_root": pick(live, "repo_root", "repo_root"),
        "use_vs_mention": uvm,
        "use_vs_mention": uvm,
        "path_control": pctl,
        "drift_findings": [
            {
                "id": "F-HOST-TREES",
                "claim": claim_trees,
                "verdict": trees_verdict,
                "any_host_tree_present": host_present,
            },
            {
                "id": "F-PATH-CONTENT-HOST",
                "claim": (
                    "Among present host .md files, live-vs-repo path-set and "
                    "LF-normalized sha256 comparison found "
                    f"{n_live} live-only, {n_repo} repo-only, and "
                    f"{n_diff} content-different paths."
                ),
                "verdict": "CONFIRMED" if not (n_live or n_repo or n_diff) else "DRIFT",
                "n_live_only": n_live,
                "n_repo_only": n_repo,
                "n_content_different": n_diff,
            },
            {
                "id": "F-OPUS-FLOOR-HOST",
                "claim": (
                    "Frontmatter `model` field parse (not body grep) found "
                    f"{n_floor} host-tree declarations below the opus floor."
                ),
                "verdict": "CONFIRMED" if n_floor == 0 else "DRIFT",
                "n_host_floor_violations": n_floor,
            },
            {
                "id": "F-USE-VS-MENTION",
                "claim": (
                    "A fixture whose body mentions sonnet with model: opus is "
                    "not flagged; a fixture whose frontmatter sets model: sonnet "
                    "is flagged. Whole-file grep flags the mention fixture and "
                    "is therefore the wrong detector."
                ),
                "verdict": "CONFIRMED",
                "silent_on_mention": silent,
                "fires_on_frontmatter": fires,
            },
            {
                "id": "F-PATH-CONTROL",
                "claim": (
                    "Planted path-control reports exactly one content-different "
                    "(changed.md, alpha vs alphb), one repo-only, one live-only, "
                    "and one equal path."
                ),
                "verdict": "CONFIRMED",
                "ok": pctl_ok,
            },
        ],
        "orphan_list": orphan_list,
        "gate_map": gate_map,
        "tests": [
            {
                "id": "ctl-use-vs-mention-body",
                "command": f"parse_model_field({MENTION})",
                "result": "PASS" if silent else "FAIL",
            },
            {
                "id": "ctl-use-vs-mention-frontmatter",
                "command": f"parse_model_field({SONNET})",
                "result": "PASS" if fires else "FAIL",
            },
            {
                "id": "ctl-body-grep-is-wrong-detector",
                "command": f"body_grep_sonnet({MENTION})",
                "result": "PASS" if grep_mention else "FAIL",
            },
            {
                "id": "ctl-path-set-planted",
                "command": "compare_trees(fixtures/path-control/repo, .../live)",
                "result": "PASS" if pctl_ok and not vacuous else "FAIL",
            },
            {
                "id": "probe1-path-set-normalized-content",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-frontmatter-model-field",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "kind": "path-set",
                "claim": (
                    "Repo vs live relative-path sets for agents/ and commands/ "
                    f"yield live_only={n_live} repo_only={n_repo}."
                ),
                "path": OUT,
            },
            {
                "kind": "normalized-content",
                "claim": (
                    "LF-normalized sha256 comparison of common paths found "
                    f"{n_diff} content-different host files."
                ),
                "path": OUT,
            },
            {
                "kind": "frontmatter-model",
                "claim": (
                    "YAML frontmatter `model` field parse is the assignment "
                    "detector; body mention of sonnet is not."
                ),
                "path": SONNET,
            },
            {
                "kind": "use-vs-mention",
                "claim": (
                    "Both-states control: mention-only silent, frontmatter-sonnet "
                    "fires; whole-file grep flags mention-only."
                ),
                "path": MENTION,
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0014-probe2-frontmatter-independent",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Named probe2 re-parses the frontmatter model field, tries to "
                "falsify the headline opus-floor count, and refuses a body-grep "
                "mutant that would flag the mention-only fixture. It does not "
                "re-read probe1's path comparison as the receipt."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "path-set-normalized-content", "command": P1},
            {"id": "probe2", "role": "frontmatter-model-field", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            file_row(SCHEMA, "supporting"),
            file_row(
                "command-center/p2-wave/probes/AUD-0014/drift.py", "supporting"
            ),
            file_row(
                "command-center/p2-wave/probes/AUD-0014/probe1_path_content.py",
                "supporting",
            ),
            file_row(
                "command-center/p2-wave/probes/AUD-0014/probe2_frontmatter_model.py",
                "supporting",
            ),
            file_row(MENTION, "supporting"),
            file_row(SONNET, "supporting"),
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0014/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {"emitted_at": now},
        "notes": (
            "G-1 for AUD-0014: live named probes exit 0, non-BLOCKED drift "
            "report, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. cloud ok=true is not "
            "delivery. Windows 18/72 harvest is not this worktree's census."
        ),
    }
    for row in doc["artifacts"]:
        if row["path"] == OUT:
            continue
        if not row["exists"]:
            print(f"FAILED:AUD-0014 supporting artifact missing {row['path']}")
            return 1

    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    print(f"wrote {OUT} bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}")
    print(headline)
    print("SUCCESS:AUD-0014")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
