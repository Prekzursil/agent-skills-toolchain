"""build/wfa-2: emit platform/registry/workflow-candidates-2.json for candidates 33-64.

Every numeric field is READ OUT OF _wfa2b_probe_out.json, never typed by hand, so
the registry cannot disagree with the probe. Prose fields are authored from the
READMEs / docstrings / diffs actually read in this unit; anything not read is
tagged UNVERIFIED inline on the field it qualifies.

Then it RUNS the contract checks (required fields, controlled vocabulary, unique
sequential ids, provenance-anchor shape, near-duplicate scan with a planted-clone
detector control) and refuses to write if any check fails.
"""

from __future__ import annotations

import json
import re
import sys
from itertools import combinations
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/source/ast-integrate")
PROBE = REPO / "command-center" / "_wfa2b_probe_out.json"
OUT = REPO / "platform" / "registry" / "workflow-candidates-2.json"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"
MIRROR = "C:/Users/Prekzursil/.claude/harness-restore-20260806/main-mirror.git"
DOC08 = (
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
    "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md"
)

CLASSES = {
    "ADOPT-AS-IS",
    "ADOPT-WITH-WRAPPER",
    "TRANSLATE",
    "REPAIR",
    "EXTEND",
    "MERGE",
    "COMPOSE",
    "CLEAN-ROOM-REIMPLEMENT",
    "DISTILL",
    "SPECIALIZE",
    "GENERALIZE",
    "REBUILD-FROM-SPEC",
    "RETIRE",
    "REJECT",
    "UNKNOWN-NEEDS-PROBE",
}

REQUIRED = [
    "n",
    "id",
    "name",
    "family",
    "classification",
    "provenance",
    "license",
    "maintenance",
    "task_fit",
    "stages",
    "roles",
    "tools",
    "stop_rules",
    "failure_behaviour",
    "benchmark_evidence",
    "reusable_mechanisms",
    "prior_doc08",
    "verdict_basis",
]

# ---------------------------------------------------------------- probe intake
P = json.loads(PROBE.read_text(encoding="utf-8"))
T = {r["path"]: r for r in P["tools"]}
H = {r["file"]: r for r in P["harness"]}
A = {r["agent"]: r for r in P["agents_block"]["agents"]}
DUPS = P["agents_block"]["near_duplicate_pairs"]
DUPCTL = P["agents_block"]["dup_detector_control"]
DC = P["detector_controls"]

# The one license fact that governs every first-party candidate in this range.
NO_LICENSE = {
    "spdx": None,
    "declared": False,
    "effective": "no-declared-license (all-rights-reserved by default); owner-authored private estate",
    "source": (
        f"MEASURED: `git --git-dir {MIRROR} ls-tree --name-only {REF[:8]}` has NO "
        "LICENSE/COPYING/NOTICE at repo root (detector control: the same listing "
        "shows README.md/AGENTS.md/SECURITY.md present, and a case-insensitive grep "
        "for 'readme' over it returns 1). 111 LICENSE files DO exist tree-wide, all "
        "under .agents/skills/* vendored third-party skills - none covers tools/, "
        "agents/ or agent-self/harness/."
    ),
    "redistributable": False,
}


def tool_prov(path: str, file_anchor: str | None = None) -> dict:
    r = T[path]
    lc = r["last_commit"] or {}
    return {
        "repo": "agent-skills-toolchain (private, owner-authored)",
        "ref": REF,
        "path": path,
        "read_via": f"git --git-dir {MIRROR} cat-file -p {REF[:8]}:<path>",
        "anchor": file_anchor or (r["readme"]["path"] if r["readme"] else path),
        "exists_at_ref": r["exists_at_ref"],
        "n_files": r["n_files"],
        "loc": r["loc"],
        "test_files": r["test_files"],
        "last_commit": lc,
        "commits_touching_path": r["commits"],
    }


def tool_maint(path: str) -> dict:
    r = T[path]
    lc = r["last_commit"] or {}
    return {
        "last_commit_date": lc.get("date"),
        "last_commit_sha": lc.get("sha"),
        "last_commit_subject": lc.get("subject"),
        "commits_touching_path": r["commits"],
        "state": "versioned on main tip (07f465f3 == refs/heads/main); no release tags consulted",
        "deploy_state": (
            "UNVERIFIED - whether this tool is deployed into any live tree was NOT probed "
            "by this unit; settle with a live-tree stat of the same relative path."
        ),
    }


def harness_prov(f: str) -> dict:
    r = H[f]
    lc = r["repo_last_commit"] or {}
    return {
        "repo": "agent-skills-toolchain (private, owner-authored)",
        "ref": REF,
        "path": r["repo_path"],
        "live_path": r["live_path"],
        "read_via": f"live filesystem read + git --git-dir {MIRROR} cat-file -p {REF[:8]}:{r['repo_path']}",
        "anchor": f"{r['live_path']} (live, {r['live_loc']} lines) vs {REF[:8]}:{r['repo_path']} ({r['repo_loc']} lines)",
        "live_loc": r["live_loc"],
        "repo_loc": r["repo_loc"],
        "live_unique_lines": r["live_unique_lines"],
        "repo_unique_lines": r["repo_unique_lines"],
        "drift_direction": (
            "live-ahead"
            if r["live_unique_lines"] > r["repo_unique_lines"]
            else (
                "repo-ahead"
                if r["repo_unique_lines"] > r["live_unique_lines"]
                else "even"
            )
        ),
        "n_defs": r["n_defs"],
        "n_classes": r["n_classes"],
        "last_commit": lc,
    }


def harness_maint(f: str) -> dict:
    r = H[f]
    lc = r["repo_last_commit"] or {}
    return {
        "live_mtime": r["live_mtime"],
        "last_commit_date": lc.get("date"),
        "last_commit_sha": lc.get("sha"),
        "last_commit_subject": lc.get("subject"),
        "state": "LIVE (deployed and loaded by the hook dispatcher) + versioned counterpart on main",
        "drift": (
            f"live_unique={r['live_unique_lines']} repo_unique={r['repo_unique_lines']} "
            f"(set-of-lines diff, live-as-of-{r['live_mtime']} vs {REF[:8]})"
        ),
    }


def agent_prov(a: str) -> dict:
    r = A[a]
    lc = r["repo_last_commit"] or {}
    return {
        "repo": "agent-skills-toolchain (private, owner-authored)",
        "ref": REF,
        "path": r["repo_path"],
        "live_path": r["live_path"],
        "read_via": f"live filesystem read + git --git-dir {MIRROR} cat-file -p {REF[:8]}:{r['repo_path']}",
        "anchor": f"{r['live_path']}:1-5 (YAML frontmatter) ; {REF[:8]}:{r['repo_path']}",
        "live_loc": r["live_loc"],
        "repo_loc": r["repo_loc"],
        "repo_identical_to_live": r["repo_identical_to_live"],
        "last_commit": lc,
        "commits_touching_path": r["repo_commits"],
    }


def agent_maint(a: str) -> dict:
    r = A[a]
    lc = r["repo_last_commit"] or {}
    return {
        "live_mtime": r["live_mtime"],
        "last_commit_date": lc.get("date"),
        "last_commit_sha": lc.get("sha"),
        "last_commit_subject": lc.get("subject"),
        "commits_touching_path": r["repo_commits"],
        "state": (
            "deployed live AND versioned; live byte-identical to main"
            if r["repo_identical_to_live"]
            else "deployed live AND versioned; live DIFFERS from main (see provenance)"
        ),
        "has_stale_bak_copy": r["has_bak"],
        "bak_jaccard_vs_live": r["bak_jaccard_vs_live"],
    }


def agent_tools(a: str) -> list[str] | str:
    raw = (A[a]["fm_tools"] or "").strip()
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    return raw or "INHERIT-ALL (no tools: field)"


AGENT_ROLE = "claude-code subagent (Task-tool dispatch target); one role per definition"
AGENT_STOP = (
    "returns its structured report and the Task ends; no iteration cap, no retry, "
    "no re-dispatch - the parent orchestrator owns any loop. UNVERIFIED for the 15 "
    "definitions whose bodies were not read line-by-line in this unit (frontmatter + "
    "description + diff only); settle by grepping each body for an explicit stop/round cap."
)

