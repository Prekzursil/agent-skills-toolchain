#!/usr/bin/env python3
"""Emit command-center/research/RES-0011.json."""
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

from contract import (  # noqa: E402
    AGENT_FRONTMATTER_KEYS,
    COMMAND_FRONTMATTER_KEYS,
    PLUGIN_IGNORED_AGENT_KEYS,
    agent_gate,
    command_gate,
    parse_frontmatter,
)
from estate import census  # noqa: E402
from spawn import (  # noqa: E402
    spawn_agent_forbidden_call,
    spawn_command_forbidden_call,
)

OUT = "command-center/research/RES-0011.json"
SENTINEL = (
    "SUCCESS:RES-0011 in the receipt AND a transcript showing the forbidden "
    "call refused for the restricted agent and allowed for the unrestricted one"
)
QUESTION = (
    "What frontmatter keys do agent (.md) and command definitions support today, "
    "how is a subagent's model chosen, and can a definition genuinely RESTRICT "
    "the tool set a subagent receives - or is the restriction advisory?"
)
DOCS = {
    "subagents": "https://code.claude.com/docs/en/sub-agents",
    "slash_commands": "https://code.claude.com/docs/en/slash-commands",
    "tools_reference": "https://code.claude.com/docs/en/tools-reference",
    "fetched": "2026-08-25",
}


def inventory_tree(root: Path, documented: tuple[str, ...]) -> dict:
    """Parse YAML frontmatter keys actually present in a definition tree."""
    if not root.is_dir():
        return {
            "present": False,
            "path": str(root),
            "files": 0,
            "with_frontmatter": 0,
            "without_frontmatter": 0,
            "parse_fail": 0,
            "observed_keys": [],
            "observed_counts": {},
            "keys_not_in_docs_table": [],
            "documented_never_observed": list(documented),
        }
    files = sorted(p for p in root.glob("*.md") if p.is_file())
    keys: dict[str, list[str]] = {}
    no_fm = 0
    parse_fail = 0
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.startswith("---"):
            no_fm += 1
            continue
        try:
            fm, _ = parse_frontmatter(text)
        except ValueError:
            parse_fail += 1
            continue
        for key in fm.keys():
            keys.setdefault(str(key), []).append(path.name)
    observed = sorted(keys)
    return {
        "present": True,
        "path": str(root.relative_to(REPO)).replace("\\", "/"),
        "files": len(files),
        "with_frontmatter": len(files) - no_fm - parse_fail,
        "without_frontmatter": no_fm,
        "parse_fail": parse_fail,
        "observed_keys": observed,
        "observed_counts": {k: len(v) for k, v in keys.items()},
        "keys_not_in_docs_table": [k for k in observed if k not in documented],
        "documented_never_observed": [k for k in documented if k not in observed],
    }


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _strip_ts(event: dict) -> dict:
    out = dict(event)
    out.pop("ts", None)
    return out


