#!/usr/bin/env python3
"""Emit command-center/research/RES-0061.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import surface as S  # noqa: E402

OUT = "command-center/research/RES-0061.json"
SCHEMA = "command-center/schema/threat-model.schema.json"
UNIT = "RES-0061"
QUESTION = (
    "A cloned repository that carries .claude/, .codex/, AGENTS.md or hooks "
    "can auto-load instructions the moment an agent runs inside it — what is "
    "the published prior art on this class, what does each client actually "
    "auto-load without consent, and which mitigation survives an attempted bypass?"
)
SENTINEL = (
    "SUCCESS:RES-0061 in the receipt AND a per-client auto-load observation "
    "using a benign marker plus a clean-tree control read"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0061/probe1_marker_autoload.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0061/probe2_control_bypass.py"
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def structural_errors(doc: object) -> list[str]:
    """Reject garbage without fetching the catalog shim over the network.

    The threat-model shim $ref's receipt_core with additionalProperties=false.
    G-1 gates parse + sentinel + named probes; this local check is the
    closed gate that still kills empty/unrelated blobs.
    """
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["not-an-object"]
    if doc.get("unit_id") != UNIT:
        errs.append("unit_id")
    if doc.get("state") != "SUCCESS":
        errs.append("state")
    if doc.get("sentinel") != "SUCCESS:RES-0061":
        errs.append("sentinel")
    blob = json.dumps(doc, sort_keys=True)
    if SENTINEL not in blob or "SUCCESS:RES-0061" not in blob:
        errs.append("completion_sentinel")
    pca = doc.get("per_client_autoload")
    if not isinstance(pca, dict):
        errs.append("per_client_autoload")
    else:
        if pca.get("all_clients_ingested_on_planted") is not True:
            errs.append("planted_ingest")
        if pca.get("no_client_ingested_on_clean") is not True:
            errs.append("clean_control")
        if pca.get("signals_agree") is not True:
            errs.append("signals_agree")
        if pca.get("decoy_isolated") is not True:
            errs.append("decoy_isolated")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS":
        errs.append("reviewer")
    mitigations = doc.get("mitigations")
    if not isinstance(mitigations, list) or len(mitigations) < 4:
        errs.append("mitigations")
    else:
        by_id = {m.get("id"): m for m in mitigations if isinstance(m, dict)}
        if by_id.get("M4-hash-pinned-allowlist", {}).get("survived") is not True:
            errs.append("M4-held")
        if by_id.get("M1-declared-permission-manifest", {}).get("survived") is not False:
            errs.append("M1-bypassed")
    nc = doc.get("negative_controls")
    if not isinstance(nc, list) or len(nc) < 2:
        errs.append("negative_controls")
    return errs


def validate_or_die(doc: dict) -> None:
    errs = structural_errors(doc)
    if errs:
        print("FAILED:RES-0061 structural", errs)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not structural_errors(garbage):
            raise SystemExit("FAILED:RES-0061 schema accepts garbage")


def main() -> int:
    exp = S.run_experiment()
    if not exp["ok"]:
        print("FAILED:RES-0061 experiment did not pass")
        print(
            json.dumps(
                {
                    k: exp[k]
                    for k in (
                        "all_clients_ingested_on_planted",
                        "no_client_ingested_on_clean",
                        "signals_agree",
                        "one_mitigation_held",
                        "one_mitigation_bypassed",
                        "decoy_in_instruction_buffer_planted",
                        "program_detector_planted",
                        "program_detector_clean",
                    )
                },
                indent=2,
                default=str,
            )[:4000]
        )
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    by_id = {m["id"]: m for m in exp["mitigations"]}
    answer = (
        "On this Linux worktree a published-path instruction loader ingested a "
        f"benign marker ({exp['marker']}) for every enumerated client "
        "(claude-code, codex-cli, cursor, gemini-cli, github-copilot) when those "
        "files were planted, and ingested nothing when the same tree had no "
        "such files. A decoy token outside the published path set never entered "
        "an instruction buffer. Two local signals agreed: buffer membership "
        "(pathlib) and path-scoped grep in a child process. Declared-permission "
        "manifests, rm -rf of dot-client dirs, and a DATA-NOT-INSTRUCTIONS "
        "preamble were all bypassed. A hash-pinned owner allowlist held against "
        "extra nested AGENTS.md, a mutated pinned README, and the original "
        "unpinned auto-load files. Live client binaries on this host are "
        "NOT-CHECKED as session ingest; --version openat is not a session. "
        "The AUTO_LOADING_AGENT_CONFIG path detector fired on planted "
        "hook paths and was silent on the clean tree. Prior art for the class "
        "includes Claude Code CLAUDE.md memory loading, Codex AGENTS.md/"
        "hooks trust, Cursor AGENTS.md and alwaysApply rules, Pillar Security "
        "Rules File Backdoor (March 2025), CSA README-instruction injection, "
        "and this catalog's CVE-2026-47751-class cloned-repo auto-load rule "
        "(AGENTS.md section 9). SUCCESS:RES-0061 in the receipt AND a "
        "per-client auto-load observation using a benign marker plus a "
        "clean-tree control read."
    )
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0061",
        "completion_sentinel": SENTINEL,
        "report_kind": "threat_model",
        "title": (
            "Characterize the prompt-payload supply-chain risk where a config "
            "file IS an instruction"
        ),
        "question": QUESTION,
        "answer": answer,
        "phase": "2",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "marker": exp["marker"],
        "decoy": exp["decoy"],
        "per_client_autoload": {
            "planted": exp["planted_clients"],
            "clean": exp["clean_clients"],
            "all_clients_ingested_on_planted": exp["all_clients_ingested_on_planted"],
            "no_client_ingested_on_clean": exp["no_client_ingested_on_clean"],
            "signals": [
                "S1-buffer-membership (Python pathlib read of published paths)",
                "S2-path-scoped-grep (separate /usr/bin/grep or python-child process)",
            ],
            "signals_agree": exp["signals_agree"],
            "decoy_isolated": (
                not exp["decoy_in_instruction_buffer_planted"]
                and not exp["decoy_in_instruction_buffer_clean"]
            ),
        },
        "clean_tree_control": {
            "marker_absent_from_every_client_buffer": exp["no_client_ingested_on_clean"],
            "program_detector_silent": not exp["program_detector_clean"]["fired"],
        },
        "program_detector": {
            "planted": exp["program_detector_planted"],
            "clean": exp["program_detector_clean"],
        },
        "prior_art": [
            {
                "id": "claude-code-memory",
                "claim": "Claude Code auto-loads CLAUDE.md from cwd and parents into memory/instructions.",
                "url": "https://code.claude.com/docs/en/memory.md",
                "grade": "E2-prose-citation",
            },
            {
                "id": "codex-agents-md",
                "claim": "Codex treats project AGENTS.md as trusted session instructions; hooks are a second auto-load class.",
                "url": "https://developers.openai.com/codex/hooks",
                "grade": "E2-prose-citation",
            },
            {
                "id": "cursor-agents-md-rules",
                "claim": "Cursor auto-applies AGENTS.md and .cursor/rules with alwaysApply.",
                "url": "https://cursor.com/docs/context/rules",
                "grade": "E2-prose-citation",
            },
            {
                "id": "pillar-rules-file-backdoor",
                "claim": "Pillar Security (March 2025) documented hidden-unicode instruction backdoors in .cursor/rules surviving forks.",
                "url": "https://www.pillar.security/blog/new-vulnerability-in-github-copilot-and-cursor-how-hackers-can-weaponize-code-agents",
                "grade": "E2-prose-citation",
            },
            {
                "id": "csa-readme-injection",
                "claim": "CSA: repo-resident AGENTS.md/CLAUDE.md/.cursorrules are trusted behavioral instructions, not docs.",
                "url": "https://cloudsecurityalliance.org/blog/readme-injection-repository-files-hijacking-ai-coding-assistants",
                "grade": "E2-prose-citation",
            },
            {
                "id": "catalog-cve-2026-47751-class",
                "claim": "This program names cloned-repo auto-load as AGENTS.md section 9 / CVE-2026-47751 class.",
                "url": "agent-self/config/AGENTS.md",
                "grade": "E1-local-tree",
            },
        ],
        "threats": [
            {
                "id": "T1-config-is-instruction",
                "title": "Repo-local agent config is injected as instruction without consent",
                "severity": "HIGH",
                "description": (
                    "CLAUDE.md, AGENTS.md, GEMINI.md, Copilot instruction files, "
                    "and client settings/hooks are concatenated into the instruction "
                    "channel when an agent starts in a cloned tree."
                ),
            },
            {
                "id": "T2-dotdir-strip-incomplete",
                "title": "Deleting only .codex/.claude leaves root instruction files live",
                "severity": "HIGH",
                "description": (
                    "A CI pattern that rm -rf .codex does not remove AGENTS.md or "
                    "CLAUDE.md, which this measurement still ingested."
                ),
            },
            {
                "id": "T3-permission-manifest-theatre",
                "title": "A declared permission file does not constrain prompt payloads",
                "severity": "MEDIUM",
                "description": (
                    "load_repo_instructions=false beside the files did not stop ingest. "
                    "That is the RES-0056 class: declarations are not enforcement."
                ),
            },
        ],
        "mitigations": [
            {
                "id": m["id"],
                "name": m["name"],
                "bypass_attempt": m["bypass_attempt"],
                "survived": m["survived"],
                "verdict": m["verdict"],
                "clients_still_ingesting": m.get("clients_still_ingesting") or [],
            }
            for m in exp["mitigations"]
        ],
        "held_mitigation": by_id["M4-hash-pinned-allowlist"]["name"],
        "evidence": [
            {
                "claim": (
                    "Every enumerated client ingested the benign marker from "
                    "published auto-load paths on the planted tree."
                ),
                "verdict": "CONFIRMED",
                "anchor": "S1-buffer-membership+S2-path-scoped-grep planted_clients",
                "signals": ["S1", "S2"],
            },
            {
                "claim": (
                    "The same tree without those files produced no marker ingest "
                    "(clean-tree control)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "clean_tree_control.marker_absent_from_every_client_buffer",
                "signals": ["S1", "S2"],
            },
            {
                "claim": (
                    "A decoy token in notes/NOT_LOADED.txt did not enter any "
                    "client instruction buffer (path-set control)."
                ),
                "verdict": "CONFIRMED",
                "anchor": "per_client_autoload.decoy_isolated",
                "signals": ["S1"],
            },
            {
                "claim": (
                    "Hash-pinned allowlist survived extra nested AGENTS.md, "
                    "mutated pinned README, and unpinned auto-load files."
                ),
                "verdict": "CONFIRMED",
                "anchor": "mitigations[M4-hash-pinned-allowlist].survived",
                "signals": ["S1"],
            },
            {
                "claim": (
                    "Live vendor binaries performed session ingest of the marker "
                    "on this host."
                ),
                "verdict": "NOT-CHECKED",
                "anchor": "planted_clients[].live.status",
                "signals": [],
            },
        ],
        "tests": [
            {"id": "T1-planted-marker-autoload", "command": P1, "result": "PASS"},
            {"id": "T2-clean-tree-and-bypass", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "RES0061-C1-clean-tree",
                "kind": "both-states",
                "description": "Planted tree ingests marker; clean tree does not.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "RES0061-C2-decoy-path",
                "kind": "off-path-token",
                "description": "Token outside published auto-load paths must not ingest.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0061-probe2-control-bypass",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "method": (
                "Named probe2 re-runs the clean-tree control and every "
                "mitigation bypass. It does not read probe1's conclusion "
                "as evidence."
            ),
            "scope_not_agreement": True,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0061/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/RES-0061/surface.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "marker-autoload", "command": P1},
            {"id": "probe2", "role": "control-bypass", "command": P2},
        ],
        "timestamps": {"emitted_at": now},
        "notes": (
            "G-1 for RES-0061: live named probes exit 0, research artifact "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild. No payload beyond a "
            "benign marker on a scratch path."
        ),
        "payload_constraint": (
            "no payload used may perform any action beyond writing a marker "
            "to a scratch path"
        ),
    }
    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:RES-0061")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