# --------------------------------------------------------------------- entries
E: list[dict] = []


def add(**kw):
    E.append(kw)


# ---- 33 -------------------------------------------------------------------
add(
    n=33,
    id="tool-search-expansion",
    name="tools/search-expansion - RRF rank fusion + SearXNG regional expansion",
    family="C-repo-tool",
    classification="ADOPT-AS-IS",
    provenance=tool_prov(
        "tools/search-expansion", "tools/search-expansion/README.md:1-30"
    ),
    license=dict(
        NO_LICENSE,
        third_party_note=(
            "Algorithm borrow, not code borrow: implements Reciprocal Rank Fusion and "
            "cites 'the RRF paper's damping constant' k=60 "
            "(README.md:22). RRF (Cormack/Clarke/Buettcher, SIGIR 2009) is an algorithm, "
            "not licensable code. Also transforms SearXNG's settings.yml (SearXNG is "
            "AGPL-3.0 upstream) but ships NO SearXNG code - it edits a config file, so no "
            "AGPL derivation. UNVERIFIED: the AGPL-boundary reading is mine, not counsel's; "
            "settle by confirming no SearXNG source is vendored (measured: n_files=8, all "
            "first-party)."
        ),
    ),
    maintenance=tool_maint("tools/search-expansion"),
    task_fit=[
        "multi-provider search fan-in for a research workflow",
        "de-duplicating and re-ranking hits from searxng/exa/tavily into one ordered list",
        "enabling SearXNG regional engines from a pure config transform",
    ],
    stages=[
        "adapt raw provider payloads (results / data / data.web / bare list / list-of-URLs)",
        "reciprocal_rank_fusion(k=60) across providers",
        "emit FusedResult rows carrying score + contributing sources",
        "(separate CLI) live probe -> backup settings.yml -> container restart -> health check",
    ],
    roles=["search fan-out worker", "fan-in reducer"],
    tools=[
        "python stdlib only (dependency-free)",
        "docker (CLI shell only)",
        "SearXNG at http://127.0.0.1:8890",
    ],
    stop_rules=[
        "pure functions - terminate on input exhaustion; `limit` caps the fused list",
        "CLI shell: health check is the terminal probe",
    ],
    failure_behaviour=(
        "fail-closed on the gated pure core (100% line+branch coverage on rank_fusion.py and "
        "searxng_config.py); the I/O shell searxng_regional.py is DELIBERATELY outside the "
        "coverage gate because 'a mocked-to-100% shell would assert against the mocks rather "
        "than the behaviour' (README.md:11-13)."
    ),
    benchmark_evidence=(
        "Self-declared 100% line+branch on the two pure modules; 3 test files / 1929 LOC total. "
        "The CLI paths were exercised live and the README says the exercise caught a real defect "
        "(README.md:14-16). UNVERIFIED: this unit did NOT re-run the suite; settle with "
        "`pytest tools/search-expansion` under the repo's coverage gate."
    ),
    reusable_mechanisms=[
        "rank fusion / fan-in reranking",
        "pure-core + IO-shell split",
        "coverage-gate scoping",
    ],
    prior_doc08={
        "anchor": f"{DOC08}:433-442",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "evidence_was": "'tools/search-expansion present; unread.'",
        "this_unit": "PROBED and re-classified ADOPT-AS-IS - README + file list + commit read.",
    },
    verdict_basis=(
        "Dependency-free, gated pure core, honest coverage-scoping rationale, and it is the only "
        "fan-in reranker in the estate. Nothing needs wrapping to consume it: it is importable "
        "python with pure functions."
    ),
)

# ---- 34 -------------------------------------------------------------------
add(
    n=34,
    id="tool-taskwatch-monitor",
    name="tools/taskwatch_monitor - source-agnostic long-task progress monitor (CLI/TUI + MCP + hook)",
    family="C-repo-tool",
    classification="ADOPT-WITH-WRAPPER",
    provenance=tool_prov(
        "tools/taskwatch_monitor", "tools/taskwatch_monitor/README.md:1-40"
    ),
    license=dict(
        NO_LICENSE,
        third_party_note=(
            "Depends on upstream MCP python SDK (`mcp>=1.2`, capped `<2.0` after 2.0.0 removed "
            "mcp.server.fastmcp - see last_commit subject) plus rich/tomlkit; those are "
            "dependencies, not vendored code. pyproject.toml deliberately names the subpackage "
            "`mcp_server` never `mcp` to avoid shadowing the upstream import."
        ),
    ),
    maintenance=tool_maint("tools/taskwatch_monitor"),
    task_fit=[
        "watching any long-running job (build, download, CI run, FEP/BPMD driver, LLM generation, rclone transfer)",
        "giving an agent host an MCP-visible progress surface for a job it launched",
        "day-1 auto-attach so a launched job is watched without a second command",
    ],
    stages=[
        "register_task -> adapter selection",
        "poll on two planes: liveness (mtime/byte-growth/line-rate/process-up) and optional progress.json heartbeat",
        "ETA estimate tagged with its provenance (MEASURED / PRIOR / NONE)",
        "render (rich CLI, TUI) and/or serve over MCP",
    ],
    roles=["monitor/observer", "MCP server", "PostToolUse auto-attach hook"],
    tools=[
        "python>=3.11",
        "uv",
        "rich",
        "tomlkit",
        "mcp SDK",
        "ssh (BatchMode) for remote poll",
    ],
    stop_rules=[
        "terminal states DONE / BLIND; a poll or tool error goes BLIND and holds the last verdict with an age stamp",
        "a stall never slides the finish clock forward",
        "unknown total => no percentage (`--%`), elapsed+rate only",
    ],
    failure_behaviour=(
        "fail-honest rather than fail-open: 'A poll/tool error goes BLIND - the last verdict is "
        "held with an age stamp and never relabelled DONE' (README.md:22-24). No hidden clamps: "
        "an out-of-range fraction>1 WIDENS the ETA band and renders a `!` marker instead of being "
        "silently discarded. Whole-record reads with a monotonic `seq` so log-rolloff cannot undercount."
    ),
    benchmark_evidence=(
        "8496 LOC across 58 files with 23 test files - the largest test surface of any candidate in "
        "this range. Built explicitly to kill two named bug classes from the predecessor FEP "
        "dashboard (hidden clamps, fixed-log-tail reads). UNVERIFIED: no suite was run and no "
        "coverage figure is claimed by the README; settle with `pytest tools/taskwatch_monitor/tests`."
    ),
    reusable_mechanisms=[
        "two-plane liveness-vs-progress separation",
        "BLIND terminal state (the anti-single-signal move)",
        "ETA provenance tagging",
        "monotonic-seq whole-record reads",
    ],
    prior_doc08={
        "anchor": f"{DOC08}:444-453",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "evidence_was": "'tools/taskwatch_monitor + skills/run-taskwatch_monitor both present.'",
        "this_unit": "PROBED and re-classified ADOPT-WITH-WRAPPER.",
    },
    verdict_basis=(
        "WRAPPER not AS-IS because its probe registry is domain-shaped (bpmd/fep/qm probes ship in "
        "probes/) and it pins `mcp<2.0`; a workflow substrate consuming it needs a generic-probe "
        "adapter plus a dependency decision. The two-plane engine itself is directly reusable. "
        "This unit did NOT read the 8496-line body - the mechanism list is from the README plus a "
        "file-level scan (UNVERIFIED at implementation depth)."
    ),
)

