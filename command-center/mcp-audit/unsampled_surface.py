#!/usr/bin/env python3
"""Measure the 7 rows the stdio sweep could not enumerate, so the fleet denominator stops
being UNMEASURED.

WHAT THIS CLOSES.  An independent audit CONFIRMED an overclaim against round 2: the share
"cloud-hub is 60.1% of every-turn resident MCP cost" rests on a denominator of 16 of 23
rows.  Round 3 fixed the SENTENCE -- scope into the field name, into the headline, and a
control (``C5``) that fails the run if it is dropped.  That was the right repair and it left
the underlying number unmeasured, which ``cost_rank``'s docstring then asserted was
permanent::

    "Publishing a fleet-wide figure instead is not available: the 7 rows have no tool names
     anywhere in the repository, so the true fleet denominator is UNMEASURED, not merely
     unpublished."

**REFUTED, and kept here rather than deleted.**  The premise is true and the conclusion does
not follow.  "Nowhere in the repository" is a statement about the repository, not about what
is measurable -- and this lane already treats a second instrument as legitimate: the CLIENT's
own deferred-tool listing, which ``_g2_drift_probe.SESSION_NAMESPACE`` has used since the
grounding round to corroborate the mounted server set.  The same listing enumerates the tool
NAMES of exactly the 7 rows the stdio sweep cannot spawn, because they are HTTP transports
(``last_error: transport='http': no stdio command``) that the client connects to anyway.

So the denominator was never unmeasurable.  It was unmeasured because the producer only ever
asked one instrument.

WHAT IS MEASURED, AND WHAT IS STILL NOT.  Resident cost only.

  * ``name_bytes``   MEASURED.  The client lists tool NAMES, which is the whole resident cost
                     under a deferred-schema client -- the cost paid on EVERY request.
  * ``schema_bytes`` NOT MEASURED, and stays ``None``.  Schemas are exactly what a deferred
                     client withholds until selection, so no honest contingent figure exists
                     for these rows.  Null means NOT MEASURED, never zero.

That asymmetry is the point of the split ``cost_rank`` already makes.  The fleet's RESIDENT
total is now knowable; the fleet's CONTINGENT total is still a lower bound.  Publishing one
and not the other is the honest result, not an omission.

INSTRUMENT INDEPENDENCE, STATED PRECISELY.  The audit reached 154 tools / 2,487 B by hand
from its own session and rated it only LIKELY, because the count was hand-transcribed and its
session ran two days after the audited sweep, so the fleet might have drifted.  This module's
transcription agrees with it on all 7 servers, on both tools and bytes, and ``_g2_drift_probe``
independently reports 23/23 server-name agreement, which settles the drift half.

That is **transcription independence, not instrument independence**: both transcriptions read
the same client listing, so a systematic error in the CLIENT would survive both.  It rules out
the error mode the audit actually flagged (miscounting by hand) and does not rule out the
client under-reporting its own namespace.  Named rather than glossed, with its settling
experiment: an HTTP ``tools/list`` against each of the 7 endpoints, which needs credentials
this lane does not read.

Deterministic: no network, no spawn, no credential read, sorted output, ``newline="\\n"``.

Run::

    python unsampled_surface.py -o unsampled-surface.json
    python unsampled_surface.py --self-test
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
MATRIX = "capability-matrix-r2.json"

PROVENANCE = (
    "this session's mounted MCP namespace, transcribed from the deferred-tool listing the "
    "Claude Code client injects at session start (the `mcp__<server>__<tool>` prefixes it "
    "enumerated), bare names only to match the upstream name_bytes basis. Second instrument "
    "to the stdio handshake sweep, which cannot reach these rows at all: all 7 are HTTP "
    "transports recorded as `transport='http': no stdio command`."
)

# Bare tool names -- no `mcp__<server>__` prefix, because the upstream `name_bytes` basis is
# `sum(len(n) for n in tool_names)` over bare names.  `_reconcile_basis` proves that is the
# same function upstream used rather than assuming it.
SESSION_SURFACE: dict[str, tuple[str, ...]] = {
    "agent-mail": (
        "acknowledge_message",
        "archive_project",
        "create_agent_identity",
        "deregister_agent",
        "ensure_project",
        "expire_window",
        "fetch_inbox",
        "fetch_summary",
        "fetch_topic",
        "file_reservation_paths",
        "force_release_file_reservation",
        "hard_delete_agent",
        "hard_delete_project",
        "health_check",
        "install_precommit_guard",
        "list_contacts",
        "list_window_identities",
        "macro_contact_handshake",
        "macro_file_reservation_cycle",
        "macro_prepare_thread",
        "macro_start_session",
        "mark_message_read",
        "purge_old_messages",
        "register_agent",
        "release_file_reservations",
        "rename_window",
        "renew_file_reservations",
        "reply_message",
        "request_contact",
        "respond_contact",
        "retire_agent",
        "search_messages",
        "send_message",
        "set_contact_policy",
        "summarize_recent",
        "summarize_thread",
        "unarchive_project",
        "uninstall_precommit_guard",
        "unretire_agent",
        "whois",
    ),
    "basic-memory": (
        "build_context",
        "canvas",
        "cloud_info",
        "create_memory_project",
        "delete_note",
        "delete_project",
        "edit_note",
        "fetch",
        "list_directory",
        "list_memory_projects",
        "list_workspaces",
        "move_note",
        "read_content",
        "read_note",
        "recent_activity",
        "release_notes",
        "schema_diff",
        "schema_infer",
        "schema_validate",
        "search",
        "search_notes",
        "view_note",
        "write_note",
    ),
    "brightdata": (
        "ask_brightdata_assistant",
        "scrape_as_markdown",
        "scrape_batch",
        "search_engine",
        "search_engine_batch",
    ),
    "deepwiki": ("ask_question", "read_wiki_contents", "read_wiki_structure"),
    "figma": (
        "add_code_connect_map",
        "create_new_file",
        "download_assets",
        "export_video",
        "generate_diagram",
        "generate_figma_design",
        "get_code_connect_map",
        "get_code_connect_suggestions",
        "get_context_for_code_connect",
        "get_design_context",
        "get_figjam",
        "get_libraries",
        "get_metadata",
        "get_motion_context",
        "get_screenshot",
        "get_shader_effect",
        "get_shader_fill",
        "get_variable_defs",
        "list_file_components_for_code_connect",
        "list_shader_effects",
        "list_shader_fills",
        "search_design_system",
        "send_code_connect_mappings",
        "upload_assets",
        "use_figma",
        "weave_cancel_tool_run",
        "weave_get_tool_inputs",
        "weave_get_tool_run_output",
        "weave_list_tools",
        "weave_run_tool",
        "weave_upload_asset",
        "whoami",
    ),
    "github": (
        "add_comment_to_pending_review",
        "add_issue_comment",
        "add_reply_to_pull_request_comment",
        "assign_copilot_to_issue",
        "create_branch",
        "create_or_update_file",
        "create_pull_request",
        "create_pull_request_with_copilot",
        "create_repository",
        "delete_file",
        "fork_repository",
        "get_commit",
        "get_copilot_job_status",
        "get_file_contents",
        "get_label",
        "get_latest_release",
        "get_me",
        "get_release_by_tag",
        "get_tag",
        "get_team_members",
        "get_teams",
        "issue_read",
        "issue_write",
        "list_branches",
        "list_commits",
        "list_issue_fields",
        "list_issue_types",
        "list_issues",
        "list_pull_requests",
        "list_releases",
        "list_repository_collaborators",
        "list_tags",
        "merge_pull_request",
        "pull_request_read",
        "pull_request_review_write",
        "push_files",
        "request_copilot_review",
        "run_secret_scanning",
        "search_code",
        "search_commits",
        "search_issues",
        "search_pull_requests",
        "search_repositories",
        "search_users",
        "sub_issue_write",
        "update_pull_request",
        "update_pull_request_branch",
    ),
    "huggingface": ("hf_fs", "hf_whoami", "hub_repo_details", "hub_repo_search"),
}

# The audit's own hand count, kept executable so the corroboration is re-checked on every run
# rather than asserted once in prose.  Two transcriptions of the same listing by different
# readers on different days: it bounds transcription error, not instrument error.
AUDIT_HAND_COUNT: dict[str, tuple[int, int]] = {
    "agent-mail": (40, 684),
    "basic-memory": (23, 271),
    "brightdata": (5, 86),
    "deepwiki": (3, 49),
    "figma": (32, 571),
    "github": (47, 781),
    "huggingface": (4, 45),
}


def name_bytes(names: tuple[str, ...] | list[str]) -> int:
    """The upstream basis. `_reconcile_basis` proves this is the same function that produced
    the committed `name_bytes` of the sampled rows, instead of assuming a shared definition."""
    return sum(len(n) for n in names)


def _matrix_split(base: pathlib.Path) -> tuple[dict[str, dict], dict[str, dict]]:
    """(sampled, unsampled) rows of the capability matrix, keyed by server name."""
    matrix = json.loads((base / MATRIX).read_text(encoding="utf-8"))
    rows = matrix.get("rows") or []
    if not rows:
        raise SystemExit("FAILED:unsampled-surface capability matrix has no rows")
    sampled, unsampled = {}, {}
    for r in rows:
        name = r.get("name")
        if not name:
            continue
        (sampled if (r.get("tool_count") and r.get("name_bytes")) else unsampled)[
            name
        ] = r
    return sampled, unsampled


def _reconcile_basis(sampled: dict[str, dict]) -> int:
    """CONTROL: recompute `name_bytes` for every SAMPLED row with this module's function and
    require an exact match against the committed value.

    This is the control that can distinguish the two hypotheses.  A check that merely read
    the surface back would pass whether or not the basis agreed -- it would prove the file
    parses.  Reconciling against 16 independently-produced numbers fails loudly if this
    module counts anything the sweep did not (a prefix, a separator, a schema byte), which is
    the one way the new rows could be silently incommensurable with the old ones.
    """
    checked = 0
    for name, row in sorted(sampled.items()):
        names = row.get("tool_names") or []
        if not names:
            raise SystemExit(
                f"FAILED:unsampled-surface sampled row {name!r} has name_bytes but no "
                "tool_names -- the basis cannot be reconciled against it"
            )
        calc = name_bytes(names)
        if calc != row["name_bytes"]:
            raise SystemExit(
                f"FAILED:unsampled-surface basis mismatch on sampled row {name!r}: this "
                f"module computes {calc}, the committed matrix says {row['name_bytes']} -- "
                "the new rows would not be commensurable with the old ones"
            )
        checked += 1
    if not checked:
        raise SystemExit(
            "FAILED:unsampled-surface no sampled row could be reconciled -- refusing to "
            "publish a surface on an unverified basis (fail closed)"
        )
    return checked


def build(
    base: pathlib.Path, surface: dict[str, tuple[str, ...]] | None = None
) -> dict[str, Any]:
    surface = SESSION_SURFACE if surface is None else surface
    sampled, unsampled = _matrix_split(base)

    # V1 -- the fail-closed link to the matrix.  If a future sweep manages to enumerate one
    # of these rows, or a new HTTP row appears, this module is stale and must not be trusted
    # to complete a fleet total.  Both directions, because a one-directional read is how a
    # divergence gets scored as agreement.
    missing = sorted(set(unsampled) - set(surface))
    extra = sorted(set(surface) - set(unsampled))
    if missing or extra:
        raise SystemExit(
            "FAILED:unsampled-surface this module's servers no longer match the matrix's "
            f"unsampled rows -- unmeasured and not transcribed here: {missing or '(none)'}; "
            f"transcribed here but no longer unsampled: {extra or '(none)'}. Re-transcribe "
            "or drop the row; do NOT complete a fleet total from a stale surface"
        )
    # V2 -- no row may be counted twice.  V1 already implies it; asserted separately because
    # double counting inflates the denominator, which moves every share in the flattering
    # direction, and that is the direction nobody audits.
    both = sorted(set(surface) & set(sampled))
    if both:
        raise SystemExit(
            f"FAILED:unsampled-surface {both} are BOTH sampled and transcribed here -- "
            "the fleet denominator would double-count them"
        )

    reconciled = _reconcile_basis(sampled)

    rows: list[dict[str, Any]] = []
    for name in sorted(surface):
        names = surface[name]
        if not names:
            raise SystemExit(
                f"FAILED:unsampled-surface {name!r} transcribed as an EMPTY surface -- a "
                "server that advertises nothing is a finding, not a default; state it"
            )
        if len(set(names)) != len(names):
            dupes = sorted({n for n in names if list(names).count(n) > 1})
            raise SystemExit(
                f"FAILED:unsampled-surface {name!r} has duplicate tool name(s) {dupes} -- "
                "a transcription slip would inflate both the count and the bytes"
            )
        bad = [n for n in names if not n or n.startswith("mcp__") or n != n.strip()]
        if bad:
            raise SystemExit(
                f"FAILED:unsampled-surface {name!r} carries non-bare tool name(s) {bad} -- "
                "the upstream basis is bare names; a prefix would inflate name_bytes"
            )
        row = {
            "name": name,
            "tool_count": len(names),
            "resident_bytes": name_bytes(names),
            # NOT MEASURED, never zero.  A deferred-schema client withholds schemas until
            # selection, so this row has no honest contingent figure.
            "contingent_bytes": None,
            "contingent_basis": (
                "NOT MEASURED: schemas are deferred by this client and never materialised "
                "for these rows, so no contingent figure exists. Null is not zero."
            ),
            "source_file": unsampled[name].get("source_file"),
            "definition_scope": unsampled[name].get("definition_scope"),
            "transport": unsampled[name].get("transport"),
            "why_unsampled": unsampled[name].get("last_error"),
        }
        audit = AUDIT_HAND_COUNT.get(name)
        row["audit_hand_count_agrees"] = bool(
            audit and audit == (row["tool_count"], row["resident_bytes"])
        )
        rows.append(row)

    # C-corroborate: the audit's independent hand count, re-checked every run.
    disagree = [
        r["name"]
        for r in rows
        if r["name"] in AUDIT_HAND_COUNT and not r["audit_hand_count_agrees"]
    ]
    if disagree:
        raise SystemExit(
            f"FAILED:unsampled-surface {disagree} disagree with the audit's independent "
            "hand count -- two readers of the same listing differ, so at least one "
            "transcription is wrong. Resolve before completing a fleet total"
        )

    return {
        "report": "mcp-unsampled-surface",
        "generated_utc_date": "2026-08-14",
        "provenance": PROVENANCE,
        "measures": (
            "RESIDENT ONLY. Tool names are measured; schemas are not, and stay null for "
            "every row here. So the fleet RESIDENT total these rows complete is a true "
            "total, and the fleet CONTINGENT total remains a lower bound."
        ),
        "independence": (
            "transcription-independent, NOT instrument-independent: this transcription and "
            "the audit's read the same client listing, so a systematic error in the CLIENT "
            "would survive both. Settling experiment: an HTTP tools/list against each "
            "endpoint, which needs credentials this lane does not read."
        ),
        "controls": {
            "V1_matches_matrix_unsampled": "both directions, or the run fails closed",
            "V2_no_double_count": "no server may be both sampled and transcribed here",
            "V3_bare_names": "no mcp__ prefix, no blank, no untrimmed name",
            "V4_no_duplicates": "a repeated name would inflate count AND bytes",
            "V5_no_empty_server": "an empty surface is a finding, not a default",
            "C_basis_reconciles": (
                f"this module's name_bytes reproduces the committed value for all "
                f"{reconciled} sampled rows -- the new rows are commensurable with the old"
            ),
            "C_audit_corroborates": (
                "the audit's independent hand count agrees on all 7 rows, tools and bytes"
            ),
        },
        "servers": len(rows),
        "tool_count_total": sum(r["tool_count"] for r in rows),
        "resident_bytes_total": sum(r["resident_bytes"] for r in rows),
        "rows": rows,
    }


# ----------------------------------------------------------------------------------------
# both-states self-test: every guard is shown firing on a mutation of the REAL surface, and
# silent on the real one.  A guard that has never gone red is indistinguishable from a no-op.
# ----------------------------------------------------------------------------------------
def _expect_fail(
    base: pathlib.Path, surface: dict[str, tuple[str, ...]], label: str
) -> bool:
    try:
        build(base, surface)
    except SystemExit:
        print(f"  ok  {label} -- fires")
        return True
    print(f"  BAD {label} -- did NOT fire")
    return False


def self_test(base: pathlib.Path) -> int:
    good = {k: v for k, v in SESSION_SURFACE.items()}
    checks: list[bool] = []

    try:
        build(base, good)
        print("  ok  the real surface builds clean")
        checks.append(True)
    except SystemExit as exc:
        print(f"  BAD the real surface does not build: {exc}")
        checks.append(False)

    m = dict(good)
    m.pop("github")
    checks.append(
        _expect_fail(base, m, "V1 a dropped server (fleet total would be short)")
    )

    m = dict(good)
    m["cloud-hub"] = ("some_tool",)
    checks.append(_expect_fail(base, m, "V2 a server that is already sampled"))

    m = dict(good)
    m["deepwiki"] = ("mcp__deepwiki__ask_question",)
    checks.append(_expect_fail(base, m, "V3 a prefixed name (inflates name_bytes)"))

    m = dict(good)
    m["deepwiki"] = ("ask_question", "ask_question", "read_wiki_contents")
    checks.append(_expect_fail(base, m, "V4 a duplicated name"))

    m = dict(good)
    m["deepwiki"] = ()
    checks.append(_expect_fail(base, m, "V5 an empty server surface"))

    m = dict(good)
    m["huggingface"] = ("hf_fs", "hf_whoami", "hub_repo_details")  # one short
    checks.append(
        _expect_fail(
            base, m, "C_audit a surface that drifts from the audit's hand count"
        )
    )

    # The basis control needs a mutated MATRIX, not a mutated surface: it guards the join
    # between this module and the committed numbers, so mutating the surface cannot reach it.
    sampled, _ = _matrix_split(base)
    victim = next(iter(sorted(sampled)))
    original = sampled[victim]["name_bytes"]
    try:
        sampled[victim]["name_bytes"] = original + 1
        _reconcile_basis(sampled)
        print("  BAD C_basis -- did NOT fire on a perturbed committed name_bytes")
        checks.append(False)
    except SystemExit:
        print(
            f"  ok  C_basis -- fires when {victim}'s committed name_bytes is perturbed"
        )
        checks.append(True)
    finally:
        sampled[victim]["name_bytes"] = original

    passed = sum(checks)
    total = len(checks)
    if passed != total:
        print(f"FAILED:unsampled-surface self-test {passed}/{total} controls behaved")
        return 1
    print(f"SUCCESS:unsampled-surface self-test {passed}/{total} controls behaved")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out")
    ap.add_argument("--base", default=str(HERE))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    base = pathlib.Path(args.base).resolve()

    if args.self_test:
        return self_test(base)

    doc = build(base)
    text = json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(text)
    print(
        f"SUCCESS:unsampled-surface {doc['servers']} unsampled row(s), "
        f"{doc['tool_count_total']} tools, {doc['resident_bytes_total']:,} resident B "
        f"(RESIDENT only -- contingent stays unmeasured for every row here)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
