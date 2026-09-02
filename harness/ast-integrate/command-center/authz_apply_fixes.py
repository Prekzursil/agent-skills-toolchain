#!/usr/bin/env python
"""Apply the D2 authorization fixes to WORK-UNIT-CATALOG.json. Idempotent; reports every edit.

Four edit classes, each recorded with WHY in D2-WORKUNIT-AUTHZ.md:

  A. add the root ``tool_policy`` block (the SAME `$defs/tool_policy` shape the DSL plane
     uses - there is deliberately no second policy document);
  B. record approval on the 23 units that hold ``Task`` unapproved (SEM-009). The tool is
     legitimately needed by all 23 - they are council fan-out sweeps - so the fix is to
     RECORD the approval, not to strip the tool;
  C. expand the 10 wildcard ``mcp__`` grants across 9 units into the specific tools each
     unit needs (SEM-011). Strictly a NARROWING;
  D. correct ``execution_substrate`` on the 2 units that declare a remote substrate while
     holding the session-local ``Task`` (SEM-010).

Writes back with the file's existing serialization: json indent=1, sort_keys=False,
ensure_ascii=False, no trailing newline, CRLF line endings (the working-tree form; git
stores LF - never hash the working-tree bytes, see rules/common/windows-shell.md 8b).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

# --------------------------------------------------------------------------- A. policy

# The authorization plane for the work-unit plane, consumed by
# platform/lib/wfdsl/semantics.py::check_work_unit_authorization (SEM-008..SEM-011). SAME
# document shape as workflow-dsl.schema.json#/$defs/tool_policy - the DSL plane and the
# work-unit plane share ONE authorization vocabulary on purpose; a second policy file would be
# a duplicate control plane (platform/architecture/TOURNAMENT-VERDICT.md 1.1/3.1, G4).
# `allow` is enumerated from the tools the 2,007 units actually request, so a NEW tool is a
# deliberate edit here rather than a silent widening. `deny` wins over `allow`.
#
# NOTE the rationale lives HERE and not in the JSON: `$defs/tool_policy` declares
# additionalProperties:false, so a `$comment` key inside the instance fails container
# validation. Measured, both states: with `$comment` -> 1 error
# ("Additional properties are not allowed ('$comment' was unexpected)"); without -> 0.
TOOL_POLICY: dict[str, Any] = {
    "default": "deny",
    "allow": [
        # native session tools
        "AskUserQuestion",
        "Bash",
        "Edit",
        "Glob",
        "Grep",
        "Monitor",
        "PowerShell",
        "Read",
        "Task",
        "WebFetch",
        "WebSearch",
        "Write",
        # mcp: one entry per tool actually requested. No family wildcards - SEM-011
        # requires a unit to name a specific tool, and an allowlist of families would
        # make that rule unenforceable in practice.
        "mcp__agent-mail__fetch_inbox",
        "mcp__agent-mail__file_reservation_paths",
        "mcp__agent-mail__send_message",
        "mcp__basic-memory__edit_note",
        "mcp__basic-memory__read_note",
        "mcp__basic-memory__recent_activity",
        "mcp__basic-memory__search_notes",
        "mcp__basic-memory__write_note",
        "mcp__brightdata__scrape_as_markdown",
        "mcp__brightdata__search_engine",
        "mcp__cloud-hub__modal_sandbox_create",
        "mcp__cloud-hub__modal_sandbox_exec",
        "mcp__cloud-hub__modal_sandbox_read_file",
        "mcp__cloud-hub__modal_sandbox_terminate",
        "mcp__codex__codex",
        "mcp__codex__codex-reply",
        "mcp__context7__query-docs",
        "mcp__context7__resolve-library-id",
        "mcp__deepwiki__ask_question",
        "mcp__figma__generate_diagram",
        "mcp__github__get_file_contents",
        "mcp__github__issue_read",
        "mcp__github__list_branches",
        "mcp__github__list_commits",
        "mcp__github__list_pull_requests",
        "mcp__github__list_releases",
        "mcp__github__pull_request_read",
        "mcp__github__search_code",
        "mcp__github__search_issues",
        "mcp__github__search_pull_requests",
        "mcp__github__search_repositories",
        "mcp__paper-search__read_arxiv_paper",
        "mcp__paper-search__search_arxiv",
        "mcp__paper-search__search_openalex",
        "mcp__paper-search__search_semantic",
        "mcp__qlty__qlty_check",
        "mcp__repomix__pack_remote_repository",
        "mcp__scholarly-access__paper_find_oa_pdf",
        "mcp__scholarly-access__paper_resolve",
        "mcp__search-hub__firecrawl_crawl",
        "mcp__search-hub__firecrawl_map",
        "mcp__search-hub__firecrawl_scrape",
        "mcp__search-hub__tavily_search",
        "mcp__search-hub__web_search_exa",
        "mcp__searxng__searxng_web_search",
    ],
    "deny": [
        # AGENTS.md 9: an agent never adds, removes, switches or reads a credential.
        "mcp__cloud-hub__az_account_add",
        "mcp__cloud-hub__az_account_remove",
        "mcp__cloud-hub__az_account_switch",
        "mcp__cloud-hub__db_account_add",
        "mcp__cloud-hub__db_account_remove",
        "mcp__cloud-hub__db_account_switch",
        "mcp__cloud-hub__dbx_secret_get",
        "mcp__cloud-hub__dbx_secret_put",
        "mcp__cloud-hub__gc_account_add",
        "mcp__cloud-hub__gc_account_remove",
        "mcp__cloud-hub__gc_account_switch",
        # Release mode is PR-ONLY and binding: no unit may merge or push to a branch.
        "mcp__github__create_or_update_file",
        "mcp__github__delete_file",
        "mcp__github__merge_pull_request",
        "mcp__github__push_files",
        # Irreversible destruction of owner state.
        "mcp__agent-mail__hard_delete_agent",
        "mcp__agent-mail__hard_delete_project",
        "mcp__basic-memory__delete_note",
        "mcp__basic-memory__delete_project",
    ],
    "require_owner_approval": [
        # Task spawns subagents that act with the unit's own permissions and spend the
        # owner's quota. Also hardcoded in semantics.APPROVAL_FLOOR_TOOLS so loosening
        # this list cannot un-gate it.
        "Task",
        # AskUserQuestion interrupts the owner; all 3 holders already declare approval.
        "AskUserQuestion",
    ],
    "network": "read-only",
    "source_policy": {
        "offline_only": False,
        "require_provenance": True,
        "treat_fetched_content_as_data": True,
    },
}

# ------------------------------------------------------------------- C. mcp expansions

#: read-only retrieval surface of search-hub. Excludes firecrawl_crawl (a whole-site
#: crawl is not "read-only retrieval" at the same cost), every *_agent / monitor_* /
#: account_* tool, and anything that writes.
SEARCH_HUB_READONLY = [
    "mcp__search-hub__web_search_exa",
    "mcp__search-hub__tavily_search",
    "mcp__search-hub__firecrawl_scrape",
    "mcp__search-hub__firecrawl_map",
]
#: the four paper-search tools the rest of the corpus already names explicitly
PAPER_SEARCH = [
    "mcp__paper-search__search_arxiv",
    "mcp__paper-search__search_semantic",
    "mcp__paper-search__search_openalex",
    "mcp__paper-search__read_arxiv_paper",
]
#: the two scholarly-access tools the rest of the corpus already names explicitly
SCHOLARLY = [
    "mcp__scholarly-access__paper_resolve",
    "mcp__scholarly-access__paper_find_oa_pdf",
]

EXPANSIONS: dict[str, list[str]] = {
    "mcp__search-hub__* (read-only retrieval)": SEARCH_HUB_READONLY,
    "mcp__paper-search__*": PAPER_SEARCH,
    "mcp__scholarly-access__*": SCHOLARLY,
}

# ------------------------------------------------------------------ D. substrate fixes

#: A remote batch runner has no attached session, so `Task` cannot be honoured there.
#: Both units are fan-out sweeps (64 presets / 48 blueprints) whose own text mandates a
#: sampled live-model arm - that arm IS the Task dispatch, so the coherent correction is
#: the substrate, not deleting the tool. Flagged for owner review as a plan edit.
SUBSTRATE_FIXES: dict[str, tuple[str, str]] = {
    "TST-0293": ("cloud-batch", "local-parallel"),
    "TST-0294": ("cloud-batch", "local-parallel"),
}


def base_of(token: str) -> str:
    return str(token).split("(", 1)[0].strip().split(":", 1)[0]


def main() -> int:
    raw = CATALOG.read_bytes()
    catalog = json.loads(raw.replace(b"\r\n", b"\n").decode("utf-8"))
    units = catalog["work_units"]
    changes: list[str] = []

    # A ----------------------------------------------------------------------------
    if catalog.get("tool_policy") != TOOL_POLICY:
        rebuilt: dict[str, Any] = {}
        for key in sorted({*catalog, "tool_policy"}):
            rebuilt[key] = TOOL_POLICY if key == "tool_policy" else catalog[key]
        catalog = rebuilt
        units = catalog["work_units"]
        changes.append(
            f"A root tool_policy: default=deny allow={len(TOOL_POLICY['allow'])} "
            f"deny={len(TOOL_POLICY['deny'])} "
            f"require_owner_approval={TOOL_POLICY['require_owner_approval']}"
        )

    # B ----------------------------------------------------------------------------
    for u in units:
        holds_task = any(base_of(t) == "Task" for t in u.get("tool_permissions", []))
        if holds_task and u.get("owner_approval_required") is not True:
            u["owner_approval_required"] = True
            changes.append(
                f"B {u['id']} owner_approval_required false -> true (holds Task)"
            )

    # C ----------------------------------------------------------------------------
    for u in units:
        tools = list(u.get("tool_permissions", []))
        if not any(str(t) in EXPANSIONS for t in tools):
            continue
        out: list[str] = []
        for t in tools:
            for repl in EXPANSIONS.get(str(t), [str(t)]):
                if repl not in out:
                    out.append(repl)
        removed = [str(t) for t in tools if str(t) in EXPANSIONS]
        u["tool_permissions"] = out
        changes.append(
            f"C {u['id']} expanded {removed} -> "
            f"{[t for t in out if t not in [str(x) for x in tools]]}"
        )

    # D ----------------------------------------------------------------------------
    for u in units:
        fix = SUBSTRATE_FIXES.get(str(u.get("id")))
        if fix and str(u.get("execution_substrate")) == fix[0]:
            u["execution_substrate"] = fix[1]
            changes.append(
                f"D {u['id']} execution_substrate {fix[0]} -> {fix[1]} "
                "(remote substrate cannot honour session-local Task)"
            )

    if not changes:
        print("SUCCESS:authz-apply-fixes no change needed (idempotent re-run)")
        return 0

    body = json.dumps(catalog, indent=1, sort_keys=False, ensure_ascii=False)
    CATALOG.write_bytes(body.replace("\n", "\r\n").encode("utf-8"))
    for line in changes:
        print(" ", line)
    print(f"SUCCESS:authz-apply-fixes edits={len(changes)} bytes={len(body)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