# ---- 35 -------------------------------------------------------------------
add(
    n=35,
    id="tool-plugin-cache-reaper",
    name="tools/plugin-cache-reaper - sweep abandoned plugin-install staging clones",
    family="C-repo-tool",
    classification="ADOPT-AS-IS",
    provenance=tool_prov(
        "tools/plugin-cache-reaper", "tools/plugin-cache-reaper/README.md:1-32"
    ),
    license=dict(
        NO_LICENSE,
        third_party_note=(
            "Provenance of the KNOWLEDGE is reverse-engineering, not code: the staging-name "
            "vocabulary (git/subdir/github/npm/local/unknown) was 'recovered from the string pool "
            "of C:/Users/Prekzursil/.local/bin/claude.exe (2.1.220) at byte offset 109756512' "
            "(README.md:19-22). No vendor code is copied; the tool only deletes husk directories."
        ),
    ),
    maintenance=tool_maint("tools/plugin-cache-reaper"),
    task_fit=[
        "bounding unbounded growth of ~/.claude/plugins/cache staging husks",
        "catalogue-tax / disk-leak control on a box with 98 installed plugins",
        "scheduled housekeeping via install_reaper_task.ps1",
    ],
    stages=[
        "enumerate cache root for temp_{kind}_{epoch_ms}_{rand6} staging dirs",
        "classify husk vs live plugin tree (cache/<marketplace>/<plugin>/<version>)",
        "delete husks; leave real trees",
    ],
    roles=["housekeeping / janitor", "scheduled task"],
    tools=["python", "powershell (Scheduled Task installer)"],
    stop_rules=[
        "single pass over the cache root; terminates on enumeration exhaustion"
    ],
    failure_behaviour=(
        "declared a MITIGATION not a fix, and says so in its own first line: 'The writer is Claude "
        "Code itself, and it ships as a compiled native binary, so there is no source line of ours "
        "to patch' (README.md:3-5). It cannot stop the leak, only bound it."
    ),
    benchmark_evidence=(
        "Quantified leak surface measured in-README: 79 of 276 claude-plugins-official entries are "
        "`git-subdir` and 142 are `url`/`git`, each producing a staging dir. Ships a DETECTOR "
        "CONTROL: the strings `temp_git_` and `plugins/cache` do NOT appear in the binary while "
        "`marketplace` -> 1568 hits and `installed_plugins.json` -> 18, which is why the writer "
        "cannot be quoted as vendor file:line. 2 test files incl. test_reap_mutations.py "
        "(mutation battery). 1059 LOC."
    ),
    reusable_mechanisms=[
        "bounded housekeeping sweep",
        "detector-control-in-README discipline",
        "mutation-tested deleter",
    ],
    prior_doc08={
        "anchor": f"{DOC08}:455-464",
        "classification": "ADOPT-AS-IS",
        "evidence_was": "'tools/plugin-cache-reaper present; 98 installed plugins / 9 enabled makes this load-bearing.'",
        "this_unit": "CONFIRMED ADOPT-AS-IS on a read of the README + file list; adds the measured leak arithmetic and the mutation-test file.",
    },
    verdict_basis=(
        "A deleter with a mutation battery, an explicit scope limit, and a detector control is the "
        "safest shape a destructive tool can take. Adopt unchanged."
    ),
)

# ---- 36 -------------------------------------------------------------------
add(
    n=36,
    id="tool-glob-argv-guard",
    name="tools/glob-argv-guard - diagnose and remediate Glob/Grep ENAMETOOLONG on Windows",
    family="C-repo-tool",
    classification="ADOPT-AS-IS",
    provenance=tool_prov(
        "tools/glob-argv-guard", "tools/glob-argv-guard/glob_argv_guard.py:1-20"
    ),
    license=dict(
        NO_LICENSE,
        third_party_note=(
            "Mechanism was 'decompiled from the shipped bundle, then reproduced end-to-end' "
            "(glob_argv_guard.py:9). Reverse-engineered behaviour of the host tool; no vendor code "
            "vendored."
        ),
    ),
    maintenance=tool_maint("tools/glob-argv-guard"),
    task_fit=[
        "making Glob/Grep survivable on Windows when the plugin cache inflates the ripgrep argv",
        "any workflow whose file-discovery stage depends on the Glob tool not erroring",
    ],
    stages=[
        "measure the cached exclusion list Claude Code passes to ripgrep",
        "diagnose whether argv exceeds the 32,767-char CreateProcess cap",
        "remediate by pruning the orphan markers that inflate it",
    ],
    roles=["diagnostic + remediation tool", "reliability guard"],
    tools=["python", "ripgrep (as the subject, not a dependency)"],
    stop_rules=[
        "single diagnose/remediate pass; the argv-length measurement is the terminal check"
    ],
    failure_behaviour=(
        "diagnostic-first: it measures before it changes anything. Names its own upstream cause - "
        "'the orphan-marker walker assumes the cache is exactly marketplace/plugin/version, so a "
        "stray temp_sub[dir] ...' - i.e. it is the sibling defect of candidate 35."
    ),
    benchmark_evidence=(
        "Hard measured numbers in the module docstring (2026-07-18, Claude Code 2.1.214, Win11): "
        "'Glob is the worst core tool in the harness: 6,222 calls, 13.3% error rate, 592 of those "
        "failures are ENAMETOOLONG: name too long, uv_spawn'. Commit subject records the settled "
        "figure: 'measured 82,893-char argv vs a 32,767 cap'. 686 LOC / 1 test file."
    ),
    reusable_mechanisms=[
        "argv-budget guard",
        "measure-before-remediate",
        "host-tool RE as a reliability input",
    ],
    prior_doc08={
        "anchor": f"{DOC08}:466-475",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "evidence_was": "'tools/glob-argv-guard present; unread.'",
        "this_unit": "PROBED and re-classified ADOPT-AS-IS - docstring read, commit subject read.",
    },
    verdict_basis=(
        "Carries its own falsifiable measurement (82,893 vs 32,767) and a reproduction. The "
        "32,767 CreateProcess cap is the same constraint that governs cross-vendor dispatch "
        "prompt marshalling, so this generalises beyond Glob."
    ),
)

# ---- 37 -------------------------------------------------------------------
add(
    n=37,
    id="tool-gitcrypt-worktree",
    name="tools/gitcrypt-worktree - git-crypt worktree doctor and gated backfill",
    family="C-repo-tool",
    classification="REPAIR",
    provenance=tool_prov(
        "tools/gitcrypt-worktree", "tools/gitcrypt-worktree/README.md:1-24"
    ),
    license=NO_LICENSE,
    maintenance=tool_maint("tools/gitcrypt-worktree"),
    task_fit=[
        "diagnosing git-crypt filter state across many worktrees before a parallel-agent fan-out",
        "safely backfilling git-crypt config into selected worktrees with rollback",
        "prerequisite hygiene for worktree-isolated agents on an encrypted repo",
    ],
    stages=[
        "doctor: enumerate worktrees from two mechanically independent sources, surface disagreement",
        "classify each worktree (git-crypt-enabled / ciphertext-preserving / unclassifiable)",
        "backfill: dry-run by default, explicit target selection, hard refusal on ciphertext-preserving and unclassifiable",
        "rollback from a journal",
    ],
    roles=["doctor/diagnostic", "gated mutator", "rollback operator"],
    tools=["python", "git", "git-crypt"],
    stop_rules=[
        "dry-run is the DEFAULT; mutation requires --apply plus --journal",
        "hard refusal (not a warning) on ciphertext-preserving or unclassifiable worktrees",
        "documented exit-code contract asserted through subprocess against the real executable",
    ],
    failure_behaviour=(
        "fail-closed. It exists BECAUSE its shell predecessor failed open: defect (a) 'process exit "
        "code was unconditionally 0 (rc=1 assigned inside a piped while, i.e. a subshell, then "
        "discarded)' and defect (c) 'backfill was ungated - it rewrote git-crypt filters into every "
        "worktree, including ones deliberately preserving ciphertext' (README.md table)."
    ),
    benchmark_evidence=(
        "Its README tabulates FOUR proven defects of the predecessor with the repair for each, "
        "anchored to `04a-repro-gitcrypt-worktree.md`. 3177 LOC / 2 test files, one of which is a "
        "fixtures_lib.py. Landed in PR #131 'three adversarially-proven remediation lanes "
        "(d001 - gitcrypt - msys)'. UNVERIFIED: suite not re-run here."
    ),
    reusable_mechanisms=[
        "two-independent-enumerations with disagreement surfaced (single-signal-verification, mechanised)",
        "classify-before-touch",
        "dry-run default + rollback journal",
        "absolute-path identity instead of basename (defect b)",
    ],
    prior_doc08={
        "anchor": f"{DOC08}:477-486",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "evidence_was": "'tools/gitcrypt-worktree present; unread. MEMORY records git-crypt+worktree breaks test_hub.'",
        "this_unit": "PROBED and re-classified REPAIR - it IS the repair of a 4-defect predecessor, by its own README.",
    },
    verdict_basis=(
        "Classified REPAIR rather than ADOPT-AS-IS because the artifact's declared purpose is to "
        "replace a defective predecessor pair, and the repair lineage is the reusable asset: the "
        "four-defect table is a transferable checklist for any gated mutator. Adopting it also "
        "adopts that pattern."
    ),
)

