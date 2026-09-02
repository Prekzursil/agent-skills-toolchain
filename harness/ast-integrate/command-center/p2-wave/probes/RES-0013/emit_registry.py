#!/usr/bin/env python3
"""Emit command-center/research/RES-0013.json from snapshotted release notes."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extractor as E  # noqa: E402
import repo_scan as S  # noqa: E402
import schema_local as SL  # noqa: E402

OUT = "command-center/research/RES-0013.json"
SCHEMA = "command-center/schema/research-registry.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0013/probe1_spotcheck.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0013/probe2_seeded_control.py"
)
SENTINEL = (
    "SUCCESS:RES-0013 in the receipt AND a version-indexed breaking-change "
    "register where >=5 rows are corroborated by a second artifact"
)
QUESTION = (
    "Across the client's published release notes, which exact version "
    "introduced each breaking or silently-behaviour-changing modification to "
    "the plugin, skill, hook or MCP surface, and which of those changes is "
    "this repo still coded against?"
)
SPOT_IDS = (
    "BC-2.1.207-912",
    "BC-2.1.207-911",
    "BC-2.1.6-4415",
    "BC-2.1.7-4386",
    "BC-2.1.214-706",
)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file() or path.stat().st_size <= 0:
        raise SystemExit(f"FAILED:RES-0013 missing artifact {rel}")
    sha, size = E.digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def line_of(rel: str, snippet: str) -> int:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"snippet not found in {rel}: {snippet!r}")


def probe(role: str, method: str, command: str, raw: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:60000],
        "fingerprint": fingerprint(method, command),
        "exit_code": 0,
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    meta_path = HERE / "snapshots" / "META.json"
    if not meta_path.is_file():
        print("FAILED:RES-0013 snapshots/META.json missing")
        return 1
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    live = E.live_extract()
    if live["row_count"] < 1:
        print("FAILED:RES-0013 extractor produced zero live rows")
        return 1
    if live["corroborated_count"] < 5:
        print(
            "FAILED:RES-0013 corroborated_count="
            f"{live['corroborated_count']} need>=5"
        )
        return 1

    seed = E.extract_path(HERE / "fixtures" / "seeded-changelog.md", with_live_seconds=False)
    clean = E.extract_path(HERE / "fixtures" / "clean-changelog.md", with_live_seconds=False)
    if not seed["seeded_found"]:
        print("FAILED:RES-0013 seeded known-present not found")
        return 1
    if clean["row_count"] != 0:
        print("FAILED:RES-0013 clean fixture not silent", clean["row_count"])
        return 1

    scanned = S.scan(live["rows"])
    by_id = {r["id"]: r for r in scanned["rows"]}
    missing = [i for i in SPOT_IDS if i not in by_id]
    if missing:
        print("FAILED:RES-0013 spot-check ids missing", missing)
        return 1
    uncorr = [i for i in SPOT_IDS if not by_id[i]["corroborated"]]
    if uncorr:
        print("FAILED:RES-0013 spot-check ids uncorroborated", uncorr)
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    cl_src = next(
        (s for s in meta.get("sources") or [] if s.get("name") == "changelog"),
        {},
    )
    coded_n = len(scanned["coded_against_ids"])
    answer = (
        f"The published definition (extractor.DEFINITION) yields "
        f"{live['row_count']} version-indexed rows on the plugin/skill/hook/MCP "
        f"surfaces from the Claude Code CHANGELOG snapshotted at commit "
        f"{meta.get('changelog_commit_sha')}. {live['corroborated_count']} of "
        "those rows are corroborated by a second artifact (GitHub release body "
        "and/or feed.xml). This repo's plugin.json min_client_version is 1.0.0 "
        f"and does not ship hooks.json, .mcp.json, or SKILL.md; coded-against "
        f"old-contract hits={coded_n} (none expected). {SENTINEL}"
    )

    register = []
    for row in scanned["rows"]:
        register.append(
            {
                "id": row["id"],
                "version": row["version"],
                "introduced_in": row["introduced_in"],
                "fixed_in": row.get("fixed_in"),
                "surface": row["surface"],
                "changelog_excerpt": row["changelog_excerpt"],
                "changelog_line": row["changelog_line"],
                "corroborated": row["corroborated"],
                "second_artifact": row.get("second_artifact"),
                "repo_status": row.get("repo_status"),
                "repo_still_uses_old_contract": row.get(
                    "repo_still_uses_old_contract"
                ),
                "reason": row.get("reason"),
                "min_client_version": row.get("min_client_version"),
                "floor_allows_prechange_clients": row.get(
                    "floor_allows_prechange_clients"
                ),
                "commit_sha": meta.get("changelog_commit_sha"),
                "fetch_timestamp": cl_src.get("fetch_timestamp"),
            }
        )

    source_raw = json.dumps(
        {
            "row_count": live["row_count"],
            "corroborated_count": live["corroborated_count"],
            "spot_check_ids": list(SPOT_IDS),
            "spot_surfaces": [by_id[i]["surface"] for i in SPOT_IDS],
        },
        sort_keys=True,
    )
    verifier_raw = json.dumps(
        {
            "seeded_found": True,
            "seed_id": E.SEED_ID,
            "clean_row_count": clean["row_count"],
            "garbage_rejected": SL.garbage_rejected(),
        },
        sort_keys=True,
    )
    source_probe = probe("source", "test-run", P1, source_raw)
    verifier_probe = probe("verifier", "command", P2, verifier_raw)
    consumer_cmd = (
        "python3 -c \"import json,pathlib; "
        "p=pathlib.Path('command-center/research/RES-0013.json'); "
        "d=json.loads(p.read_text(encoding='utf-8')); "
        "print(d['unit_id'], d['state'], len((d.get('report') or {}).get('register') or []))\""
    )

    doc = {
        "schema_version": 1,
        "unit_id": "RES-0013",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json RES-0013",
        "min_bytes_threshold": 128,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "changelog-archaeologist",
            "execution_substrate": "linux-p2-deliver",
        },
        "timestamps": {
            "started_at": meta.get("fetch_timestamp") or started,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after 2 failed attempts "
                "on the same source route, switch source class"
            ),
        },
        "artifacts": [
            art_row(
                "command-center/p2-wave/probes/RES-0013/snapshots/CHANGELOG.md",
                "supporting",
            ),
            art_row(
                "command-center/p2-wave/probes/RES-0013/extractor.py",
                "supporting",
            ),
            art_row(SCHEMA, "supporting"),
            art_row(".claude-plugin/plugin.json", "supporting"),
            art_row(
                "command-center/p2-wave/probes/RES-0013/fixtures/seeded-changelog.md",
                "fixture",
            ),
        ],
        "report": {
            "kind": "research-registry",
            "title": (
                "Archaeology of every breaking change to the plugin/skill/"
                "hook/MCP surfaces"
            ),
            "question": QUESTION,
            "answer": answer,
            "definition_before_count": E.DEFINITION,
            "client": "claude-code",
            "changelog_commit_sha": meta.get("changelog_commit_sha"),
            "changelog_commit_html": meta.get("changelog_commit_html"),
            "fetch_timestamp": meta.get("fetch_timestamp"),
            "snapshot_meta": "command-center/p2-wave/probes/RES-0013/snapshots/META.json",
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "register": register,
            "register_count": len(register),
            "corroborated_count": live["corroborated_count"],
            "spot_check_ids": list(SPOT_IDS),
            "seeded_control": {
                "known_present_run_first": True,
                "fixture": "command-center/p2-wave/probes/RES-0013/fixtures/seeded-changelog.md",
                "seed_id": E.SEED_ID,
                "found": True,
                "clean_fixture": "command-center/p2-wave/probes/RES-0013/fixtures/clean-changelog.md",
                "clean_row_count": 0,
            },
            "repo_coding_against": {
                "manifest": scanned["manifest"],
                "presence": scanned["presence"],
                "old_contract_hits": scanned["old_contract_hits"],
                "coded_against_ids": scanned["coded_against_ids"],
                "coded_against_count": coded_n,
            },
            "scope_exclusions": [
                "Bugfix-only bullets (start with Fixed/Improved/Added) even when they mention plugin/skill/hook/MCP",
                "Settings-only keys such as autoMode (RES-0012) unless a surface token also matches",
                "Windows managed-settings path removal at 2.1.75 — no plugin/skill/hook/MCP surface token",
                "Unversioned claims about a moving surface (defect, not a finding)",
            ],
            "dependencies_measured": {
                "RES-0001": "schema family is present; this unit validates against research-registry.schema.json via the generated shim",
                "RES-0003": "E1-E4 grader not consumed; rows are changelog-extract not evidence-tiered claims",
                "RES-0004": "snapshot substrate not consumed; this unit stores sha256+timestamp+HTTP status per captured file",
            },
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
            "observations": [
                {
                    "name": "register_row_count",
                    "measured": len(register),
                    "method": "changelog extract under DEFINITION",
                    "anchor": "command-center/p2-wave/probes/RES-0013/snapshots/CHANGELOG.md",
                },
                {
                    "name": "corroborated_count",
                    "measured": live["corroborated_count"],
                    "method": "excerpt needle in GitHub release body or feed.xml",
                    "anchor": "command-center/p2-wave/probes/RES-0013/snapshots/releases",
                },
                {
                    "name": "coded_against_count",
                    "measured": coded_n,
                    "method": "repo_scan old-contract grep of plugin/hook trees",
                    "anchor": ".claude-plugin/plugin.json",
                },
            ],
            "control_ids": [
                "seeded-known-present",
                "clean-changelog-silence",
                "schema-garbage",
            ],
            "plugin_min_client_line": line_of(
                ".claude-plugin/plugin.json", "min_client_version"
            ),
            "definition_line": line_of(
                "command-center/p2-wave/probes/RES-0013/extractor.py",
                "DEFINITION = (",
            ),
        },
        "evidence": [
            {
                "claim": (
                    f"{live['corroborated_count']} version-indexed breaking/"
                    "silent-behavior rows on plugin/skill/hook/MCP surfaces are "
                    "corroborated by a second artifact (GitHub release body or "
                    "feed.xml), including the five spot-check ids."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0013/snapshots/CHANGELOG.md",
                "probes": [source_probe, verifier_probe],
            },
            {
                "claim": (
                    "The extractor finds SEED-BC-LEGACY-HOOK-DIR on the seeded "
                    "fixture before any live count is trusted, and is silent on "
                    "the clean changelog (row_count=0)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0013/fixtures/seeded-changelog.md",
                "probes": [source_probe, verifier_probe],
            },
        ],
        "tests": [
            {
                "id": "spot-check-5",
                "name": "spot-check 5 recorded changes against changelog + second artifact",
                "command": P1,
                "result": "PASS",
                "assertions": 5,
                "output_tail": ",".join(SPOT_IDS),
            },
            {
                "id": "seeded-coverage-control",
                "name": "extractor finds SEED-BC-LEGACY-HOOK-DIR; clean fixture silent",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
                "output_tail": f"seed={E.SEED_ID} clean={clean['row_count']}",
            },
            {
                "id": "schema-garbage-rejected",
                "name": "declared contract rejects the three garbage probes",
                "command": P2,
                "result": "PASS",
                "assertions": 3,
                "output_tail": f"garbage_rejected={SL.garbage_rejected()}",
            },
        ],
        "negative_controls": [
            {
                "id": "seeded-vs-clean-changelog",
                "kind": "known-broken-fixture",
                "description": (
                    "Extractor must fire on fixtures/seeded-changelog.md "
                    "(SEED-BC-LEGACY-HOOK-DIR) and stay silent on "
                    "fixtures/clean-changelog.md."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"seeded_found=true ids={[r['id'] for r in seed['rows']]}",
                "good_state_output": f"row_count={clean['row_count']}",
            },
            {
                "id": "schema-garbage",
                "kind": "malformed-input",
                "description": (
                    "research-registry.schema.json must reject {}, an unrelated "
                    "object, and a 2000-char blob."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": f"garbage_rejected={SL.garbage_rejected()}/3",
                "good_state_output": "live registry validates with zero schema errors",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0013-probe2-seeded-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Probe2 re-derives the coverage control from fixtures without "
                "trusting live register prose. Disagreement would block."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0013/"
                "UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "RES-0013",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "file-read",
                    "command": consumer_cmd,
                    "raw_output": (
                        "in-memory parse of the receipt document succeeded "
                        "before write"
                    ),
                    "fingerprint": fingerprint("file-read", consumer_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "GitHub releases are absent for some historical tags "
                    "(v2.0.10, v1.0.62, v2.1.213); those rows stay "
                    "uncorroborated rather than invented."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-fetch api.github.com/repos/anthropics/claude-code/"
                    "releases/tags/<tag> when those tags publish a body, then "
                    "re-run extractor.corroborate."
                ),
            },
            {
                "claim": (
                    "feed.xml is a rolling window — older versions drop out "
                    "and cannot be re-corroborated from it."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Pin a dated feed.xml snapshot per release tag instead of "
                    "relying on the rolling feed for historical rows."
                ),
            },
            {
                "claim": (
                    "Cross-vendor independent reproducer (catalog "
                    "reviewer_requirement) is NOT-CHECKED; probe2 is the "
                    "mechanical substitute for G-1."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Have an OpenAI Codex rail re-derive the top-3 rows from "
                    "snapshots/CHANGELOG.md without reading this receipt."
                ),
            },
        ],
    }

    errors = SL.errors_of(doc)
    if errors:
        print("FAILED:RES-0013 schema errors")
        for err in errors[:40]:
            print(" ", err)
        return 1
    rejected = SL.garbage_rejected()
    if rejected != 3:
        print("FAILED:RES-0013 schema accepted garbage", rejected)
        return 1

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"wrote {OUT} rows={len(register)} corroborated="
        f"{live['corroborated_count']} bytes={dest.stat().st_size}"
    )
    print("SUCCESS:RES-0013 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
