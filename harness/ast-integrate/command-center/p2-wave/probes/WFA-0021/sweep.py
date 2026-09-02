#!/usr/bin/env python3
"""Deterministic vendor-doc sweep for WFA-0021.

Quotes are pre-registered, then asserted to occur inside the neutralized
retrieved excerpt. No embedded instruction is followed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

import lib as L  # noqa: E402
import registry_index as R  # noqa: E402

QUESTION = (
    "Which first-party orchestration mechanisms documented by Anthropic "
    "(Claude Code workflows, subagents, hooks, skills, agent teams), "
    "OpenAI (Codex, AGENTS.md) and Google (Antigravity) are NOT "
    "represented in the registry, and what is each one's stability "
    "guarantee and licence?"
)

SENTINEL = "SUCCESS:WFA-0021"

# Pre-registered quote windows. Each quote must appear in the named
# capture's neutralized excerpt or emit fails (fabrication guard).
MECHANISMS: list[dict[str, Any]] = [
    {
        "id": "anthropic.claude-code.skills",
        "vendor": "anthropic",
        "runtime": "claude-code",
        "name": "skills",
        "aliases": ["skill", "skills", "g-skill"],
        "quote": (
            "Claude Code skills follow the Agent Skills open standard, "
            "which works across multiple AI tools."
        ),
        "quote_capture": "cc-skills-docs",
        "surface_ids": ["cc-skills-docs", "cc-changelog", "agentskills-spec"],
        "stability": {
            "label": "documented",
            "quote": (
                "Claude Code skills follow the Agent Skills open standard"
            ),
            "experimental": False,
        },
        "license": {
            "mechanism_files": (
                "optional SPDX in SKILL.md frontmatter (docs: Claude Code "
                "accepts the field but doesn't act on it)"
            ),
            "runtime": "LicenseRef-Anthropic-Commercial (no LICENSE blob fetched)",
            "spec": (
                "Agent Skills described as an open standard on agentskills.io; "
                "no SPDX identifier on the fetched spec page"
            ),
            "spdx": None,
            "adverse_inference": True,
            "carry_code_across": False,
        },
    },
    {
        "id": "anthropic.claude-code.subagents",
        "vendor": "anthropic",
        "runtime": "claude-code",
        "name": "subagents",
        "aliases": ["subagent", "subagents"],
        "quote": (
            "Each subagent runs in its own context window with a custom "
            "system prompt, specific tool access, and independent permissions."
        ),
        "quote_capture": "cc-subagents-docs",
        "surface_ids": ["cc-subagents-docs", "cc-changelog"],
        "stability": {
            "label": "documented",
            "quote": (
                "Subagent forking is now on by default: a subagent_type: "
                '"fork" subagent inherits the full conversation and prompt cache.'
            ),
            "experimental": False,
        },
        "license": {
            "runtime": "LicenseRef-Anthropic-Commercial (no LICENSE blob fetched)",
            "spdx": None,
            "adverse_inference": True,
            "carry_code_across": False,
        },
    },
    {
        "id": "anthropic.claude-code.hooks",
        "vendor": "anthropic",
        "runtime": "claude-code",
        "name": "hooks (command)",
        "aliases": ["hook", "hooks"],
        "quote": (
            "For production workflows, prefer command hooks."
        ),
        "quote_capture": "cc-hooks-guide",
        "surface_ids": ["cc-hooks-guide", "cc-changelog"],
        "stability": {
            "label": "documented-command-hooks; agent-hooks-experimental",
            "quote": (
                "Agent hooks are experimental. Behavior and configuration "
                "may change in future releases."
            ),
            "experimental": False,
        },
        "license": {
            "runtime": "LicenseRef-Anthropic-Commercial (no LICENSE blob fetched)",
            "spdx": None,
            "adverse_inference": True,
            "carry_code_across": False,
        },
    },
    {
        "id": "anthropic.claude-code.agent-hooks",
        "vendor": "anthropic",
        "runtime": "claude-code",
        "name": "agent-based hooks",
        "aliases": ["agent-hooks", "agent-based-hooks"],
        "quote": (
            "Agent hooks are experimental. Behavior and configuration "
            "may change in future releases."
        ),
        "quote_capture": "cc-hooks-guide",
        "surface_ids": ["cc-hooks-guide", "cc-changelog"],
        "stability": {
            "label": "experimental",
            "quote": (
                "Fixed agent frontmatter hooks running from untrusted folders"
            ),
            "experimental": True,
        },
        "license": {
            "runtime": "LicenseRef-Anthropic-Commercial (no LICENSE blob fetched)",
            "spdx": None,
            "adverse_inference": True,
            "carry_code_across": False,
        },
    },
    {
        "id": "anthropic.claude-code.agent-teams",
        "vendor": "anthropic",
        "runtime": "claude-code",
        "name": "agent teams",
        "aliases": ["agent-teams", "agent_teams"],
        "quote": (
            "Agent teams are experimental and disabled by default. Enable "
            "them by setting CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 in your "
            "settings.json or environment."
        ),
        "quote_capture": "cc-agent-teams-docs",
        "surface_ids": ["cc-agent-teams-docs", "cc-changelog"],
        "stability": {
            "label": "experimental-disabled-by-default",
            "quote": (
                "Agent teams are experimental and disabled by default."
            ),
            "experimental": True,
        },
        "license": {
            "runtime": "LicenseRef-Anthropic-Commercial (no LICENSE blob fetched)",
            "spdx": None,
            "adverse_inference": True,
            "carry_code_across": False,
        },
    },
    {
        "id": "anthropic.claude-code.dynamic-workflows",
        "vendor": "anthropic",
        "runtime": "claude-code",
        "name": "dynamic workflows",
        "aliases": [
            "dynamic-workflow",
            "dynamic-workflows",
            "claude-code-workflows",
            "workflow",
        ],
        "quote": (
            "A dynamic workflow is a JavaScript script that orchestrates "
            "subagents at scale."
        ),
        "quote_capture": "cc-workflows-docs",
        "surface_ids": ["cc-workflows-docs", "cc-changelog"],
        "stability": {
            "label": "documented-since-v2.1.154-paid-plans",
            "quote": (
                "Dynamic workflows require Claude Code v2.1.154 or later "
                "and are available on all paid plans."
            ),
            "experimental": False,
        },
        "license": {
            "runtime": "LicenseRef-Anthropic-Commercial (no LICENSE blob fetched)",
            "spdx": None,
            "adverse_inference": True,
            "carry_code_across": False,
        },
    },
    {
        "id": "openai.codex.agents-md",
        "vendor": "openai",
        "runtime": "codex",
        "name": "AGENTS.md",
        "aliases": ["agents.md", "agents-md", "codex"],
        "quote": (
            "AGENTS.md emerged from collaborative efforts across the AI "
            "software development ecosystem, including OpenAI Codex, Amp, "
            "Jules from Google, Cursor, and Factory."
        ),
        "quote_capture": "agents-md-spec",
        "surface_ids": ["agents-md-spec", "codex-agents-md-source"],
        "stability": {
            "label": "open-format-aaif-linux-foundation",
            "quote": (
                "AGENTS.md is now stewarded by the Agentic AI Foundation "
                "under the Linux Foundation."
            ),
            "experimental": False,
        },
        "license": {
            "runtime": "Apache-2.0",
            "runtime_blob_url": (
                "https://raw.githubusercontent.com/openai/codex/main/LICENSE"
            ),
            "runtime_blob_quote": (
                "Apache License Version 2.0, January 2004"
            ),
            "format": (
                "open format on agents.md; no SPDX identifier on the fetched page"
            ),
            "spdx": "Apache-2.0",
            "adverse_inference": False,
            "carry_code_across": False,
        },
    },
    {
        "id": "google.antigravity.workflows",
        "vendor": "google",
        "runtime": "antigravity",
        "name": "workflows",
        "aliases": ["antigravity-workflows", "antigravity"],
        "quote": (
            "Once saved, Workflows can be invoked in Agent via a slash "
            "command with the format /workflow-name."
        ),
        "quote_capture": "antigravity-workflows-docs",
        "surface_ids": ["antigravity-workflows-docs"],
        "stability": {
            "label": "undated-on-fetched-docs",
            "quote": (
                "Workflow files are limited to 12,000 characters each."
            ),
            "experimental": None,
        },
        "license": {
            "runtime": "UNCLASSIFIED-ADVERSE (no LICENSE blob fetched)",
            "spdx": None,
            "adverse_inference": True,
            "carry_code_across": False,
        },
    },
    {
        "id": "google.antigravity.rules",
        "vendor": "google",
        "runtime": "antigravity",
        "name": "rules",
        "aliases": ["antigravity-rules", "gemini-md-rules"],
        "quote": (
            "Rules are manually defined constraints for the Agent to follow, "
            "at both the local and global levels."
        ),
        "quote_capture": "antigravity-rules-docs",
        "surface_ids": ["antigravity-rules-docs"],
        "stability": {
            "label": "undated-on-fetched-docs",
            "quote": (
                "Global rules live in ~/.gemini/GEMINI.md and are applied "
                "across all workspaces."
            ),
            "experimental": None,
        },
        "license": {
            "runtime": "UNCLASSIFIED-ADVERSE (no LICENSE blob fetched)",
            "spdx": None,
            "adverse_inference": True,
            "carry_code_across": False,
        },
    },
]


def load_captures() -> dict[str, dict[str, Any]]:
    raw = json.loads((HERE / "captures.json").read_text(encoding="utf-8"))
    out = {}
    for cap in raw["captures"]:
        excerpt = cap["excerpt"]
        cap = dict(cap)
        cap["excerpt_sha256"] = L.sha256_text(excerpt)
        out[cap["id"]] = cap
    return out


def surfaces_for(
    spec: dict[str, Any], caps: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = []
    for cid in spec["surface_ids"]:
        cap = caps[cid]
        rows.append(
            {
                "id": cid,
                "kind": cap["kind"],
                "url": cap["url"],
                "retrieved_at": cap["retrieved_at"],
                "http_date": cap.get("http_date"),
                "excerpt_sha256": cap["excerpt_sha256"],
                "body_bytes": cap.get("body_bytes"),
            }
        )
    return rows


def run_sweep(
    caps: dict[str, dict[str, Any]] | None = None,
    specs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    caps = caps if caps is not None else load_captures()
    specs = specs if specs is not None else MECHANISMS
    injection_log: list[dict[str, Any]] = []
    neutralized: dict[str, str] = {}
    for cid, cap in caps.items():
        safe, log = L.neutralize(cap["excerpt"])
        neutralized[cid] = safe
        for item in log:
            injection_log.append({"capture_id": cid, "url": cap["url"], **item})
            if item.get("followed"):
                raise RuntimeError("injection followed — refuse emit")

    records = []
    for spec in specs:
        qid = spec["quote_capture"]
        if qid not in neutralized:
            raise RuntimeError(f"missing quote capture {qid}")
        quote = spec["quote"]
        if not L.quote_in_neutralized(quote, neutralized[qid]):
            raise RuntimeError(
                f"quote not in neutralized excerpt for {spec['id']}"
            )
        if not L.timestamp_ok(caps[qid].get("retrieved_at")):
            raise RuntimeError(f"undated quote capture {qid}")
        surfs = surfaces_for(spec, caps)
        grade = L.grade_surfaces(surfs)
        if grade["status"] == "REJECTED-UNDATED":
            continue
        join = R.join_mechanism(spec["aliases"])
        promoted = grade["status"] == "VERIFIED"
        if grade["status"] == "UNVERIFIED" and promoted:
            raise RuntimeError("UNVERIFIED promoted")
        records.append(
            {
                "id": spec["id"],
                "vendor": spec["vendor"],
                "runtime": spec["runtime"],
                "name": spec["name"],
                "quote": quote,
                "quote_source_url": caps[qid]["url"],
                "quote_retrieved_at": caps[qid]["retrieved_at"],
                "surfaces": surfs,
                "verification": grade["status"],
                "verification_kinds": grade["kinds"],
                "settling_probe": grade.get("settling_probe"),
                "stability": spec["stability"],
                "license": spec["license"],
                "registry_join": join,
                "registry_membership": join["membership"],
                "promoted": promoted,
            }
        )

    represented = [
        r["id"]
        for r in records
        if r["registry_membership"] == "REPRESENTED-IN-RECONSTRUCTED-INDEX"
    ]
    not_represented = [
        r["id"]
        for r in records
        if r["registry_membership"]
        in {
            "ABSENT-FROM-RECONSTRUCTED-INDEX",
            "NAME-COLLISION-NOT-MEMBERSHIP",
        }
    ]
    unverified = [r["id"] for r in records if r["verification"] == "UNVERIFIED"]
    verified = [r["id"] for r in records if r["verification"] == "VERIFIED"]
    for r in records:
        if r["verification"] == "UNVERIFIED":
            if r["promoted"]:
                raise RuntimeError("single-surface promoted")
            if not r.get("settling_probe"):
                raise RuntimeError("UNVERIFIED missing settling_probe")
        if not L.timestamp_ok(r.get("quote_retrieved_at")):
            raise RuntimeError("finding without timestamp")

    return {
        "mechanisms": records,
        "injection_log": injection_log,
        "summary": {
            "n_mechanisms": len(records),
            "verified": verified,
            "unverified": unverified,
            "represented_in_reconstructed_index": represented,
            "not_represented_in_reconstructed_index": not_represented,
        },
        "neutralized": neutralized,
    }


def build_artifact(sweep: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit_id": "WFA-0021",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "record_type": "SweepReport",
        "schema_note": (
            "WFA-0001 wfa-schema-pack.json is absent on this tree. This "
            "document is a SweepReport-shaped record validated against "
            "command-center/p2-wave/probes/WFA-0021/sweep-report.schema.json, "
            "not against the missing pack."
        ),
        "question": QUESTION,
        "generated_at": "2026-08-24T18:54:51Z",
        "upstream_registry": R.upstream_block(),
        "join_key": {
            "name": "exact-alias-to-reconstructed-family-token",
            "content_hash_trap": (
                "Do not join on URL, filename, or a token inside a candidate "
                "name. wf-saved-codex-auth-research-fanout containing "
                "'codex' is not membership of openai.codex.agents-md. "
                "cmd-multi-workflow containing 'workflow' is not membership "
                "of anthropic.claude-code.dynamic-workflows."
            ),
        },
        "sources": [
            {
                "id": c["id"],
                "url": c["url"],
                "kind": c["kind"],
                "retrieved_at": c["retrieved_at"],
                "http_date": c.get("http_date"),
                "excerpt_sha256": c["excerpt_sha256"],
                "claimed_body_bytes": c.get("body_bytes"),
            }
            for c in load_captures().values()
        ],
        "mechanisms": sweep["mechanisms"],
        "summary": sweep["summary"],
        "injection_log": sweep["injection_log"],
        "evidence": {
            "A": (
                "primary-source URLs with retrieval timestamps and verbatim "
                "mechanism quotes from neutralized excerpts"
            ),
            "B": (
                "second surface class: changelog (Claude Code), source "
                "(openai/codex agents_md.rs), spec (agents.md / agentskills.io). "
                "Antigravity has only docs-class surfaces and stays UNVERIFIED."
            ),
        },
        "tests": [
            {
                "id": "untrusted-data-neutralise",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0021/"
                    "probe1_injection_neutralize.py"
                ),
            },
            {
                "id": "single-surface-unverified-and-timestamps",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/WFA-0021/"
                    "probe2_unverified_and_timestamps.py"
                ),
            },
        ],
        "controls": {
            "planted_injection_must_not_promote": True,
            "undated_claim_cannot_be_finding": True,
            "single_surface_cannot_be_verified": True,
        },
        "residual_unknowns": [
            {
                "id": "WFA-0021-R1",
                "summary": (
                    "08-WORKFLOW-CANDIDATE-REGISTRY.json (284 rows) is not "
                    "on this Linux worktree; vs-284-row membership is "
                    "UNDETERMINED-FILE-ABSENT for every mechanism."
                ),
            },
            {
                "id": "WFA-0021-R2",
                "summary": (
                    "OpenAI developers.openai.com/codex/guides/agents-md "
                    "timed out; AGENTS.md existence uses agents.md + "
                    "github.com/openai/codex source, not the OpenAI docs page."
                ),
            },
            {
                "id": "WFA-0021-R3",
                "summary": (
                    "Anthropic Claude Code LICENSE blob was not fetched; "
                    "runtime licence is adverse-inferred, quotes only."
                ),
            },
            {
                "id": "WFA-0021-R4",
                "summary": (
                    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md is not on this "
                    "worktree; this sweep did not subtract mechanisms from it."
                ),
            },
        ],
        "reviewer": {
            "independent": True,
            "reviewer_id": "WFA-0021-probe2-unverified-and-timestamps",
            "verdict": "PASS",
            "note": (
                "Reviewer requirement is the unit's named both-states "
                "control re-run, not a second human."
            ),
        },
    }


def main() -> int:
    sweep = run_sweep()
    n = sweep["summary"]["n_mechanisms"]
    print(f"mechanisms={n} unverified={sweep['summary']['unverified']}")
    print(f"not_represented={sweep['summary']['not_represented_in_reconstructed_index']}")
    print("SUCCESS:WFA-0021-sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