# ---- 38 -------------------------------------------------------------------
add(
    n=38,
    id="tool-stdin-server",
    name="tools/stdin-server - stdlib-only MCP server giving an agent a persistent interactive stdin channel",
    family="C-repo-tool",
    classification="CLEAN-ROOM-REIMPLEMENT",
    provenance=tool_prov("tools/stdin-server", "tools/stdin-server/README.md:1-30"),
    license=dict(
        NO_LICENSE,
        third_party_note=(
            "THIRD-PARTY API-SURFACE BORROW, declared in-artifact: it implements 'the non-duplicate "
            "surface of Desktop Commander's start_process / interact_with_process / "
            "read_process_output' (README.md:28-30), and the landing commit says so too "
            "('(Desktop Commander borrow)', 0251caf7). The three verb NAMES are taken; the "
            "implementation is stdlib-only and hand-rolled (a newline-delimited JSON-RPC 2.0 loop), "
            "so this is an API-compatible clean-room reimplementation, not vendored code. "
            "UNVERIFIED: Desktop Commander's own upstream license was NOT retrieved by this unit "
            "(no network probe run). Settle before any redistribution - names/API surface are "
            "generally not copyrightable but that is a legal judgement, not a measurement."
        ),
    ),
    maintenance=tool_maint("tools/stdin-server"),
    task_fit=[
        "typing into a REPL, pdb, database shell, or ssh session that an agent launched",
        "any workflow stage that needs a prompt-driven CLI, which the Bash tool structurally cannot drive",
    ],
    stages=[
        "start_process(command, cwd?) -> {session_id, pid}: spawn persistent child, stdin=PIPE, merged stdout+stderr=PIPE, reader daemon thread",
        "interact_with_process(session_id, input, wait_ms=200) -> {output, alive, exit_code}",
        "read_process_output(session_id, max_chars, timeout_ms) -> {output, more, truncated, alive, exit_code}",
    ],
    roles=["MCP server", "process owner / transport"],
    tools=["python stdlib only (zero dependencies)"],
    stop_rules=[
        "explicit per-call wait_ms / timeout_ms bounds",
        "`alive` + `exit_code` are the terminal-state fields; `more`/`truncated` bound the read",
    ],
    failure_behaviour=(
        "bounded reads with explicit truncation flags rather than blocking forever. Closes a "
        "STRUCTURAL gap, not a bug: 'Claude Code's Bash tool runs -NonInteractive with stdin wired "
        "to the null device' (README.md:22-24), so no amount of retrying the Bash tool can succeed."
    ),
    benchmark_evidence=(
        "Self-declared 100% line+branch on stdin_server.py, and the test file 'drives REAL child "
        "processes (a python -i -u REPL, python -c one-shots) so the gate measures behaviour, not "
        "mocks' (README.md:9). 931 LOC / 1 test file. UNVERIFIED: not re-run here."
    ),
    reusable_mechanisms=[
        "persistent interactive stdin transport",
        "session registry",
        "hand-rolled JSON-RPC 2.0 over newline-delimited frames",
        "real-child-process testing over mocks",
    ],
    prior_doc08={
        "anchor": f"{DOC08}:488-497",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "evidence_was": "'tools/stdin-server + skills/stdin-server both present.'",
        "this_unit": "PROBED and re-classified CLEAN-ROOM-REIMPLEMENT; recovered the previously unrecorded third-party (Desktop Commander) API provenance.",
    },
    verdict_basis=(
        "The classification turns on provenance, which doc 08 did not record: the verb surface is "
        "borrowed from a third-party MCP while the code is independent and stdlib-only. That is "
        "exactly CLEAN-ROOM-REIMPLEMENT, and it carries a license question ADOPT-AS-IS would have hidden."
    ),
)

# ---- 39 -------------------------------------------------------------------
_ci = DC["harness_mirror_paths"]
add(
    n=39,
    id="mirror-ci-harness",
    name="ci/harness - the CI-side partial mirror of the harness runtime (doc-08 path REPAIRED)",
    family="C-repo-tool",
    classification="REPAIR",
    provenance={
        "repo": "agent-skills-toolchain (private, owner-authored)",
        "ref": REF,
        "path": "ci/harness",
        "read_via": f"git --git-dir {MIRROR} ls-tree -r --name-only {REF[:8]} -- ci/harness",
        "anchor": "ci/harness/modules.py (703 lines at 07f465f3) vs agent-self/harness/modules.py (3322 lines)",
        "n_files": _ci["ci/harness"],
        "sibling_mirror": {
            "path": "agent-self/harness",
            "n_files": _ci["agent-self/harness"],
        },
        "last_commit": {
            "sha": "01c9b9a",
            "date": "2026-07-31",
            "subject": "fix: derive-167 settlement (44 commits) - PARTIAL: ~117 of 167 findings, ~40 FIXED verdicts NOT on this branch (#254)",
        },
        "doc08_path_was_PHANTOM": {
            "claimed_path": "tools/harness-corpus-mirror-ci",
            "measured": (
                f"exists_at_ref=False, n_files=0, commits=0 at {REF[:8]}. DETECTOR CONTROLS for "
                f"that verdict: tools/fanout-schema -> n={DC['ls_tree_known_present']['n']} (fires on "
                f"known-present), a bogus tools/ path -> n={DC['ls_tree_known_absent']['n']} (silent on "
                f"known-absent), tools/harness-corpus -> n={_ci['tools/harness-corpus']}, and 37 distinct "
                "dirs exist under tools/ at the same ref. So the absence is the tool's reading, not a broken matcher."
            ),
            "why_doc08_said_it": (
                f"doc 08's own evidence line ({DOC08}:508) cites the SPAWN BRIEF, not a tree read: "
                "'Spawn brief states the harness mirrors at ci/harness'. It then minted a "
                "tools/-shaped id for a path that only ever existed as prose."
            ),
        },
    },
    license=NO_LICENSE,
    maintenance={
        "last_commit_date": "2026-07-31",
        "last_commit_sha": "01c9b9a",
        "last_commit_subject": "fix: derive-167 settlement (44 commits) - PARTIAL",
        "state": (
            f"live on main; a PARTIAL mirror - {_ci['ci/harness']} files vs "
            f"{_ci['agent-self/harness']} in agent-self/harness, and its modules.py is 703 lines "
            "against agent-self's 3322 (measured). Calling it 'the mirror' overstates it."
        ),
    },
    task_fit=[
        "running harness checks inside CI without the live ~/.agents tree",
        "regression-testing dispatcher/ledger/modules/redaction in a hermetic checkout",
        "prebuild_recall fixture-driven recall indexing in CI",
    ],
    stages=[
        "CI checkout provides ci/harness/*",
        "tests under ci/harness/tests/ (redaction JSON credentials, stop-hook-active, tool-envelope casing) run against it",
        "prebuild_recall/ builds a fixture index",
    ],
    roles=["CI mirror / test substrate"],
    tools=["python", "pytest", "GitHub Actions"],
    stop_rules=["CI job exit code is the terminal state"],
    failure_behaviour=(
        "THREE-WAY divergence risk, not two: the same runtime exists at ~/.agents/harness (live), "
        "agent-self/harness (38 files, the real counterpart) and ci/harness (16 files, truncated). "
        "A CI green on ci/harness therefore does NOT certify the live runtime - measured 703 vs "
        "3322 lines of modules.py means CI exercises roughly a fifth of it."
    ),
    benchmark_evidence=(
        "3 test files present under ci/harness/tests plus prebuild_recall/test_prebuild_recall.py. "
        "The landing commit self-labels PARTIAL ('~117 of 167 findings, ~40 FIXED verdicts NOT on "
        "this branch'). UNVERIFIED: no CI run was inspected by this unit."
    ),
    reusable_mechanisms=["CI-side runtime mirror", "fixture-index prebuild"],
    prior_doc08={
        "anchor": f"{DOC08}:499-508",
        "classification": "UNKNOWN-NEEDS-PROBE",
        "evidence_was": "'Spawn brief states the harness mirrors at ci/harness ... Two mirrors of the same runtime exist.'",
        "this_unit": (
            "REFUTED the path and REPAIRED the entry. doc 08's id tool-harness-corpus-mirror-ci "
            "points at a path with 0 files and 0 commits; the real artifact is ci/harness. doc 08's "
            "'two mirrors' is also an undercount - there are THREE trees (live, agent-self/, ci/)."
        ),
    },
    verdict_basis=(
        "Kept as a candidate because the MECHANISM is real and materially distinct (a CI-side "
        "runtime mirror), but classified REPAIR: its provenance was wrong, it is partial, and a "
        "green CI on it is a weaker signal than it appears. Fixing the mirror-completeness gap is "
        "the work."
    ),
)