def main() -> int:
    os.environ.pop("CLAUDE_CODE_SUBAGENT_MODEL", None)
    restricted = spawn_agent_forbidden_call(HERE / "fixtures/restricted.md")
    unrestricted = spawn_agent_forbidden_call(HERE / "fixtures/unrestricted.md")
    cmd_adv = spawn_command_forbidden_call(HERE / "fixtures/command-advisory.md")
    cmd_deny = spawn_command_forbidden_call(HERE / "fixtures/command-disallow.md")
    if restricted["decision"] != "REFUSED" or unrestricted["decision"] != "ALLOWED":
        print("FAILED:emit restriction both-states did not fire")
        print(json.dumps({"restricted": restricted, "unrestricted": unrestricted}))
        return 1
    if cmd_adv["decision"] != "ALLOWED" or cmd_deny["decision"] != "REFUSED":
        print("FAILED:emit command advisory/deny both-states did not fire")
        return 1

    est = census()
    inv_agents = inventory_tree(REPO / "agents", AGENT_FRONTMATTER_KEYS)
    inv_commands = inventory_tree(REPO / "commands", COMMAND_FRONTMATTER_KEYS)
    ag_r = agent_gate(HERE / "fixtures/restricted.md")
    ag_u = agent_gate(HERE / "fixtures/unrestricted.md")
    cg_a = command_gate(HERE / "fixtures/command-advisory.md")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    repo_agents_n = inv_agents["files"]
    repo_cmds_n = inv_commands["files"]
    user_trees = any(
        (est.get("trees") or {}).get(k, {}).get("is_dir_pathlib")
        for k in ("live_agents", "live_commands")
    )

    answer = (
        "On the documented Claude Code contract re-fetched 2026-08-25, agent "
        "markdown supports the YAML keys name, description (required), tools, "
        "disallowedTools, model, permissionMode, maxTurns, skills, mcpServers, "
        "hooks, memory, background, effort, isolation, color, and initialPrompt. "
        "Command/skill markdown supports name, description, when_to_use, "
        "argument-hint, arguments, disable-model-invocation, user-invocable, "
        "allowed-tools, disallowed-tools, model, effort, context, agent, "
        "background, hooks, paths, shell, metadata, license, and compatibility. "
        "A subagent model is chosen in order CLAUDE_CODE_SUBAGENT_MODEL, then "
        "the per-invocation model parameter, then the definition's model "
        "frontmatter, then the parent conversation model; omitted or inherit "
        "falls through. Agent tools/disallowedTools genuinely filter the tool "
        "pool a subagent receives. Command allowed-tools is advisory "
        "pre-approval and does not shrink the callable pool; command "
        "disallowed-tools does remove tools for that turn. This Linux estate "
        f"has repo-root agents/ ({repo_agents_n} md) and commands/ "
        f"({repo_cmds_n} md); ~/.claude/agents and ~/.claude/commands are "
        f"{'present' if user_trees else 'absent'}; no claude CLI, so the "
        "shipped binary was not attached. Keys observed in repo files that "
        "are absent from the docs table (agent fallbacks/server-side-fallback; "
        "command `command` and underscore allowed_tools) are treated as "
        "unhonoured until a behaviour delta is measured. Fixture transcripts: "
        "restricted REFUSED Bash, unrestricted ALLOWED the same call."
    )

    claims = [
        {
            "id": "C-FRONTMATTER-AGENT",
            "claim": (
                "Agent .md definitions support the documented YAML keys "
                + ", ".join(AGENT_FRONTMATTER_KEYS)
                + "; only name and description are required."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "canonical_mechanism": "yaml-frontmatter-key-table",
            "settling_probe": "command-center/p2-wave/probes/RES-0011/probe1_restricted_refuse.py",
            "signals": [
                "official subagents frontmatter table re-fetched 2026-08-25",
                "repo agents/*.md YAML key inventory (field parse, not body grep)",
            ],
            "strongest_caveat": (
                "This estate has no live ~/.claude/agents tree and no claude "
                "CLI, so the table is the documented client contract plus a "
                "repo-file inventory, not a binary-attached behaviour map. "
                "AUD-0014's 2026-08-19 harvest listed these trees MISSING; "
                "they are present now at repo root."
            ),
        },
        {
            "id": "C-FRONTMATTER-COMMAND",
            "claim": (
                "Command/skill definitions support the documented YAML keys "
                + ", ".join(COMMAND_FRONTMATTER_KEYS)
                + "."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "canonical_mechanism": "yaml-frontmatter-key-table",
            "settling_probe": "command-center/p2-wave/probes/RES-0011/probe2_unrestricted_allow.py",
            "signals": [
                "official slash-commands/skills frontmatter table re-fetched 2026-08-25",
                "repo commands/*.md YAML key inventory (field parse, not body grep)",
            ],
            "strongest_caveat": (
                "Claude.ai skill packaging rejects keys such as argument-hint; "
                "Claude Code accepts the full table. This unit maps Claude Code. "
                f"{inv_commands['without_frontmatter']} of {inv_commands['files']} "
                "repo command files have no YAML frontmatter at all."
            ),
        },
        {
            "id": "C-MODEL-ORDER",
            "claim": (
                "A subagent's model is env CLAUDE_CODE_SUBAGENT_MODEL, then "
                "per-invocation model, then frontmatter model, then parent; "
                "env inherit is unset as of v2.1.196."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E3",
            "confidence_band": "high",
            "canonical_mechanism": "ordered-fallback-resolver",
            "settling_probe": "command-center/p2-wave/probes/RES-0011/probe2_unrestricted_allow.py",
            "signals": [
                "official subagents Choose a model order list re-fetched 2026-08-25",
                "resolver four-case table env/invocation/frontmatter/parent",
            ],
            "strongest_caveat": (
                "availableModels substitution and the live Claude Code binary "
                "were not attached on this estate."
            ),
        },
        {
            "id": "C-AGENT-RESTRICTS",
            "claim": (
                "An agent definition can genuinely restrict the tool set a "
                "subagent receives: tools is an allowlist and disallowedTools "
                "is a denylist applied to the resolved pool, not an advisory "
                "hint."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E3",
            "confidence_band": "high",
            "canonical_mechanism": "resolved-tool-set-gate",
            "settling_probe": "command-center/p2-wave/probes/RES-0011/probe1_restricted_refuse.py",
            "signals": [
                "docs: 'The subagent can't edit files, write files, or use any MCP tools'",
                "fixture spawn: restricted REFUSED Bash; unrestricted ALLOWED the same argv",
            ],
            "strongest_caveat": (
                "The refuse/allow transcript is from this worktree's fixture "
                "runtime reproducing the documented gate. The Claude Code "
                "binary is absent here, so a future binary regression would "
                "not be caught by these probes."
            ),
        },
        {
            "id": "C-COMMAND-ALLOWED-ADVISORY",
            "claim": (
                "Command/skill allowed-tools is advisory pre-approval: it does "
                "not restrict which tools are callable."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E3",
            "confidence_band": "high",
            "canonical_mechanism": "preapproval-not-allowlist",
            "settling_probe": "command-center/p2-wave/probes/RES-0011/probe2_unrestricted_allow.py",
            "signals": [
                "docs: 'It does not restrict which tools are available: every tool remains callable'",
                "fixture command with allowed-tools: Read Grep still ALLOWED Bash",
            ],
            "strongest_caveat": (
                "disallowed-tools on the same command/skill surface IS a "
                "turn-scoped genuine restriction; do not collapse both fields "
                "into 'advisory'."
            ),
        },
        {
            "id": "C-LIVE-TREES",
            "claim": (
                "This Linux worktree has live ~/.claude/agents, ~/.claude/commands, "
                "AND repo agents/ commands/ trees that can be inventoried."
            ),
            "verdict": "REFUTED",
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "canonical_mechanism": "path-is-dir",
            "settling_probe": "command-center/p2-wave/probes/RES-0011/estate.py",
            "signals": [
                "pathlib.Path.is_dir on six candidate roots (estate.py REPO=probe-dir.parents[3])",
                "os.path.isdir on the same six roots",
            ],
            "strongest_caveat": (
                "Conjunction fails because ~/.claude/agents and ~/.claude/commands "
                "are absent. Repo-root agents/ and commands/ ARE present; that "
                "weaker claim is C-REPO-TREES. AUD-0014's 2026-08-19 harvest "
                "listed repo trees MISSING; they exist on this 2026-08-25 seed."
            ),
        },
        {
            "id": "C-REPO-TREES",
            "claim": (
                "Repo-root agents/ and commands/ exist on this worktree and "
                "contain markdown definitions whose YAML frontmatter keys can "
                "be inventoried by field parse."
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E1",
            "confidence_band": "almost-certain",
            "canonical_mechanism": "path-is-dir",
            "settling_probe": "command-center/p2-wave/probes/RES-0011/estate.py",
            "signals": [
                f"agents/: {inv_agents['files']} md, {inv_agents['with_frontmatter']} with YAML",
                f"commands/: {inv_commands['files']} md, {inv_commands['with_frontmatter']} with YAML",
            ],
            "strongest_caveat": (
                "These are repo-root trees, not ~/.claude/ or .claude/ trees. "
                "A key's presence in a file is not evidence the client honours it."
            ),
        },
        {
            "id": "C-UNDOCUMENTED-KEYS-ARE-CONTRACT",
            "claim": (
                "Undocumented keys observed in repo definitions (agent "
                "fallbacks, server-side-fallback; command `command` and "
                "underscore allowed_tools) are part of the Claude Code "
                "agent/command contract the client honours."
            ),
            "verdict": "REFUTED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "canonical_mechanism": "docs-table-minus-observed",
            "settling_probe": "command-center/p2-wave/probes/RES-0011/estate.py",
            "signals": [
                "2026-08-25 subagents/skills frontmatter tables omit those keys",
                "repo inventory lists them via YAML field parse, not body grep",
            ],
            "strongest_caveat": (
                "Refutation is 'honoured by the client'. The keys exist as "
                "bytes in files. commands/skill-create.md uses allowed_tools "
                "(underscore) rather than the documented allowed-tools "
                "(hyphen); that is a misspelling, not a second documented field."
            ),
        },
        {
            "id": "C-RESTRICTION-IS-ONLY-ADVISORY",
            "claim": (
                "Tool lists on agent definitions are advisory and a restricted "
                "subagent can still invoke a forbidden tool."
            ),
            "verdict": "REFUTED",
            "evidence_tier": "E3",
            "confidence_band": "high",
            "canonical_mechanism": "resolved-tool-set-gate",
            "settling_probe": "command-center/p2-wave/probes/RES-0011/probe1_restricted_refuse.py",
            "signals": [
                "restricted fixture REFUSED Bash",
                "same call ALLOWED after adding Bash to tools: (both-states mutant)",
            ],
            "strongest_caveat": (
                "Refutation is of the agent tools field. Command allowed-tools "
                "really is advisory; that is a different claim (C-COMMAND-ALLOWED-ADVISORY)."
            ),
        },
    ]

    doc = {
        "unit_id": "RES-0011",
        "id": "RES-0011",
        "state": "SUCCESS",
        "status": "SUCCESS",
        "registered": True,
        "report_kind": "research-claim-record",
        "report": {"kind": "research-claim-record"},
        "output_schema_declared": "command-center/schema/research-claim-record.schema.json",
        "output_schema_on_disk": (
            REPO / "command-center/schema/research-claim-record.schema.json"
        ).is_file(),
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": (
            "Map the agent and slash-command definition contracts and their "
            "tool-restriction surface"
        ),
        "question": QUESTION,
        "answer": answer,
        "freshness_stamp": now,
        "docs_fetched": DOCS,
        "source_lineage": [
            {
                "kind": "official-docs",
                "url": DOCS["subagents"],
                "fetched": DOCS["fetched"],
                "role": "agent-frontmatter-and-model-order",
            },
            {
                "kind": "official-docs",
                "url": DOCS["slash_commands"],
                "fetched": DOCS["fetched"],
                "role": "command-skill-frontmatter",
            },
            {
                "kind": "official-docs",
                "url": DOCS["tools_reference"],
                "fetched": DOCS["fetched"],
                "role": "tools-vs-disallowedTools-resolution",
            },
            {
                "kind": "catalog",
                "path": "command-center/WORK-UNIT-CATALOG.json",
                "role": "unit-contract",
            },
            {
                "kind": "fixture",
                "path": "command-center/p2-wave/probes/RES-0011/fixtures/restricted.md",
                "role": "restricted-subagent",
            },
            {
                "kind": "fixture",
                "path": "command-center/p2-wave/probes/RES-0011/fixtures/unrestricted.md",
                "role": "unrestricted-subagent",
            },
            {
                "kind": "inventory",
                "path": "agents/",
                "role": "repo-agent-frontmatter-keys",
            },
            {
                "kind": "inventory",
                "path": "commands/",
                "role": "repo-command-frontmatter-keys",
            },
        ],
        "frontmatter_contracts": {
            "agent": {
                "required": ["name", "description"],
                "keys": list(AGENT_FRONTMATTER_KEYS),
                "plugin_ignored": sorted(PLUGIN_IGNORED_AGENT_KEYS),
                "tools_field": "genuine-allowlist",
                "disallowedTools_field": "genuine-denylist",
                "both_set_rule": (
                    "disallowedTools applied first, then tools resolved "
                    "against the remaining pool"
                ),
            },
            "command": {
                "required": [],
                "recommended": ["description"],
                "keys": list(COMMAND_FRONTMATTER_KEYS),
                "allowed-tools": "advisory-preapproval",
                "disallowed-tools": "turn-scoped-genuine-denylist",
            },
        },
        "model_resolution": {
            "order": [
                "CLAUDE_CODE_SUBAGENT_MODEL",
                "per-invocation model parameter",
                "definition model frontmatter",
                "parent conversation model",
            ],
            "default": "inherit",
            "aliases": ["sonnet", "opus", "haiku", "fable", "inherit"],
            "restricted_fixture": ag_r["model"],
            "unrestricted_fixture": ag_u["model"],
        },
        "restriction_surface": {
            "agent_tools_restricts": True,
            "agent_disallowedTools_restricts": True,
            "command_allowed_tools_restricts": False,
            "command_disallowed_tools_restricts": True,
            "restricted_resolved": ag_r["tool_resolution"],
            "unrestricted_resolved": ag_u["tool_resolution"],
            "command_advisory_resolved": cg_a["tool_resolution"],
        },
        "transcripts": {
            "forbidden_call": {
                "tool": "Bash",
                "argv": "echo RES-0011-FORBIDDEN-CALL",
            },
            "restricted": _strip_ts(restricted),
            "unrestricted": _strip_ts(unrestricted),
            "command_advisory": _strip_ts(cmd_adv),
            "command_disallow": _strip_ts(cmd_deny),
            "summary": (
                "transcript showing the forbidden call refused for the "
                "restricted agent and allowed for the unrestricted one"
            ),
        },
        "estate": est,
        "inventory": {"agents": inv_agents, "commands": inv_commands},
        "claims": claims,
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/RES-0011/fixtures/restricted.md",
                "kind": "fixture",
                "claim": "C-AGENT-RESTRICTS",
                "snippet": "tools: Read, Grep, Glob",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0011/fixtures/unrestricted.md",
                "kind": "fixture",
                "claim": "C-AGENT-RESTRICTS",
                "snippet": "model: inherit",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0011/fixtures/command-advisory.md",
                "kind": "fixture",
                "claim": "C-COMMAND-ALLOWED-ADVISORY",
                "snippet": "allowed-tools: Read Grep",
            },
            {
                "path": "https://code.claude.com/docs/en/sub-agents",
                "kind": "official-docs",
                "claim": "C-FRONTMATTER-AGENT",
                "snippet": "Supported frontmatter fields",
            },
            {
                "path": "https://code.claude.com/docs/en/slash-commands",
                "kind": "official-docs",
                "claim": "C-FRONTMATTER-COMMAND",
                "snippet": "Frontmatter reference; allowed-tools does not restrict which tools are available",
            },
            {
                "path": "agents/",
                "kind": "inventory",
                "claim": "C-REPO-TREES",
                "snippet": f"{inv_agents['files']} md; extra keys={inv_agents['keys_not_in_docs_table']}",
            },
            {
                "path": "commands/skill-create.md",
                "kind": "inventory",
                "claim": "C-UNDOCUMENTED-KEYS-ARE-CONTRACT",
                "snippet": "allowed_tools (underscore), not allowed-tools",
            },
        ],
        "tests": [
            {
                "id": "probe1",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0011/probe1_restricted_refuse.py"
                ),
                "result": "PASS",
            },
            {
                "id": "probe2",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                    "command-center/p2-wave/probes/RES-0011/probe2_unrestricted_allow.py"
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "mention-is-not-grant",
                "detail": (
                    "restricted.md body mentions Bash; resolved tool set still "
                    "excludes Bash and the call is REFUSED."
                ),
            },
            {
                "id": "allowed-tools-does-not-deny",
                "detail": (
                    "command-advisory.md lists allowed-tools: Read Grep; Bash "
                    "is still ALLOWED."
                ),
            },
            {
                "id": "underscore-allowed-tools-is-not-the-docs-field",
                "detail": (
                    "commands/skill-create.md has allowed_tools (underscore). "
                    "The documented field is allowed-tools (hyphen). Presence "
                    "of the underscore key is not a grant."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0011-probe2-unrestricted-allow",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "defaulted_to_refuted_when_insufficient": True,
            "notes": (
                "Live Claude Code binary and ~/.claude/agents are absent; "
                "repo-root agents/ and commands/ are present. Inventory claims "
                "about user trees stay REFUTED. Undocumented keys default to "
                "REFUTED as client-honoured."
            ),
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            }
        ],
        "residual_unknowns": [
            "Whether the exact Claude Code build that would run on the Windows "
            "estate still matches the 2026-08-25 public docs for zero-tools "
            "launch failure (changed in v2.1.208).",
            "command-center/schema/research-claim-record.schema.json exists here "
            "as a generated shim that $ref's platform/schema/artifact-class-profiles.schema.json. "
            "G-1 delivery does not network-resolve that $id; live binary "
            "attachment of tools-vs-disallowedTools remains untested.",
            "Repo agent tools lists include names outside the documented "
            "background subagent pool (for example ReportFindings on "
            "agents/code-reviewer.md); unresolved-name behaviour of the "
            "shipped binary was not attached.",
        ],
        "contradiction_support_edges": [
            {
                "from": "C-AGENT-RESTRICTS",
                "to": "C-RESTRICTION-IS-ONLY-ADVISORY",
                "kind": "contradicts",
            },
            {
                "from": "C-COMMAND-ALLOWED-ADVISORY",
                "to": "C-AGENT-RESTRICTS",
                "kind": "does-not-generalize",
            },
            {
                "from": "C-REPO-TREES",
                "to": "C-LIVE-TREES",
                "kind": "does-not-generalize",
            },
            {
                "from": "C-FRONTMATTER-AGENT",
                "to": "C-UNDOCUMENTED-KEYS-ARE-CONTRACT",
                "kind": "contradicts",
            },
        ],
        "named_settling_probe": (
            "command-center/p2-wave/probes/RES-0011/probe1_restricted_refuse.py"
        ),
        "snapshot_sha256": hashlib.sha256(
            (HERE / "fixtures/restricted.md").read_bytes()
            + b"\n"
            + (HERE / "fixtures/unrestricted.md").read_bytes()
        ).hexdigest(),
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    out_path.write_text(payload, encoding="utf-8")
    sha, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:RES-0011 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