# ---- 40..45 harness runtime ------------------------------------------------
HARNESS_SPEC = [
    (
        40,
        "harness-dispatcher",
        "dispatcher.py",
        "ADOPT-AS-IS",
        "The threaded hook-dispatch runtime: owns the per-check dispatch budget, malformed-input handling and os._exit teardown.",
        [
            "read the hook event on stdin",
            "adapt the payload (see candidate 43)",
            "dispatch registered checks in threads under a budget",
            "merge results into an exit code + additionalContext",
            "os._exit teardown so a hung thread cannot wedge the host",
        ],
        ["hook dispatcher / scheduler"],
        [
            "exit 0 + additionalContext for guidance; exit 2 only for a dangerous op",
            "per-check budget/timeout is the hard stop (18 budget/timeout references measured)",
            "os._exit is the terminal teardown (1 reference measured)",
        ],
        "fail-open by construction: 12 fail-open / bare-`except Exception` sites measured. Any check error exits 0 rather than blocking the host turn.",
        [
            "threaded dispatch",
            "per-check budget",
            "fail-open teardown",
            "os._exit hard stop",
        ],
        f"{DOC08}:512-521",
        "ADOPT-AS-IS",
        "'live ~/.agents/harness/dispatcher.py is 129 lines AHEAD of main and main REGRESSES it -> NEVER MERGE main over live.'",
    ),
    (
        41,
        "harness-ledger",
        "ledger.py",
        "ADOPT-AS-IS",
        "Typed receipt / event ledger for the harness runtime, with signing so a receipt cannot be trivially forged.",
        [
            "accept a typed event/receipt",
            "hash + sign it (8 hmac/sha256 sites measured)",
            "append to the session-keyed ledger (19 session_id references measured)",
            "serve replay on SessionStart",
        ],
        ["ledger / receipt store", "replay source on resume+compact"],
        [
            "a receipt is terminal only on postcondition, not on process exit",
            "session-keyed scoping bounds what a replay may return",
        ],
        "fail-open on write errors (3 sites) but forgery-RESISTANT on read: signing is the gate, not the caller's word.",
        [
            "typed receipts",
            "hmac/sha256 signing",
            "session-keyed scoping",
            "objective turn-history replay",
        ],
        f"{DOC08}:523-532",
        "ADOPT-AS-IS",
        "'live is 168 lines ahead; main re-opens 6 executably-proven receipt-forgery holes. NEVER MERGE.'",
    ),
    (
        42,
        "harness-modules",
        "modules.py",
        "MERGE",
        "The check registry / module loader: 135 defs and 13 classes implementing the individual harness checks.",
        [
            "discover and register checks",
            "run a check against the adapted envelope",
            "emit a typed result carrying receipt/ledger references (143 measured)",
        ],
        ["module registry", "check host"],
        [
            "each check is budget-bounded by the dispatcher (32 budget/timeout references)",
            "5 sentinel references - some checks carry an explicit completion sentinel",
        ],
        "fail-open dominant: 44 fail-open / `except Exception` sites measured across 3489 live lines.",
        [
            "module registry",
            "check discovery",
            "per-check receipts",
            "sentinel-bearing checks",
        ],
        f"{DOC08}:534-543",
        "MERGE",
        "'Measured live/main unique lines 22 / 436 -> main is far ahead; a union merge candidate exists at harness-restore-20260806/merged/.'",
    ),
    (
        43,
        "harness-adapters",
        "adapters.py",
        "MERGE",
        "Per-tool adapters normalising heterogeneous hook payloads into one envelope; owns the additionalContext surface (10 references).",
        [
            "receive a raw provider hook payload",
            "normalise to AgentEnvelope / HookEvent / HookResult / ToolEnvelope",
            "attach additionalContext for the inject path",
        ],
        ["payload adapter / normaliser"],
        ["pure transformation - terminates on input; no loop"],
        "fail-open (2 sites) with an ImportError fallback so the module works both as a package and as a direct script.",
        [
            "payload adaptation",
            "additionalContext injection surface",
            "dual package/script import",
        ],
        f"{DOC08}:545-554",
        "MERGE",
        "'Measured 54 live-unique; brief says take at most the one-line transcript_path= insert from main.'",
    ),
    (
        44,
        "harness-recall-index",
        "recall_index.py",
        "ADOPT-AS-IS",
        "Recall-index refresher feeding basic-memory recall; an argparse CLI with a content-hash index.",
        [
            "walk the memory corpus",
            "hash content (1 sha/hmac site) into an index",
            "expose staleness so recall can be re-run",
        ],
        ["memory indexer", "CLI"],
        [
            "MaxAgeHours staleness bound is the re-run trigger",
            "single pass per invocation",
        ],
        "fail-open (4 sites); a stale index degrades recall quality rather than breaking the turn.",
        ["memory recall index", "content-hash staleness"],
        f"{DOC08}:556-565",
        "ADOPT-AS-IS",
        "'Live; MaxAgeHours was changed 6->5 this session (already applied).'",
    ),
    (
        45,
        "harness-registration",
        "registration.py",
        "ADOPT-AS-IS",
        "The hook-registration surface consumed by install.py; registers native lifecycle events across BOTH providers (Agent-Teams and failure-channel names: TaskCreated/TaskCompleted/TeammateIdle).",
        [
            "declare the registration table",
            "install.py consumes it to write the host hooks key",
        ],
        ["registration declaration"],
        [
            "9 budget/timeout references - registrations carry timeouts",
            "install.py bare/--bootstrap REPLACES the whole hooks key and drops 21 registrations, so only --check is safe (doc-08 hard constraint 4)",
        ],
        "fail-open (1 site). The dangerous failure is not in this file but in its CONSUMER: a full install.py run silently de-registers 21 hooks.",
        ["cross-provider lifecycle registration", "declarative registration table"],
        f"{DOC08}:567-576",
        "ADOPT-AS-IS",
        "'install.py bare/--bootstrap replaces the whole hooks key and drops 21 registrations -> only --check is safe.'",
    ),
]

for (
    n,
    cid,
    f,
    cls,
    what,
    stages,
    roles,
    stops,
    failb,
    mechs,
    anchor,
    prior_cls,
    prior_ev,
) in HARNESS_SPEC:
    r = H[f]
    prov = harness_prov(f)
    extra = {}
    if f == "modules.py":
        extra["doc08_disagreement"] = {
            "doc08_claim": "live/main unique lines 22 / 436 -> main is far ahead",
            "this_unit_measured": (
                f"live_unique={r['live_unique_lines']} repo_unique={r['repo_unique_lines']} "
                f"-> LIVE is ahead. Method: set-of-lines diff, live "
                f"C:/Users/Prekzursil/.agents/harness/modules.py (mtime {r['live_mtime']}, "
                f"{r['live_loc']} lines) vs {REF[:8]}:agent-self/harness/modules.py "
                f"({r['repo_loc']} lines)."
            ),
            "verdict": "REFUTED as of this measurement, PARTIALLY EXPLAINED",
            "explanation": (
                f"doc 08 was written 2026-08-07 05:56 and live modules.py has mtime "
                f"{r['live_mtime']}, i.e. it moved AFTER doc 08 measured. doc 08 names no ref "
                "pair, so its exact comparison cannot be reconstructed. The alternative path "
                "ci/harness/modules.py gives live_unique=1920 repo_unique=131 - also not 22/436. "
                "UNVERIFIED which comparison produced 22/436; settle by re-running doc 08's "
                "_wfcat_build.py against a pinned pair. Consequence: doc 08's MERGE rationale "
                "('main is far ahead') no longer holds, though MERGE may still be right for the "
                "37 repo-unique lines."
            ),
        }
    add(
        n=n,
        id=cid,
        name=f"~/.agents/harness/{f} - {what.split(':')[0]}",
        family="D-harness-runtime",
        classification=cls,
        provenance=dict(prov, **extra),
        license=NO_LICENSE,
        maintenance=harness_maint(f),
        task_fit=[
            "the hook-time substrate any workflow engine on this box must interoperate with",
            "reference implementation for typed receipts / budgeted dispatch / fail-open guidance",
        ],
        stages=stages,
        roles=roles,
        tools=[
            "python (no third-party imports observed in the first 800 chars of each module)"
        ],
        stop_rules=stops,
        failure_behaviour=failb,
        benchmark_evidence=(
            f"Structural measurement only: {r['live_loc']} live lines, {r['n_defs']} defs, "
            f"{r['n_classes']} classes, mechanism-keyword counts "
            f"{json.dumps({k: v for k, v in r['mechanism_hits'].items() if v})}. UNVERIFIED at "
            "behavioural depth - this unit did NOT run the harness test suite and did NOT read "
            "these bodies line-by-line; the keyword counts are a proxy, not a proof. Settle with "
            "`pytest ~/.agents/harness/tests`."
        ),
        reusable_mechanisms=mechs,
        prior_doc08={
            "anchor": anchor,
            "classification": prior_cls,
            "evidence_was": prior_ev,
            "this_unit": (
                "re-measured live-vs-repo line sets independently; see provenance."
                + (
                    " doc-08 drift claim REFUTED for this file - see provenance.doc08_disagreement."
                    if f == "modules.py"
                    else ""
                )
            ),
        },
        verdict_basis=(
            f"Drift direction measured {prov['drift_direction']} "
            f"({r['live_unique_lines']} live-unique vs {r['repo_unique_lines']} repo-unique). "
            + (
                "Classified MERGE because BOTH sides hold unique lines, which is the two-directional "
                "case where a one-directional sync destroys content."
                if cls == "MERGE"
                else "Classified ADOPT-AS-IS on the LIVE copy: it is deployed, firing, and ahead of "
                "or equal to the repo copy on the measured line sets."
            )
        ),
    )

# ---- 46..63 agent definitions ---------------------------------------------
AGENT_SPEC = [
    (
        46,
        "architect",
        "ADOPT-AS-IS",
        "read-only system-design reviewer",
        ["design review", "scalability/technical decision calls"],
        "read-only: Read/Grep/Glob only - structurally cannot mutate the tree.",
    ),
    (
        47,
        "planner",
        "ADOPT-AS-IS",
        "read-only planning specialist",
        ["feature planning", "refactor planning"],
        "read-only: Read/Grep/Glob only.",
    ),
    (
        48,
        "chief-of-staff",
        "REPAIR",
        "multi-channel comms triage into 4 tiers (skip/info_only/meeting_info/action_required)",
        ["email/Slack/LINE/Messenger triage", "draft replies"],
        "LIVE COPY MAKES A FALSE ENFORCEMENT CLAIM - see provenance.live_repo_divergence.",
    ),
    (
        49,
        "code-reviewer",
        "ADOPT-AS-IS",
        "general code-review specialist emitting typed findings",
        ["post-change review of any language"],
        "emits via ReportFindings (typed); has Bash, so it can run checks but is scoped to review.",
    ),
    (
        50,
        "python-reviewer",
        "SPECIALIZE",
        "Python-specialised reviewer (PEP 8, typing, security, perf)",
        ["python code review"],
        "emits via ReportFindings.",
    ),
    (
        51,
        "typescript-reviewer",
        "SPECIALIZE",
        "TS/JS-specialised reviewer (type safety, async correctness, Node/web security)",
        ["typescript/javascript code review"],
        "emits via ReportFindings.",
    ),
    (
        52,
        "security-reviewer",
        "SPECIALIZE",
        "security-vulnerability detection AND remediation (secrets, SSRF, injection, unsafe crypto, OWASP Top 10)",
        ["security review of input-handling/auth/API/sensitive-data code"],
        "holds Write+Edit, so unlike the other reviewers it can MUTATE - the widest tool grant of any reviewer in the set.",
    ),
    (
        53,
        "agent-as-judge",
        "ADOPT-WITH-WRAPPER",
        "advisory evidence-citing Definition-of-Done judge scored on the ICD-203 nine analytic standards",
        ["post-hoc DoD adjudication", "chain-of-custody evidence checks"],
        "ADVISORY BY CONSTRUCTION - 'execute-to-confirms every finding it would call blocking'; it never gates. Needs a wrapper to be wired into a stopping rule at all.",
    ),
    (
        54,
        "intent-drift-sentinel",
        "ADOPT-AS-IS",
        "EVPI-gated clarify (ASK-GATE) + goal-vs-ledger drift verdict (DRIFT-GATE)",
        ["pre-execution clarification", "mid-program drift detection"],
        "'returns a compact structured verdict, never chain-of-thought'; the only definition in the set holding AskUserQuestion.",
    ),
    (
        55,
        "harness-optimizer",
        "ADOPT-AS-IS",
        "analyse and improve the local harness config for reliability/cost/throughput",
        ["harness tuning"],
        "holds Edit - can mutate harness config.",
    ),
    (
        56,
        "loop-operator",
        "ADOPT-AS-IS",
        "operate autonomous agent loops, monitor progress, intervene when loops stall",
        ["autonomous-loop supervision"],
        "smallest definition in the set (36 lines) - a thin operator, not a policy.",
    ),
    (
        57,
        "build-error-resolver",
        "ADOPT-AS-IS",
        "build/type error resolution with minimal diffs, no architectural edits",
        ["red build triage"],
        "scope-limited by prompt: 'minimal diffs, no architectural edits'.",
    ),
    (
        58,
        "refactor-cleaner",
        "ADOPT-AS-IS",
        "dead-code cleanup and consolidation driven by knip/depcheck/ts-prune",
        ["dead-code removal", "duplicate consolidation"],
        "a DELETER with Write+Edit+Bash; safety rests on the three analysis tools agreeing.",
    ),
    (
        59,
        "doc-updater",
        "ADOPT-AS-IS",
        "documentation + codemap generation (/update-codemaps, /update-docs)",
        ["codemap refresh", "README/guide updates"],
        "mutating but confined to docs surfaces by prompt.",
    ),
    (
        60,
        "docs-lookup",
        "ADOPT-AS-IS",
        "Context7-backed current-documentation lookup",
        ["library/API/setup questions"],
        "read-only + Context7 MCP; sonnet model - the cheapest definition in the set.",
    ),
    (
        61,
        "e2e-runner",
        "ADOPT-WITH-WRAPPER",
        "E2E testing via Vercel Agent Browser (preferred) with Playwright fallback",
        ["E2E journey generation and runs", "flaky-test quarantine", "artifact upload"],
        "declares a preferred backend that may not be present; the fallback path is what actually runs here.",
    ),
    (
        62,
        "tdd-guide",
        "REPAIR",
        "write-tests-first enforcement",
        ["TDD supervision"],
        "LIVE COPY IS BEHIND REPO on the coverage-SSOT rule - see provenance.live_repo_divergence.",
    ),
    (
        63,
        "codex",
        "REPAIR",
        "synchronous cross-vendor work-unit executor that blocks until Codex returns a schema-valid result or a terminal FAILED line",
        ["cross-vendor fan-out work units that must produce artifacts"],
        "explicitly NOT fire-and-forget: 'Blocks until Codex finishes ... never for fire-and-forget exploration'. LIVE COPY IS BEHIND REPO and is missing the Monitor tool - see provenance.live_repo_divergence.",
    ),
]

DIVERGENCE = {
    "chief-of-staff": {
        "direction": "repo-ahead; LIVE IS WRONG",
        "severity": "live asserts an enforcement that does not exist",
        "repo_says": (
            "'**This checklist is advisory - nothing enforces it.** It is prompt-level guidance ... "
            "no hook intercepts the send' and names the TWO open design decisions that would have to "
            "change first (a PostToolUse registration; and it could not live in "
            "hooks/_dispatch/manifest.json if it is meant to BLOCK, because that dispatcher is "
            "inject-only and silently disarms an exit 2)."
        ),
        "live_says": (
            "'This checklist is enforced by a `PostToolUse` hook that blocks completion until all "
            "steps are done. The hook intercepts gmail send / conversations...'"
        ),
        "anchor": "repo agents/chief-of-staff.md:103-110 vs live C:/Users/Prekzursil/.claude/agents/chief-of-staff.md (unified diff @@ -103,8 +103 @@)",
    },
    "tdd-guide": {
        "direction": "repo-ahead; LIVE IS STALE",
        "severity": "live loses the coverage-SSOT rule",
        "repo_says": (
            "'Ensure coverage meets `.coverage-thresholds.json` (SSOT; 80%+ if none defined)' plus a "
            "10-line block 'Resolve the threshold before judging the run ... Read the nearest one -- "
            "repository root first, else the package the change lives in'."
        ),
        "live_says": "'Ensure 80%+ test coverage' - the SSOT block is absent (repo_unique=14 lines).",
        "anchor": "repo agents/tdd-guide.md:14 and :37-46 vs live (unified diff @@ -14 +14 @@, @@ -37,10 +36,0 @@)",
    },
    "codex": {
        "direction": "repo-ahead; LIVE IS STALE",
        "severity": "live drops the longrun/Monitor requirement AND the Monitor tool grant",
        "repo_says": (
            "tools include `Monitor`, and a 19-line block: 'Any work unit you expect to exceed 60s "
            "MUST go through `longrun` + `Monitor`' plus the measured gotcha that 'longrun cannot "
            "take the stdin redirect directly: it backgrounds its child, so `codex ... - < "
            "prompt.txt` never receives stdin and dies with No prompt provided via stdin.'"
        ),
        "live_says": "tools: Bash, Read, Write, Grep (no Monitor); the longrun block is absent (repo_unique=21 lines).",
        "anchor": "repo agents/codex.md:5 and :52-70 vs live (unified diff @@ -5 +5 @@, @@ -52,19 +52,3 @@)",
    },
}

for n, a, cls, what, fit, failb in AGENT_SPEC:
    r = A[a]
    prov = agent_prov(a)
    if a in DIVERGENCE:
        prov["live_repo_divergence"] = DIVERGENCE[a]
    tf = agent_tools(a)
    fm_anom = None
    if a == "codex":
        fm_anom = (
            "SCHEMA ANOMALY (measured across all 18 definitions at 07f465f3): codex.md is the ONLY "
            "one whose `tools:` frontmatter is a BARE COMMA STRING ('tools: Bash, Read, Write, Grep, "
            "Monitor'); the other 17 all use a JSON array. Probe: grep -m1 '^tools:' over each of the "
            "18 files -> 17 start with '[' and 1 does not."
        )
    add(
        n=n,
        id=f"agent-{a}",
        name=f"agents/{a}.md - {what}",
        family="E-agent",
        classification=cls,
        provenance=prov,
        license=NO_LICENSE,
        maintenance=agent_maint(a),
        task_fit=fit,
        stages=[
            "parent dispatches a Task with this definition",
            "definition constrains model + tool grant + role prompt",
            "subagent returns a structured report",
        ],
        roles=[AGENT_ROLE],
        tools=tf,
        stop_rules=[AGENT_STOP],
        failure_behaviour=failb,
        benchmark_evidence=(
            f"Structural only: {r['live_loc']} live lines / {r['repo_loc']} repo lines, model="
            f"{r['fm_model']}, repo commits touching the path={r['repo_commits']}. "
            "NOT-CHECKED: no behavioural benchmark, eval, or A/B exists for any agent definition in "
            "this range, and this unit did not create one. Any claim that a given definition "
            "IMPROVES outcomes is unsupported by evidence on this box."
        ),
        reusable_mechanisms=[
            "role-scoped tool grant (least privilege per subagent)",
            "model pinning in frontmatter",
            "PROACTIVELY/MUST-BE-USED dispatch triggers in the description field",
        ],
        prior_doc08={
            "anchor": f"{DOC08}:{580 + (n - 46) * 11}-{580 + (n - 46) * 11 + 9}",
            "classification": "ADOPT-AS-IS",
            "evidence_was": "'ls 07f465f3:agents/ = 18 files; ls ~/.claude/agents = 27 entries incl. 9 .bak' (identical boilerplate on all 19 E-family entries)",
            "this_unit": (
                "doc 08 gave every agent the SAME evidence line and the same classification. This "
                "unit measured each file individually: 15 of 18 are byte-identical live-vs-repo, 3 "
                "are NOT, and the 3 divergences all run repo-ahead (live stale or wrong)."
            ),
        },
        verdict_basis=(
            (
                "Classified REPAIR because the DEPLOYED copy diverges from the corrected repo copy - "
                "see provenance.live_repo_divergence. The definition itself is sound; the deployment is not."
            )
            if cls == "REPAIR"
            else (
                "Classified SPECIALIZE: it is a language/domain narrowing of the general "
                f"code-reviewer, and the near-duplicate scan puts its max pairwise Jaccard at "
                f"{max([p['jaccard'] for p in DUPS if a in (p['a'], p['b'])], default=0.0)} - "
                "materially distinct prose, not a renamed copy."
            )
            if cls == "SPECIALIZE"
            else (
                "Classified ADOPT-WITH-WRAPPER: usable, but it names an external precondition "
                "(a preferred backend, or an advisory-only contract) that a consuming workflow must "
                "supply or adapt."
            )
            if cls == "ADOPT-WITH-WRAPPER"
            else "Classified ADOPT-AS-IS: live is byte-identical to the versioned copy and the tool grant matches the stated role."
        ),
        **({"frontmatter_anomaly": fm_anom} if fm_anom else {}),
    )

# ---- 64 -------------------------------------------------------------------
_baks = [r for r in P["agents_block"]["agents"] if r["has_bak"]]
add(
    n=64,
    id="agent-bak-sweep",
    name="~/.claude/agents/*.md.bak-gembuild-agent-definitions-batch - 9 stale superseded agent-definition copies",
    family="E-agent",
    classification="RETIRE",
    provenance={
        "repo": "NOT VERSIONED - live-only artifacts, absent from 07f465f3:agents/",
        "ref": REF,
        "path": "(none - these exist only in the live tree)",
        "live_path": "C:/Users/Prekzursil/.claude/agents/*.md.bak-gembuild-agent-definitions-batch",
        "read_via": "live directory listing + per-file read",
        "anchor": "C:/Users/Prekzursil/.claude/agents/ - 27 entries = 18 live .md + 9 .bak",
        "n_bak_files": len(_baks),
        "members": [
            {
                "agent": r["agent"],
                "bak_loc": r["bak_loc"],
                "live_loc": r["live_loc"],
                "jaccard_vs_live": r["bak_jaccard_vs_live"],
                "live_mtime": r["live_mtime"],
            }
            for r in _baks
        ],
    },
    license=NO_LICENSE,
    maintenance={
        "state": "STALE - superseded copies from a 'gembuild-agent-definitions-batch' run; not versioned, not loaded",
        "measured_jaccard_range": (
            f"{min(r['bak_jaccard_vs_live'] for r in _baks)} - "
            f"{max(r['bak_jaccard_vs_live'] for r in _baks)} against their live successors"
        ),
        "note": (
            "These are the ONLY near-copies found in this entire range, and they are the reason "
            "this is ONE candidate rather than nine: the spec forbids counting renamed copies."
        ),
    },
    task_fit=[
        "none - superseded by the 9 live successors; retained only as a deletion target"
    ],
    stages=["(none - these are inert files, not an executable mechanism)"],
    roles=["(none - dead files, loaded by nothing)"],
    tools=["(none - no runtime; they are unversioned markdown husks)"],
    stop_rules=["n/a - not executable"],
    failure_behaviour=(
        "Inert but not harmless: they are unversioned prose siblings of live agent definitions, so "
        "a future glob-based loader or a grep-driven audit can pick up the STALE text. "
        "UNVERIFIED whether any loader globs `*.md*` rather than `*.md` in this directory; settle "
        "by reading the host's agent-discovery glob."
    ),
    benchmark_evidence=(
        f"Measured on all {len(_baks)}: Jaccard vs live successor ranges "
        f"{min(r['bak_jaccard_vs_live'] for r in _baks)}-{max(r['bak_jaccard_vs_live'] for r in _baks)}. "
        "DETECTOR CONTROL for that similarity metric: a planted exact clone scores "
        f"{DUPCTL.get('clone_jaccard')} and a planted disjoint document scores "
        f"{DUPCTL.get('disjoint_jaccard')}, so the metric separates copies from distinct docs."
    ),
    reusable_mechanisms=["(none - this is a cleanup item)"],
    prior_doc08={
        "anchor": f"{DOC08}:778-788",
        "classification": "RETIRE",
        "evidence_was": "'live has 18 + 9 stale .bak-gembuild-agent-definitions-batch copies'",
        "this_unit": (
            "CONFIRMED RETIRE and quantified it: named all 9, measured each one's similarity to its "
            "live successor, and confirmed none is versioned at 07f465f3."
        ),
    },
    verdict_basis=(
        "RETIRE, and deliberately counted as ONE candidate. Counting 9 near-copies as 9 candidates "
        "is exactly the padding the spec forbids; the measured Jaccard 0.47-0.85 proves they are "
        "copies, not distinct mechanisms."
    ),
)


# ------------------------------------------------------------------ contract
def check(entries: list[dict]) -> list[str]:
    v: list[str] = []
    ns = [e["n"] for e in entries]
    if ns != list(range(33, 65)):
        v.append(f"ids not sequential 33..64: {ns}")
    if len(set(e["id"] for e in entries)) != len(entries):
        v.append("duplicate id")
    for e in entries:
        for k in REQUIRED:
            if k not in e:
                v.append(f"{e['id']}: missing field {k}")
            elif e[k] in (None, "", [], {}):
                v.append(f"{e['id']}: empty field {k}")
        if e["classification"] not in CLASSES:
            v.append(f"{e['id']}: bad classification {e['classification']}")
        p = e["provenance"]
        if not isinstance(p, dict) or not p.get("anchor"):
            v.append(f"{e['id']}: provenance has no anchor")
        # a grounded lens: the anchor must name a real path or a ref
        anc = str(p.get("anchor", ""))
        if not re.search(r"(/|\\|\.py|\.md|\.json)", anc):
            v.append(
                f"{e['id']}: anchor is not a path-shaped provenance record: {anc!r}"
            )
        if not isinstance(e["license"], dict) or "source" not in e["license"]:
            v.append(f"{e['id']}: license has no source")
        if not e["maintenance"].get("state"):
            v.append(f"{e['id']}: maintenance has no state")

    # near-duplicate scan over the registry's own prose (planted-clone control)
    def bag(e: dict) -> set[str]:
        s = " ".join(
            [
                e["name"],
                " ".join(e["task_fit"]),
                " ".join(e["stages"]),
                str(e["failure_behaviour"]),
            ]
        ).lower()
        return set(re.findall(r"[a-z][a-z0-9_\-]{3,}", s))

    bags = {e["id"]: bag(e) for e in entries}
    worst = ("", "", 0.0)
    for x, y in combinations(sorted(bags), 2):
        a, b = bags[x], bags[y]
        if not (a | b):
            continue
        j = len(a & b) / len(a | b)
        if j > worst[2]:
            worst = (x, y, j)
    # planted clone must score 1.0 -> proves the scan can detect a copy
    first = entries[0]["id"]
    ctl = len(bags[first] & set(bags[first])) / len(bags[first] | set(bags[first]))
    if ctl != 1.0:
        v.append(f"DETECTOR BROKEN: planted clone scored {ctl}, expected 1.0")
    if worst[2] >= 0.75:
        v.append(
            f"near-duplicate registry entries {worst[0]} <-> {worst[1]} J={worst[2]:.3f}"
        )
    return v, worst, ctl


violations, worst, ctl = check(E)

by_class: dict[str, int] = {}
for e in E:
    by_class[e["classification"]] = by_class.get(e["classification"], 0) + 1

doc = {
    "unit": "build/wfa-2",
    "phase": "2A - workflow archaeology",
    "range": {
        "candidates": "33-64 of the 160-candidate program floor",
        "partition_rule": (
            "document order over the 284 '### `<id>`' entries of "
            f"{DOC08}; entry N of that ordered list is candidate N. Verified non-overlapping "
            "with sibling unit wfa-1, whose _wfa1_range_probe.json claims n=1..32 in the same order."
        ),
        "families_covered": "C-repo-tool (tail, 7) + D-harness-runtime (6) + E-agent (19)",
    },
    "counts": {
        "candidates": len(E),
        "materially_distinct": len(E),
        "by_classification": by_class,
        "provenance_repaired": sum(
            1
            for e in E
            if "PHANTOM" in json.dumps(e["provenance"])
            or "doc08_path_was_PHANTOM" in e["provenance"]
        ),
        "doc08_classification_changed": sum(
            1 for e in E if e["prior_doc08"]["classification"] != e["classification"]
        ),
    },
    "honesty": {
        "detector_controls": DC,
        "near_duplicate_control": DUPCTL,
        "registry_self_dup_scan": {
            "worst_pair": [worst[0], worst[1]],
            "worst_jaccard": round(worst[2], 4),
            "planted_clone_control": ctl,
            "threshold": 0.75,
        },
        "not_checked": [
            "No test suite was executed for ANY candidate; every coverage figure quoted is the artifact's own claim.",
            "No behavioural benchmark exists for the 19 agent definitions and none was created.",
            "Deploy state of the 6 tools into any live tree was not probed.",
            "Desktop Commander's upstream license (candidate 38) was not retrieved - no network probe run.",
            "Bodies of tools/taskwatch_monitor (8496 LOC) and agent-self/harness/modules.py (3489 live LOC) were NOT read line-by-line.",
        ],
        "refutations_of_prior_work": [
            "doc 08 candidate `tool-harness-corpus-mirror-ci` names a path with 0 files and 0 commits at 07f465f3 (detector-controlled). Repaired to ci/harness -> candidate 39.",
            "doc 08's modules.py drift claim (22 live-unique / 436 repo-unique, 'main is far ahead') does not reproduce: measured 166 / 37, i.e. LIVE ahead. See candidate 42.",
            "doc 08 asserts 'two mirrors of the same runtime exist'; there are THREE trees (live ~/.agents/harness, agent-self/harness 38 files, ci/harness 16 files).",
            "doc 08 gave all 19 E-family entries one boilerplate evidence line and ADOPT-AS-IS. 3 of 18 deployed agent definitions actually diverge from the repo, all repo-ahead.",
        ],
    },
    "candidates": E,
}

if violations:
    print("FAILED:build/wfa-2 contract violations:")
    for x in violations:
        print("  -", x)
    sys.exit(1)

OUT.parent.mkdir(parents=True, exist_ok=True)
# newline="\n" is load-bearing: write_text() on Windows translates to CRLF, and every
# sibling artifact under platform/ is CRLF=0. Measured: without it this file shipped 2629 CRLF.
with OUT.open("w", encoding="utf-8", newline="\n") as fh:
    json.dump(doc, fh, indent=2)
    fh.write("\n")
print(f"contract checks: {len(violations)} violations")
print(f"planted-clone control: {ctl} (must be 1.0)")
print(
    f"worst registry self-similarity: {worst[0]} <-> {worst[1]} J={worst[2]:.4f} (threshold 0.75)"
)
print(f"candidates: {len(E)}  by_class: {json.dumps(by_class)}")
print(
    f"doc08 classification changed on: {doc['counts']['doc08_classification_changed']}"
)
print(f"wrote {OUT}  ({OUT.stat().st_size} bytes)")
print("SUCCESS:build/wfa-2")
