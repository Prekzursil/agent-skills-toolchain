"""Blueprints 82-84 of 96 - the head of the D16-documentation family.

    82  BP-DOC-01  Pre-PR Self-Reflect Knowledge Capture
    83  BP-DOC-02  Rules-Distill Sweep
    84  BP-DOC-03  Single-Source-of-Truth Documentation Reconcile

Category span: 82 and 84 are ``data-science-knowledge-and-creative`` (the knowledge axis);
83 is ``collective-intelligence-and-meta`` because its subject is the shared agent rule floor
rather than any one project's docs.

All three "write documentation", which is exactly why the distinction has to be structural:
  82 is BRANCH-scoped and its load-bearing property is ATOMICITY - the knowledge commit must
     land in the same commit as the code, so the two cannot drift. It also refuses a "learning"
     that merely restates the diff, and permits an honest EMPTY capture.
  83 is CORPUS-scoped and its load-bearing property is a SCRIPT-FIRST VETO - a principle a
     script can enforce becomes a script, not a rule - plus a hard always-on context budget.
  84 is FACT-scoped and its load-bearing property is AUTHORITY BY MEASURABILITY - the winning
     statement is the one that can be measured, not the most convenient - ending in a pointer
     rewrite and a superseded-guidance register.
"""

from __future__ import annotations

from typing import Any

from bp7_common import (
    CAT_DATA,
    CAT_ENGINEERING,
    CAT_META,
    artifact,
    cache,
    card,
    dry_run,
    estimate,
    failure_policy,
    gate_expr,
    gate_predicate_v1,
    lineage,
    portability,
    replay_deterministic,
    replay_nondeterministic,
    resume,
    sch as _sch,
    tool_policy,
    unit_id,
    work_unit,
)

LIBRARY = "09-WORKFLOW-BLUEPRINT-LIBRARY.md"


# ============================================================ 82 / BP-DOC-01


def pre_pr_knowledge_capture() -> dict[str, Any]:
    u = lambda n: unit_id("DOC", 82, n)  # noqa: E731
    root = "command-center/knowledge/pre-pr-capture"
    return {
        "dsl_version": "1.0.0",
        "id": "pre-pr-knowledge-capture",
        "name": "Pre-PR knowledge capture, committed atomically with the code",
        "description": (
            "Capture learnings while the context is still fresh - after the work passes review but "
            "BEFORE the PR - so knowledge lands atomically with the code rather than as a follow-up "
            "that never comes. Three properties do the work. ATOMICITY: the knowledge commit and "
            "the code commit are the same commit, so the two cannot drift apart later. A "
            "RESTATEMENT gate: a 'learning' that merely paraphrases the diff is rejected, because a "
            "changelog dressed as knowledge is worse than an empty capture. And an HONEST EMPTY "
            "path: a branch that taught nothing records that fact instead of manufacturing a lesson."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": [CAT_DATA, CAT_ENGINEERING],
        "tags": [
            "bp-doc-01",
            "knowledge-capture",
            "atomic-commit",
            "pre-pr",
            "honest-empty",
        ],
        "flagship": False,
        "params": {
            "branch": {
                "type": "string",
                "required": True,
                "min_length": 1,
                "description": "The development branch whose learnings are being captured.",
            },
            "review_outcomes": {
                "type": "path",
                "required": True,
                "description": "The review verdicts for this branch - including any REFUTED premise, which is the highest-value thing to capture.",
            },
            "session_transcript_scope": {
                "type": "enum",
                "enum": ["this-branch-only", "this-session", "since-last-capture"],
                "default": "this-branch-only",
                "description": "How far back to scan. Wider scope raises the redaction burden, so it is a declared choice.",
            },
            "knowledge_base_root": {
                "type": "path",
                "required": True,
                "description": "Where durable learnings are written. The only tree this workflow may write outside its own root.",
            },
            "allow_empty_capture": {
                "type": "boolean",
                "default": True,
                "description": "When true a branch that taught nothing records an honest empty capture. Setting this false is how a ritual starts.",
            },
        },
        "roles": {
            "reflector": {
                "description": "Scans the branch's review outcomes and session patterns and extracts durable learnings - not a changelog.",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "advisory",
                "independence": "informed",
                "tool_permissions": [
                    "Read",
                    "Grep",
                    "Bash:git",
                    "Write(command-center/knowledge/**)",
                ],
            },
            "restatement-auditor": {
                "description": "Rejects a 'learning' that is a restatement of the diff. Holds the veto that keeps the knowledge base from filling with changelog.",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "veto",
                "independence": "cross-examining",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Bash:git", "mcp__codex__codex"],
                "speaking_rights": "always",
            },
            "redaction-screener": {
                "description": "Screens the capture for secrets carried in from a transcript. Records classes and locations, never values.",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "veto",
                "independence": "independent",
                "tool_permissions": [
                    "Read",
                    "Bash:python",
                    "Write(command-center/knowledge/**)",
                ],
            },
            "committer": {
                "description": "Stages the knowledge alongside the code so both land in ONE commit. Never uses --no-verify.",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "medium",
                "authority": "advisory",
                "independence": "informed",
                "tool_permissions": [
                    "Read",
                    "Bash:git",
                    "Write(command-center/knowledge/**)",
                ],
            },
        },
        "tool_policy": tool_policy(
            allow=[
                "Read",
                "Grep",
                "Bash:git",
                "Bash:python",
                "Write(command-center/knowledge/**)",
                "mcp__codex__codex",
                "mcp__basic-memory__write_note",
            ],
            deny=["Bash", "WebFetch", "Edit"],
            network="none",
            write_paths=[f"{root}/**"],
            forbid_write_paths=[".git/config", ".github/workflows/**"],
            source_policy={"offline_only": True, "require_provenance": True},
        ),
        "model_routing": {
            "strategy": "vendor-diverse",
            "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
            "routes": [
                {
                    "when": "stage_role == restatement-auditor",
                    "target": {
                        "model": "gpt-5-codex",
                        "vendor": "openai",
                        "effort": "high",
                    },
                    "reason": "the author of a learning is the worst judge of whether it restates its own diff",
                }
            ],
            "forbid_downgrade_below": "opus",
        },
        "gates": {
            "not-a-restatement": gate_expr(
                "learnings_restating_diff == 0",
                "repair",
            ),
            "redaction-clean": gate_expr(
                "secret_candidates_unredacted == 0 AND secret_values_in_artifact == 0",
                "fail",
            ),
            "capture-honest": gate_expr(
                "learnings_count >= 1 OR honest_empty_capture_recorded == true",
                "fail",
            ),
            "commit-atomic": gate_expr(
                "knowledge_and_code_in_one_commit == true AND no_verify_used == false",
                "escalate-to-human",
            ),
        },
        "subworkflows": {
            "rules-distill-sweep": {
                "workflow_id": "rules-distill-sweep",
                "version_range": ">=1.0.0 <2.0.0",
                "source": "platform/workflows/rules-distill-sweep.json",
            }
        },
        "stages": [
            {
                "id": "scan-branch",
                "title": "S0 - scan the branch's review outcomes and session patterns",
                "kind": "task",
                "role": "reflector",
                "timeout_seconds": 1800,
                "checkpoint": True,
                "tool_permissions": [
                    "Read",
                    "Grep",
                    "Bash:git",
                    "Write(command-center/knowledge/**)",
                ],
                "work_unit": work_unit(
                    uid=u(1),
                    title="Scan the branch for the material a durable learning could come from",
                    target="Collect this branch's review verdicts, refuted premises, retries and dead ends into one structured record, so extraction reads evidence rather than memory.",
                    inputs=[
                        "params.branch",
                        "params.review_outcomes",
                        "params.session_transcript_scope",
                    ],
                    dependencies=[],
                    model="opus",
                    vendor="anthropic",
                    role="reflector",
                    basis="recognising which review comment carries a generalisable lesson is judgement, not retrieval",
                    tools=[
                        "Read",
                        "Grep",
                        "Bash:git",
                        "Write(command-center/knowledge/**)",
                    ],
                    substrate="local-serialized",
                    timeout_seconds=1800,
                    output_path=f"{root}/branch-scan.json",
                    output_schema=_sch("audit-inventory"),
                    evidence="every candidate anchored to a review comment, a commit, or a failed-then-fixed sequence in the branch history",
                    tests=[
                        "a REFUTED premise in the review outcomes appears as a candidate, since the refutation is more valuable than the fix",
                        "a branch with no review comments still produces a scan record, possibly empty, rather than failing",
                    ],
                    reviewer="the restatement-auditor, which will reject candidates with no anchor",
                    sentinel_condition="the scan record exists and every candidate carries an anchor",
                    retry="two strikes then narrow the transcript scope rather than re-scanning the same range",
                    failure_classes=[
                        "scan-scope-too-wide",
                        "anchor-missing",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="branch-scoped evidence collection anchored to review comments and history",
                ),
                "produces": [
                    artifact(
                        f"{root}/branch-scan.json",
                        _sch("audit-inventory"),
                        min_bytes=128,
                        sentinel=f"SUCCESS:{u(1)}",
                        consumers=["extract-learnings", "audit-restatement"],
                    )
                ],
            },
            {
                "id": "extract-learnings",
                "title": "S1 - extract durable learnings, not a changelog",
                "kind": "task",
                "depends_on": ["scan-branch"],
                "role": "reflector",
                "timeout_seconds": 2400,
                "tool_permissions": [
                    "Read",
                    "Bash:git",
                    "Write(command-center/knowledge/**)",
                ],
                "work_unit": work_unit(
                    uid=u(2),
                    title="Turn scan candidates into durable, generalisable learnings",
                    target="Write learnings that would help on a DIFFERENT branch, each with a falsifiable precondition - and when nothing generalises, record an honest empty capture instead of inventing one.",
                    inputs=[f"{root}/branch-scan.json", "params.allow_empty_capture"],
                    dependencies=[u(1)],
                    model="opus",
                    vendor="anthropic",
                    role="reflector",
                    basis="generalising from one branch to a reusable lesson is the hardest judgement in the workflow",
                    tools=["Read", "Bash:git", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=2400,
                    output_path=f"{root}/learnings.json",
                    output_schema=_sch("novelty-ledger"),
                    evidence="each learning states the condition under which it applies and the observation that produced it, so a later reader can test whether it still holds",
                    tests=[
                        "a branch that taught nothing produces an HONEST EMPTY capture, not a manufactured lesson",
                        "a branch with a refuted premise captures the REFUTATION, not only the fix that followed it",
                        "each learning carries a falsifiable precondition; a learning that is true unconditionally is a platitude and is rejected",
                    ],
                    reviewer="the restatement-auditor, cross-vendor, which decides whether each learning generalises",
                    sentinel_condition="learnings exist with preconditions, or an explicit honest-empty record does",
                    retry="two strikes then record the honest empty capture rather than lowering the bar a third time",
                    failure_classes=[
                        "learning-is-restatement",
                        "manufactured-lesson",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="generalisation with a falsifiable precondition per learning, and an honest-empty escape",
                ),
                "produces": [
                    artifact(
                        f"{root}/learnings.json",
                        _sch("novelty-ledger"),
                        min_bytes=64,
                        sentinel=f"SUCCESS:{u(2)}",
                        consumers=[
                            "audit-restatement",
                            "screen-redaction",
                            "write-knowledge",
                        ],
                    )
                ],
            },
            {
                "id": "audit-restatement",
                "title": "A learning that restates the diff is rejected",
                "kind": "task",
                "depends_on": ["extract-learnings"],
                "role": "restatement-auditor",
                "timeout_seconds": 1800,
                "tool_permissions": ["Read", "Bash:git", "mcp__codex__codex"],
                "work_unit": work_unit(
                    uid=u(3),
                    title="Decide for each learning whether it says more than the diff already says",
                    target="Compare each learning against the branch diff and reject any that a reader could derive from the diff alone, because that is a changelog entry occupying a knowledge slot.",
                    inputs=[f"{root}/learnings.json", "params.branch"],
                    dependencies=[u(2)],
                    model="gpt-5-codex",
                    vendor="openai",
                    role="restatement-auditor",
                    basis="the author cannot see that its own lesson is a paraphrase of its own change; a different vendor can",
                    tools=["Read", "Bash:git", "mcp__codex__codex"],
                    substrate="local-serialized",
                    timeout_seconds=1800,
                    output_path=f"{root}/restatement-audit.json",
                    output_schema=_sch("overclaim-scan"),
                    evidence="for each rejection, the diff hunk the learning merely paraphrases",
                    tests=[
                        "a learning that paraphrases a renamed function is REJECTED with the hunk cited",
                        "both-states control: a genuine cross-cutting lesson is ACCEPTED, so the auditor is not rejecting everything",
                    ],
                    reviewer="the reflector, which may contest a rejection with a generalisation argument but not by repetition",
                    sentinel_condition="every learning is accepted or rejected with the paraphrased hunk cited for each rejection",
                    retry="two strikes then escalate the contested learning rather than letting either side win by persistence",
                    failure_classes=[
                        "learning-is-restatement",
                        "detector-failure",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="cross-vendor diff-paraphrase detection with the hunk cited per rejection",
                ),
                "produces": [
                    artifact(
                        f"{root}/restatement-audit.json",
                        _sch("overclaim-scan"),
                        min_bytes=128,
                        sentinel=f"SUCCESS:{u(3)}",
                        consumers=["restatement-gate", "write-knowledge"],
                    )
                ],
            },
            {
                "id": "restatement-gate",
                "title": "The knowledge base is not a changelog",
                "kind": "gate",
                "depends_on": ["audit-restatement"],
                "gate_ref": "not-a-restatement",
            },
            {
                "id": "screen-redaction",
                "title": "A transcript-derived capture is redaction-screened before it is written",
                "kind": "task",
                "depends_on": ["restatement-gate"],
                "role": "redaction-screener",
                "timeout_seconds": 1200,
                "tool_permissions": [
                    "Read",
                    "Bash:python",
                    "Write(command-center/knowledge/**)",
                ],
                "work_unit": work_unit(
                    uid=u(4),
                    title="Screen the capture for secrets carried in from the session transcript",
                    target="Deny by default: scan every learning for credential-shaped content and redact it, recording the CLASS and location only, because a transcript can carry a token into a committed file.",
                    inputs=[
                        f"{root}/learnings.json",
                        "params.session_transcript_scope",
                    ],
                    dependencies=[u(2)],
                    model="opus",
                    vendor="anthropic",
                    role="redaction-screener",
                    basis="an allowlist redactor leaks; deciding what is credential-shaped needs judgement over a deny-by-default rule",
                    tools=["Read", "Bash:python", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=1200,
                    output_path=f"{root}/redaction-screen.json",
                    output_schema=_sch("secret-egress-map"),
                    evidence="per-learning screening verdict naming any detected class and its location, with the VALUE never written to this or any artifact",
                    tests=[
                        "a token-shaped string in a learning is redacted and its value does not appear in any artifact",
                        "the screener denies by default: an unrecognised high-entropy string is redacted rather than passed because it matched no known prefix",
                        "both-states control: ordinary prose passes unredacted, so the screener is not blanking the capture",
                    ],
                    reviewer="the committer, which refuses to stage a capture with an unresolved redaction",
                    sentinel_condition="every learning is screened and no artifact contains a detected secret value",
                    retry="two strikes then drop the affected learning rather than committing an unscreened one",
                    failure_classes=[
                        "secret-in-capture",
                        "redactor-allowlist-leak",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="deny-by-default redaction screen recording classes and locations, never values",
                ),
                "produces": [
                    artifact(
                        f"{root}/redaction-screen.json",
                        _sch("secret-egress-map"),
                        min_bytes=128,
                        sentinel=f"SUCCESS:{u(4)}",
                        consumers=["redaction-gate", "write-knowledge"],
                    )
                ],
            },
            {
                "id": "redaction-gate",
                "title": "No secret reaches a committed knowledge file",
                "kind": "gate",
                "depends_on": ["screen-redaction"],
                "gate_ref": "redaction-clean",
            },
            {
                "id": "write-knowledge",
                "title": "S2 - write the surviving learnings to the knowledge base",
                "kind": "task",
                "depends_on": ["redaction-gate"],
                "role": "reflector",
                "timeout_seconds": 1800,
                "tool_permissions": [
                    "Read",
                    "Write(command-center/knowledge/**)",
                    "mcp__basic-memory__write_note",
                ],
                "work_unit": work_unit(
                    uid=u(5),
                    title="Write the accepted learnings into the knowledge base and the semantic store",
                    target="Persist each accepted learning to the knowledge base and as a semantic note, and where it supersedes an earlier belief, link the supersession so the dead end is retired rather than re-walked.",
                    inputs=[
                        f"{root}/learnings.json",
                        f"{root}/restatement-audit.json",
                        "params.knowledge_base_root",
                    ],
                    dependencies=[u(3), u(4)],
                    model="opus",
                    vendor="anthropic",
                    role="reflector",
                    basis="deciding what an entry supersedes requires knowing the prior belief, which is judgement",
                    tools=[
                        "Read",
                        "Write(command-center/knowledge/**)",
                        "mcp__basic-memory__write_note",
                    ],
                    substrate="local-serialized",
                    timeout_seconds=1800,
                    output_path=f"{root}/knowledge-diff.json",
                    output_schema=_sch("improvement-ledger"),
                    evidence="the knowledge-base diff plus, for each superseding entry, the permalink of the entry it supersedes",
                    tests=[
                        "a learning that contradicts an existing entry links the supersession rather than leaving both live",
                        "an honest empty capture writes the empty record and nothing else",
                    ],
                    reviewer="the committer, which will not stage an entry whose supersession link dangles",
                    sentinel_condition="the diff exists and every superseding entry names what it supersedes",
                    retry="two strikes then write the entry without the supersession link and flag the unresolved link",
                    failure_classes=["supersession-dangling", "partial-artifact"],
                    owner_approval=False,
                    mechanism="knowledge write with explicit supersession linking of retired beliefs",
                ),
                "produces": [
                    artifact(
                        f"{root}/knowledge-diff.json",
                        _sch("improvement-ledger"),
                        min_bytes=128,
                        sentinel=f"SUCCESS:{u(5)}",
                        consumers=[
                            "honesty-gate",
                            "commit-with-code",
                            "promote-to-rule",
                        ],
                    )
                ],
            },
            {
                "id": "honesty-gate",
                "title": "Either a learning or an honest empty capture - never silence",
                "kind": "gate",
                "depends_on": ["write-knowledge"],
                "gate_ref": "capture-honest",
            },
            {
                "id": "promote-to-rule",
                "title": "S1b - a cross-cutting learning is promoted to the rules sweep",
                "kind": "subworkflow",
                "depends_on": ["honesty-gate"],
                "when": "cross_cutting_learning_found == true",
                "timeout_seconds": 7200,
                "workflow": {
                    "workflow_id": "rules-distill-sweep",
                    "version_range": ">=1.0.0 <2.0.0",
                },
                "params": {"seeded_from_branch_capture": True},
                "isolation": "none",
                "propagate_failure": False,
            },
            {
                "id": "commit-with-code",
                "title": "S3 - ONE commit: the knowledge and the code together",
                "kind": "task",
                "depends_on": ["honesty-gate"],
                "role": "committer",
                "timeout_seconds": 1200,
                "tool_permissions": [
                    "Read",
                    "Bash:git",
                    "Write(command-center/knowledge/**)",
                ],
                "work_unit": work_unit(
                    uid=u(6),
                    title="Stage the knowledge alongside the code and commit both in one commit",
                    target="Produce a single commit containing both the code change and the knowledge entries, with a scoped stage list, no --no-verify, and a recorded commit id proving the atomicity claim.",
                    inputs=[f"{root}/knowledge-diff.json", "params.branch"],
                    dependencies=[u(5)],
                    model="opus",
                    vendor="anthropic",
                    role="committer",
                    basis="staging scope matters: a broad add on a shared index sweeps a sibling agent's work",
                    tools=["Read", "Bash:git", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=1200,
                    output_path=f"{root}/atomic-commit.json",
                    output_schema=_sch("attestation-ledger"),
                    evidence="the commit id, the full list of paths in that commit, and proof that both a code path and a knowledge path appear in it",
                    tests=[
                        "the recorded commit contains at least one code path AND at least one knowledge path; two commits fail the atomicity gate",
                        "the staged path list is explicit; a broad add-all is rejected because a shared index would sweep a sibling agent's files",
                        "--no-verify is never used, and the record states so",
                    ],
                    reviewer="one independent reviewer in a fresh context who re-reads the commit's path list",
                    sentinel_condition="one commit id is recorded whose path list contains both a code and a knowledge path",
                    retry="two strikes then stop and hand the staging decision to the owner rather than force a commit",
                    failure_classes=[
                        "commit-not-atomic",
                        "staging-scope-escape",
                        "hook-bypassed",
                    ],
                    owner_approval=True,
                    mechanism="single scoped commit carrying both code and knowledge, with the path list as the proof",
                ),
                "produces": [
                    artifact(
                        f"{root}/atomic-commit.json",
                        _sch("attestation-ledger"),
                        min_bytes=128,
                        sentinel=f"SUCCESS:{u(6)}",
                        consumers=["atomicity-gate", "command-center/MANIFEST.json"],
                    )
                ],
            },
            {
                "id": "atomicity-gate",
                "title": "Knowledge that lands in its own commit will drift from the code",
                "kind": "gate",
                "depends_on": ["commit-with-code"],
                "gate_ref": "commit-atomic",
            },
        ],
        "stopping_rules": [
            {
                "id": "knowledge-committed",
                "expression": "knowledge_and_code_in_one_commit == true",
                "applies_to": "workflow",
                "minimum_conditions": "learnings_restating_diff == 0",
                "on_stop": "complete",
            },
            {
                "id": "honest-empty-capture",
                "expression": "learnings_count == 0 AND honest_empty_capture_recorded == true",
                "applies_to": "workflow",
                "on_stop": "complete",
            },
            {
                "id": "secret-in-capture-halts",
                "expression": "secret_candidates_unredacted > 0",
                "applies_to": "workflow",
                "on_stop": "escalate",
            },
        ],
        "retry_policy": {
            "strategy": "two-strikes-then-pivot",
            "max_attempts": 3,
            "backoff_seconds": 15,
            "jitter": True,
            "retry_on": ["scan-scope-too-wide", "supersession-dangling"],
            "no_retry_on": ["secret-in-capture", "commit-not-atomic", "hook-bypassed"],
            "pivot": {
                "after_attempts": 2,
                "enumerate_alternatives_min": 2,
                "escalate_to": "atomicity-gate",
            },
        },
        "failure_policy": failure_policy(
            "escalate-to-human",
            [
                "learning-is-restatement",
                "secret-in-capture",
                "commit-not-atomic",
                "staging-scope-escape",
            ],
            escalate_to="atomicity-gate",
            quarantine_path=f"{root}/quarantine",
        ),
        "resume": resume(
            f"{root}/checkpoints",
            "stage",
            ["workflow_id", "workflow_version", "stage_id", "params_hash"],
        ),
        "replay": replay_nondeterministic(
            f"{root}/replay.jsonl",
            ["params", "inputs", "model_outputs", "tool_calls"],
        ),
        "cache": {"enabled": False},
        "dry_run": dry_run(
            f"{root}/dry-run-plan.json",
            [
                "Bash:git",
                "Write(command-center/knowledge/**)",
                "mcp__basic-memory__write_note",
                "mcp__codex__codex",
            ],
            emits=["plan", "artifact-diff", "permission-report"],
        ),
        "estimate": estimate(
            basis="static-declared",
            confidence="almost-certain",
            cost_expected=1.4,
            cost_max=6.0,
            seconds_expected=2400,
            seconds_max=9000,
            tokens_expected=250000,
            risk="low",
            reversibility="reversible",
            blast_radius="writes the knowledge base and creates ONE commit on the named branch; the staging list is explicit so a shared git index cannot sweep a sibling's files",
            owner_approval=True,
        ),
        "portability": portability(
            f"{root}/export/pre-pr-knowledge-capture.bundle.json"
        ),
        "lineage": lineage(
            [
                card(f"{LIBRARY}#BP-DOC-01", "ADOPT-AS-IS"),
                card("cmd-self-reflect", "ADOPT-AS-IS"),
                card("plugin-claude-reflect", "COMPOSE", license_="third-party-plugin"),
                card("skill-knowledge-ops", "COMPOSE"),
            ],
            rollback_to=["cmd-self-reflect@current"],
        ),
        "outputs": {
            "knowledge_base_diff": artifact(
                f"{root}/knowledge-diff.json",
                _sch("improvement-ledger"),
                min_bytes=128,
                consumers=["command-center/MANIFEST.json", "rules-distill-sweep"],
            ),
            "atomicity_proof": artifact(
                f"{root}/atomic-commit.json",
                _sch("attestation-ledger"),
                min_bytes=128,
                consumers=["command-center/MANIFEST.json"],
            ),
        },
        "x_extensions": {
            "bp7": {
                "card": "BP-DOC-01",
                "card_index_in_library": 82,
                "family": "D16-documentation",
                "primary_category": CAT_DATA,
                "mechanism_signature": [
                    "branch-scoped-learning-extraction",
                    "cross-vendor-restatement-rejection",
                    "deny-by-default-redaction-screen",
                    "single-commit-atomicity-proof",
                    "honest-empty-capture",
                ],
                "why_not_deterministic": "Extraction and the restatement judgement are model calls; the journal is recorded and divergence is compared semantically rather than by hash.",
                "worked_example": {
                    "scenario": "A branch fixed a flaky test. Along the way the reviewer REFUTED the original premise ('the flake is a timing race') - the real cause was a shared fixture.",
                    "params": {
                        "branch": "fix/flaky-export-test",
                        "review_outcomes": "command-center/reviews/fix-flaky-export-test.json",
                        "session_transcript_scope": "this-branch-only",
                        "knowledge_base_root": "command-center/knowledge",
                        "allow_empty_capture": True,
                    },
                    "expected_trace": [
                        "scan-branch -> 6 candidates, including the refuted timing-race premise",
                        "extract-learnings -> 2 learnings: (a) 'a shared fixture torn down by a sibling test presents as a timing race' with the precondition 'the fixture is module-scoped'; (b) the REFUTATION of the timing-race premise",
                        "audit-restatement -> a third candidate ('renamed the helper to setup_export') is REJECTED as a paraphrase of one diff hunk",
                        "restatement-gate PASS (0 restatements survive)",
                        "screen-redaction -> one high-entropy string in a pasted log is redacted by the deny-by-default rule despite matching no known prefix",
                        "redaction-gate PASS; write-knowledge -> 2 entries, one linking supersession of the earlier timing-race note",
                        "honesty-gate PASS; promote-to-rule skipped (no cross-cutting learning)",
                        "commit-with-code -> one commit containing src/export.py, tests/test_export.py and command-center/knowledge/*.md",
                        "atomicity-gate PASS (code path and knowledge path both in commit)",
                    ],
                    "expected_terminal_state": "SUCCESS:DOC-8206",
                },
                "unverified": "UNVERIFIED capture rate - nothing here proves the workflow is actually run before a PR rather than skipped. Settling experiment = count branches merged over one month without a knowledge path in any of their commits; the atomicity artifact makes that count mechanical.",
                "distinct_from": {
                    "BP-INC-04": "that distils from an INCIDENT into a failure entry; this distils from a completed BRANCH into the knowledge base, atomically with the code",
                    "bp-doc-02": "that scans the WHOLE skill corpus for repetition; this reads ONE branch and its reviews",
                    "bp-doc-03": "that reconciles a FACT stated in many places; this creates new knowledge from new work",
                },
                "flagship_test": None,
                "flagship_rationale": "NOT flagship: its load-bearing gate is an atomicity property of a real git commit, and this unit is forbidden from committing (roughly twenty agents share one index). The gate's structure - a commit record naming both a code and a knowledge path, and an explicit no-broad-add test - IS asserted by test_bp7_slice.py.",
            }
        },
    }


# ============================================================ 83 / BP-DOC-02


def rules_distill_sweep() -> dict[str, Any]:
    u = lambda n: unit_id("DOC", 83, n)  # noqa: E731
    root = "command-center/knowledge/rules-distill"
    return {
        "dsl_version": "1.0.0",
        "id": "rules-distill-sweep",
        "name": "Rules-distill sweep with a script-first veto and a context budget",
        "description": (
            "Scan the skill corpus for cross-cutting principles and distil them into rules, so a "
            "lesson learned inside one skill becomes available everywhere. Two mechanisms stop this "
            "from becoming rule bloat. The SCRIPT-FIRST VETO: a principle a script can enforce "
            "becomes a script, not a rule, because a rule competes for the always-on context budget "
            "while a script does not. And a hard BUDGET gate: the always-on rule surface has a line "
            "ceiling, and a proposal that would exceed it must displace something rather than "
            "accumulate. A caveat unique to one skill is never promoted - single-skill detail "
            "belongs in that skill."
        ),
        "version": "1.0.0",
        "kind": "meta-workflow",
        "categories": [CAT_META],
        "tags": ["bp-doc-02", "rules", "script-first", "context-budget", "dedupe"],
        "flagship": False,
        "params": {
            "skill_corpus": {
                "type": "array",
                "required": True,
                "min_items": 1,
                "items": {"type": "path"},
                "description": "Roots of the skill vault to scan. One fan-out shard per root.",
            },
            "existing_rules": {
                "type": "path",
                "required": True,
                "description": "The current rules tree, so a proposal can be deduped against what already exists.",
            },
            "min_skills_for_promotion": {
                "type": "integer",
                "default": 3,
                "minimum": 2,
                "maximum": 50,
                "description": "A caveat must appear in at least this many skills to be cross-cutting. Below it, the detail belongs in its skill.",
            },
            "rule_line_budget": {
                "type": "integer",
                "default": 300,
                "minimum": 50,
                "maximum": 5000,
                "description": "Ceiling on the always-on rule surface. The stated discipline is CLAUDE.md under 300 lines.",
            },
            "seeded_from_branch_capture": {
                "type": "boolean",
                "default": False,
                "description": "True when invoked as a subworkflow by the pre-PR capture, which supplies a candidate principle to test against the corpus.",
            },
        },
        "roles": {
            "corpus-scanner": {
                "description": "Scans one corpus shard for repeated caveats and records where each occurrence lives.",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "medium",
                "authority": "advisory",
                "independence": "independent",
                "tool_permissions": [
                    "Read",
                    "Grep",
                    "Glob",
                    "Write(command-center/knowledge/**)",
                ],
            },
            "cluster-synthesiser": {
                "description": "Clusters occurrences into candidate principles. This is the subjective step and is labelled as such.",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "voting",
                "independence": "informed",
                "tool_permissions": ["Read", "Write(command-center/knowledge/**)"],
            },
            "script-first-auditor": {
                "description": "Holds the veto that turns an enforceable principle into a SCRIPT rather than a rule.",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "veto",
                "independence": "independent",
                "tool_permissions": [
                    "Read",
                    "Bash:python",
                    "Write(command-center/knowledge/**)",
                ],
                "speaking_rights": "always",
            },
            "dedupe-auditor": {
                "description": "Refutes a proposal that restates an existing rule, and distinguishes 'new rule' from 'existing rule needs updating'.",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "veto",
                "independence": "cross-examining",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Grep", "mcp__codex__codex"],
            },
        },
        "tool_policy": tool_policy(
            allow=[
                "Read",
                "Grep",
                "Glob",
                "Bash:python",
                "Write(command-center/knowledge/**)",
                "mcp__codex__codex",
            ],
            deny=["Bash", "Edit", "WebFetch", "Bash:git"],
            network="none",
            write_paths=[f"{root}/**"],
            forbid_write_paths=["skills/**", "rules/**"],
            source_policy={"offline_only": True, "require_provenance": True},
        ),
        "model_routing": {
            "strategy": "vendor-diverse",
            "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
            "routes": [
                {
                    "when": "stage_role == dedupe-auditor",
                    "target": {
                        "model": "gpt-5-codex",
                        "vendor": "openai",
                        "effort": "high",
                    },
                    "reason": "the synthesiser that clustered a principle will not see that it already exists as a rule",
                },
                {
                    "when": "stage_role == corpus-scanner",
                    "target": {
                        "model": "opus",
                        "vendor": "anthropic",
                        "effort": "medium",
                    },
                    "reason": "scanning is bounded pattern work; the judgement is in the clustering",
                },
            ],
            "forbid_downgrade_below": "opus",
        },
        "gates": {
            "cross-cutting-only": gate_expr(
                "single_skill_principles_promoted == 0",
                "fail",
            ),
            "script-beats-rule": gate_expr(
                "enforceable_principles_proposed_as_rules == 0",
                "repair",
            ),
            "no-restatement-of-existing": gate_expr(
                "proposals_restating_existing_rule == 0",
                "repair",
            ),
            "within-context-budget": gate_expr(
                "always_on_rule_lines <= rule_line_budget",
                "escalate-to-human",
            ),
        },
        "stages": [
            {
                "id": "scan-corpus",
                "title": "S0 - scan the corpus for repeated caveats",
                "kind": "fanout",
                "over": {
                    "source": "param",
                    "ref": "skill_corpus",
                    "item_var": "corpus_shard",
                    "key_field": "corpus_shard",
                },
                "max_concurrency": 8,
                "arrival_stagger_ms": 100,
                "max_items": 128,
                "on_item_failure": "continue",
                "body": [
                    {
                        "id": "scan-shard",
                        "title": "Scan one corpus shard",
                        "kind": "task",
                        "role": "corpus-scanner",
                        "timeout_seconds": 1800,
                        "tool_permissions": [
                            "Read",
                            "Grep",
                            "Glob",
                            "Write(command-center/knowledge/**)",
                        ],
                        "cache": cache(
                            f"{root}/cache/shards",
                            ["stage_id", "item_key", "inputs_hash", "tool_versions"],
                            ttl=604800,
                        ),
                        "work_unit": work_unit(
                            uid=u(1),
                            title="Extract every caveat, gotcha and warning from one corpus shard with its location",
                            target="Record each caveat verbatim with the skill and file:line it came from, so a later cluster can count HOW MANY DISTINCT SKILLS exhibit it rather than how many times it was written.",
                            inputs=[
                                "item.corpus_shard",
                                "params.min_skills_for_promotion",
                            ],
                            dependencies=[],
                            model="opus",
                            vendor="anthropic",
                            role="corpus-scanner",
                            basis="recognising a caveat that is phrased differently in two skills is judgement a grep cannot do",
                            tools=[
                                "Read",
                                "Grep",
                                "Glob",
                                "Write(command-center/knowledge/**)",
                            ],
                            substrate="local-parallel",
                            timeout_seconds=1800,
                            output_path=f"{root}/caveats/shard-caveats.jsonl",
                            output_schema=_sch("caveat-audit"),
                            evidence="each caveat with its verbatim text, its owning SKILL id, and a file:line anchor",
                            tests=[
                                "a caveat repeated twice inside ONE skill counts as one skill, not two occurrences - the promotion threshold is per-skill",
                                "a caveat phrased differently in two skills is recorded as two occurrences of one candidate, not two candidates",
                            ],
                            reviewer="the cluster-synthesiser, which needs per-skill attribution to count correctly",
                            sentinel_condition="every caveat carries a skill id and a file:line anchor",
                            retry="two strikes then narrow the shard rather than re-scanning the same tree",
                            failure_classes=[
                                "shard-unreadable",
                                "anchor-missing",
                                "partial-artifact",
                            ],
                            owner_approval=False,
                            mechanism="per-skill caveat extraction with skill-level attribution for the promotion count",
                        ),
                        "produces": [
                            artifact(
                                f"{root}/caveats/shard-caveats.jsonl",
                                _sch("caveat-audit"),
                                min_bytes=32,
                                sentinel=f"SUCCESS:{u(1)}",
                                consumers=["cluster-principles"],
                            )
                        ],
                    }
                ],
                "barrier": {
                    "mode": "quorum",
                    "quorum": 0.8,
                    "on_partial": "proceed-degraded",
                    "verify_artifact_exists": True,
                },
            },
            {
                "id": "corpus-join",
                "title": "Gather the shards before clustering",
                "kind": "barrier",
                "depends_on": ["scan-corpus"],
                "barrier": {
                    "mode": "all",
                    "on_partial": "proceed-degraded",
                    "require_stages": ["scan-corpus"],
                    "verify_artifact_exists": True,
                },
                "joins": ["scan-corpus"],
            },
            {
                "id": "cluster-principles",
                "title": "S1 - cluster occurrences into candidate principles",
                "kind": "task",
                "depends_on": ["corpus-join"],
                "role": "cluster-synthesiser",
                "timeout_seconds": 2400,
                "checkpoint": True,
                "tool_permissions": ["Read", "Write(command-center/knowledge/**)"],
                "work_unit": work_unit(
                    uid=u(2),
                    title="Cluster caveats into principles and count the DISTINCT skills exhibiting each",
                    target="Group semantically equivalent caveats into candidate principles, and for each record the distinct skills that exhibit it, so the promotion threshold is a count rather than an impression.",
                    inputs=[
                        f"{root}/caveats/shard-caveats.jsonl",
                        "params.min_skills_for_promotion",
                    ],
                    dependencies=[u(1)],
                    model="opus",
                    vendor="anthropic",
                    role="cluster-synthesiser",
                    basis="clustering is the subjective step and is labelled subjective in the artifact rather than presented as measurement",
                    tools=["Read", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=2400,
                    output_path=f"{root}/candidate-principles.json",
                    output_schema=_sch("dedup-report"),
                    evidence="each candidate names the distinct skills exhibiting it with an anchor per skill, and the clustering is marked NON-DETERMINISTIC because it is model judgement",
                    tests=[
                        "a caveat present in 5 skills is surfaced as a candidate",
                        "a caveat unique to ONE skill is NOT promoted - it is recorded as single-skill detail belonging in that skill",
                        "both-states control: raising min_skills_for_promotion above the top candidate's count empties the promotion set, proving the threshold is live",
                    ],
                    reviewer="the dedupe-auditor, cross-vendor, which checks the clusters are not already rules",
                    sentinel_condition="every candidate carries a distinct-skill count with per-skill anchors",
                    retry="two strikes then emit the raw caveat groups unclustered rather than forcing a cluster",
                    failure_classes=[
                        "clustering-unstable",
                        "single-skill-promotion",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="semantic clustering with a distinct-SKILL count as the promotion threshold",
                ),
                "produces": [
                    artifact(
                        f"{root}/candidate-principles.json",
                        _sch("dedup-report"),
                        min_bytes=256,
                        sentinel=f"SUCCESS:{u(2)}",
                        consumers=[
                            "cross-cutting-gate",
                            "check-script-enforceable",
                            "dedupe-against-existing",
                        ],
                    )
                ],
            },
            {
                "id": "cross-cutting-gate",
                "title": "Single-skill detail belongs in its skill, not in a rule",
                "kind": "gate",
                "depends_on": ["cluster-principles"],
                "gate_ref": "cross-cutting-only",
            },
            {
                "id": "check-script-enforceable",
                "title": "S2 - prefer a SCRIPT: a rule competes for the always-on budget, a script does not",
                "kind": "task",
                "depends_on": ["cross-cutting-gate"],
                "role": "script-first-auditor",
                "timeout_seconds": 1800,
                "tool_permissions": [
                    "Read",
                    "Bash:python",
                    "Write(command-center/knowledge/**)",
                ],
                "work_unit": work_unit(
                    uid=u(3),
                    title="Decide for each principle whether a script could enforce it mechanically",
                    target="For each candidate, decide whether the principle is decidable by an exact algorithm - counting, set membership, byte comparison, schema validation - and if so route it to a SCRIPT rather than to a rule.",
                    inputs=[f"{root}/candidate-principles.json"],
                    dependencies=[u(2)],
                    model="opus",
                    vendor="anthropic",
                    role="script-first-auditor",
                    basis="judging decidability requires knowing what a script could actually observe, which is the veto's whole content",
                    tools=["Read", "Bash:python", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=1800,
                    output_path=f"{root}/script-enforceability.json",
                    output_schema=_sch("capability-record"),
                    evidence="for each principle, the verdict script-enforceable or judgement-only, with the exact check a script would perform when enforceable",
                    tests=[
                        "a principle stating a countable property is routed to a SCRIPT and does not reach the rule proposal",
                        "a principle requiring judgement stays a rule candidate, so the veto is not rejecting every principle",
                        "the named script check is concrete enough to implement; 'a script could check this' with no check named is not a verdict",
                    ],
                    reviewer="the dedupe-auditor, which checks a script proposal does not duplicate an existing gate",
                    sentinel_condition="every candidate carries a script-enforceable verdict and, when enforceable, the concrete check",
                    retry="two strikes then mark the principle judgement-only and record the undecided enforceability",
                    failure_classes=[
                        "enforceability-undecided",
                        "rule-bloat",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="script-first veto that removes mechanically-decidable principles from the rule surface",
                ),
                "produces": [
                    artifact(
                        f"{root}/script-enforceability.json",
                        _sch("capability-record"),
                        min_bytes=256,
                        sentinel=f"SUCCESS:{u(3)}",
                        consumers=[
                            "script-first-gate",
                            "emit-script-spec",
                            "propose-rules",
                        ],
                    )
                ],
            },
            {
                "id": "script-first-gate",
                "title": "An enforceable principle may not be proposed as a rule",
                "kind": "gate",
                "depends_on": ["check-script-enforceable"],
                "gate_ref": "script-beats-rule",
            },
            {
                "id": "emit-script-spec",
                "title": "S2b - emit a script specification for each enforceable principle",
                "kind": "task",
                "depends_on": ["script-first-gate"],
                "role": "script-first-auditor",
                "when": "enforceable_principles > 0",
                "timeout_seconds": 1800,
                "tool_permissions": [
                    "Read",
                    "Bash:python",
                    "Write(command-center/knowledge/**)",
                ],
                "work_unit": work_unit(
                    uid=u(4),
                    title="Specify the script that enforces each mechanically-decidable principle",
                    target="Write an implementable specification per enforceable principle: the inputs it enumerates, the failure it emits, and the known-bad input that proves the gate can go red.",
                    inputs=[f"{root}/script-enforceability.json"],
                    dependencies=[u(3)],
                    model="opus",
                    vendor="anthropic",
                    role="script-first-auditor",
                    basis="a specification that cannot fail closed is a permanently green gate, so the spec author must reason about the empty-input case",
                    tools=["Read", "Bash:python", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=1800,
                    output_path=f"{root}/script-specs.json",
                    output_schema=_sch("contract-spec"),
                    evidence="per script: the input enumeration, the fail-closed behaviour on an empty walk, the terminal marker it prints, and a named known-bad input",
                    tests=[
                        "each spec names a known-bad input that makes the gate exit non-zero - a gate that has never gone red is indistinguishable from a no-op",
                        "each spec fails CLOSED on an empty input walk rather than reporting nothing-found as a pass",
                    ],
                    reviewer="the dedupe-auditor, checking the script does not duplicate an existing gate",
                    sentinel_condition="every enforceable principle has a spec with a fail-closed rule and a known-bad input",
                    retry="two strikes then downgrade the principle to judgement-only rather than shipping an unfalsifiable gate spec",
                    failure_classes=[
                        "gate-spec-unfalsifiable",
                        "no-op-gate",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="script specification carrying its own fail-closed rule and a known-bad input",
                    not_a_duplicate_because="the enforceability audit DECIDES whether a script is possible; this writes the spec that makes it falsifiable, which is where a no-op gate would otherwise be born",
                ),
                "produces": [
                    artifact(
                        f"{root}/script-specs.json",
                        _sch("contract-spec"),
                        min_bytes=256,
                        sentinel=f"SUCCESS:{u(4)}",
                        consumers=["command-center/MANIFEST.json"],
                    )
                ],
            },
            {
                "id": "dedupe-against-existing",
                "title": "S3 - dedupe against the existing rules; distinguish NEW from NEEDS-UPDATE",
                "kind": "task",
                "depends_on": ["script-first-gate"],
                "role": "dedupe-auditor",
                "timeout_seconds": 2400,
                "tool_permissions": ["Read", "Grep", "mcp__codex__codex"],
                "work_unit": work_unit(
                    uid=u(5),
                    title="Refute any proposal that already exists as a rule, and separate updates from additions",
                    target="For each surviving principle, decide NEW, RESTATES-EXISTING or EXISTING-NEEDS-UPDATE by searching the rules tree, so the sweep cannot rediscover a rule it already wrote.",
                    inputs=[
                        f"{root}/script-enforceability.json",
                        "params.existing_rules",
                    ],
                    dependencies=[u(3)],
                    model="gpt-5-codex",
                    vendor="openai",
                    role="dedupe-auditor",
                    basis="the synthesiser that just clustered a principle is the least likely to notice it already exists",
                    tools=["Read", "Grep", "mcp__codex__codex"],
                    substrate="local-serialized",
                    timeout_seconds=2400,
                    output_path=f"{root}/dedupe-audit.json",
                    output_schema=_sch("dedup-audit"),
                    evidence="for each RESTATES verdict, the existing rule file:line that already says it; for each NEEDS-UPDATE, the clause that is now wrong",
                    tests=[
                        "the dedupe control: a principle that already exists as a rule is caught and cited - if the sweep rediscovers an existing rule, the dedupe step is broken",
                        "an existing rule whose content is now WRONG is classified NEEDS-UPDATE, not as a new rule alongside the stale one",
                        "both-states control: a genuinely novel principle is classified NEW, so the auditor is not rejecting everything",
                    ],
                    reviewer="the cluster-synthesiser, which may contest a RESTATES verdict with a distinguishing mechanism",
                    sentinel_condition="every surviving principle carries one of the three verdicts with a citation where applicable",
                    retry="two strikes then mark the principle CONTESTED and let the owner decide rather than double-adding",
                    failure_classes=[
                        "duplicate-rule-proposed",
                        "detector-failure",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="cross-vendor dedupe with a three-way NEW / RESTATES / NEEDS-UPDATE verdict",
                ),
                "produces": [
                    artifact(
                        f"{root}/dedupe-audit.json",
                        _sch("dedup-audit"),
                        min_bytes=256,
                        sentinel=f"SUCCESS:{u(5)}",
                        consumers=[
                            "dedupe-gate",
                            "update-existing-rule",
                            "propose-rules",
                        ],
                    )
                ],
            },
            {
                "id": "dedupe-gate",
                "title": "A new rule must not restate an existing one",
                "kind": "gate",
                "depends_on": ["dedupe-against-existing"],
                "gate_ref": "no-restatement-of-existing",
            },
            {
                "id": "update-existing-rule",
                "title": "S3b - an existing rule that is now wrong is UPDATED, not duplicated",
                "kind": "task",
                "depends_on": ["dedupe-gate"],
                "role": "cluster-synthesiser",
                "when": "existing_rules_needing_update > 0",
                "timeout_seconds": 1800,
                "tool_permissions": ["Read", "Write(command-center/knowledge/**)"],
                "work_unit": work_unit(
                    uid=u(6),
                    title="Propose a correction to each existing rule the sweep found to be stale",
                    target="For each EXISTING-NEEDS-UPDATE verdict, propose the corrected clause and record what the old clause claimed, so the correction is traceable and the stale guidance is retired rather than silently overwritten.",
                    inputs=[f"{root}/dedupe-audit.json", "params.existing_rules"],
                    dependencies=[u(5)],
                    model="opus",
                    vendor="anthropic",
                    role="cluster-synthesiser",
                    basis="deciding what an updated clause should say is authoring work, not a mechanical patch",
                    tools=["Read", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=1800,
                    output_path=f"{root}/rule-updates.json",
                    output_schema=_sch("supersession-graph"),
                    evidence="the old clause verbatim, the proposed replacement, and the observation that made the old one wrong",
                    tests=[
                        "the old clause is recorded verbatim, so a corrected rule cannot be silently rewritten as though it was always right",
                        "a rule update does not increase the always-on line count unless the budget gate allows it",
                    ],
                    reviewer="the dedupe-auditor, which verifies the update targets the rule it cited",
                    sentinel_condition="every NEEDS-UPDATE verdict has a proposed replacement plus the old clause recorded",
                    retry="two strikes then propose the correction as a comment on the rule rather than a rewrite",
                    failure_classes=[
                        "supersession-dangling",
                        "rule-bloat",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="in-place rule correction with the superseded clause recorded verbatim",
                ),
                "produces": [
                    artifact(
                        f"{root}/rule-updates.json",
                        _sch("supersession-graph"),
                        min_bytes=128,
                        sentinel=f"SUCCESS:{u(6)}",
                        consumers=["propose-rules"],
                    )
                ],
            },
            {
                "id": "propose-rules",
                "title": "S4 - propose the surviving rules within the context budget",
                "kind": "task",
                "depends_on": ["dedupe-gate", "update-existing-rule"],
                "role": "cluster-synthesiser",
                "timeout_seconds": 1800,
                "tool_permissions": ["Read", "Write(command-center/knowledge/**)"],
                "work_unit": work_unit(
                    uid=u(7),
                    title="Emit the rule proposals with their line cost and displacement plan",
                    target="Write the surviving rules with a measured line cost, and when the total would exceed rule_line_budget, name what each new rule DISPLACES rather than assuming the budget will stretch.",
                    inputs=[
                        f"{root}/dedupe-audit.json",
                        f"{root}/rule-updates.json",
                        "params.rule_line_budget",
                    ],
                    dependencies=[u(5), u(6)],
                    model="opus",
                    vendor="anthropic",
                    role="cluster-synthesiser",
                    basis="choosing what to displace is a priority judgement the budget arithmetic cannot make",
                    tools=["Read", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=1800,
                    output_path=f"{root}/rule-proposals.json",
                    output_schema=_sch("owner-brief"),
                    evidence="the projected always-on line count after the change, and for an over-budget proposal the specific rule or clause it displaces",
                    tests=[
                        "an over-budget proposal names a displacement; it does not silently exceed rule_line_budget",
                        "a sweep that found no cross-cutting principle proposes NOTHING and says so, rather than promoting a single-skill detail to justify the run",
                    ],
                    reviewer="one independent adversarial reviewer in a fresh context who recomputes the projected line count",
                    sentinel_condition="the projected line count is recorded and any overage carries a named displacement",
                    retry="two strikes then propose the highest-value rule alone rather than the whole set",
                    failure_classes=[
                        "rule-bloat",
                        "budget-exceeded",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="budget-aware rule proposal with an explicit displacement plan",
                ),
                "produces": [
                    artifact(
                        f"{root}/rule-proposals.json",
                        _sch("owner-brief"),
                        min_bytes=256,
                        sentinel=f"SUCCESS:{u(7)}",
                        consumers=["budget-gate", "command-center/MANIFEST.json"],
                    )
                ],
            },
            {
                "id": "budget-gate",
                "title": "Rules compete for the always-on context budget",
                "kind": "gate",
                "depends_on": ["propose-rules"],
                "gate_ref": "within-context-budget",
            },
        ],
        "stopping_rules": [
            {
                "id": "corpus-scanned",
                "expression": "shards_scanned >= shards_total",
                "applies_to": "workflow",
                "minimum_conditions": "single_skill_principles_promoted == 0",
                "on_stop": "complete",
            },
            {
                "id": "nothing-cross-cutting-found",
                "expression": "candidate_principles == 0",
                "applies_to": "workflow",
                "on_stop": "complete",
            },
            {
                "id": "budget-exceeded-needs-owner",
                "expression": "always_on_rule_lines > rule_line_budget",
                "applies_to": "workflow",
                "on_stop": "escalate",
            },
        ],
        "retry_policy": {
            "strategy": "two-strikes-then-pivot",
            "max_attempts": 3,
            "backoff_seconds": 20,
            "jitter": True,
            "retry_on": ["shard-unreadable", "clustering-unstable"],
            "no_retry_on": ["rule-bloat", "duplicate-rule-proposed", "budget-exceeded"],
            "pivot": {
                "after_attempts": 2,
                "enumerate_alternatives_min": 2,
                "escalate_to": "budget-gate",
            },
        },
        "failure_policy": failure_policy(
            "degrade-loudly",
            [
                "shard-unreadable",
                "rule-bloat",
                "duplicate-rule-proposed",
                "budget-exceeded",
            ],
            escalate_to="budget-gate",
            quarantine_path=f"{root}/quarantine",
        ),
        "resume": resume(
            f"{root}/checkpoints",
            "fanout-item",
            ["workflow_id", "workflow_version", "stage_id", "item_key", "inputs_hash"],
        ),
        "replay": replay_deterministic(
            20260810,
            f"{root}/replay.jsonl",
            verify="semantic-equal",
            record=["params", "inputs", "tool_calls", "tool_results", "model_outputs"],
            forbid=["clock", "random", "network", "filesystem-order"],
            on_divergence="record-discrepancy",
        ),
        "cache": cache(
            f"{root}/cache",
            [
                "workflow_version",
                "stage_id",
                "item_key",
                "inputs_hash",
                "tool_versions",
            ],
            scope="workflow",
            ttl=604800,
        ),
        "dry_run": dry_run(
            f"{root}/dry-run-plan.json",
            ["Write(command-center/knowledge/**)", "mcp__codex__codex", "Bash:python"],
            emits=["plan", "estimate", "permission-report", "graph"],
        ),
        "estimate": estimate(
            basis="static-declared",
            confidence="likely",
            cost_expected=5.0,
            cost_max=22.0,
            seconds_expected=5400,
            seconds_max=21600,
            tokens_expected=1200000,
            risk="low",
            reversibility="reversible",
            blast_radius="proposal only: skills/** and rules/** are in forbid_write_paths, so the sweep cannot edit the corpus it is reading",
            owner_approval=False,
        ),
        "portability": portability(f"{root}/export/rules-distill-sweep.bundle.json"),
        "lineage": lineage(
            [
                card(f"{LIBRARY}#BP-DOC-02", "ADOPT-AS-IS"),
                card("cmd-rules-distill", "ADOPT-AS-IS"),
                card("skill-skill-stocktake", "COMPOSE"),
            ],
            rollback_to=["cmd-rules-distill@current"],
        ),
        "outputs": {
            "candidate_rules": artifact(
                f"{root}/rule-proposals.json",
                _sch("owner-brief"),
                min_bytes=256,
                consumers=["command-center/MANIFEST.json"],
            ),
            "script_specs": artifact(
                f"{root}/script-specs.json",
                _sch("contract-spec"),
                min_bytes=256,
                consumers=["command-center/MANIFEST.json"],
            ),
            "dedupe_against_existing": artifact(
                f"{root}/dedupe-audit.json",
                _sch("dedup-audit"),
                min_bytes=256,
                consumers=["command-center/MANIFEST.json"],
            ),
        },
        "x_extensions": {
            "bp7": {
                "card": "BP-DOC-02",
                "card_index_in_library": 83,
                "family": "D16-documentation",
                "primary_category": CAT_META,
                "mechanism_signature": [
                    "corpus-wide-caveat-scan-with-skill-attribution",
                    "distinct-skill-count-promotion-threshold",
                    "script-first-veto-over-rule-proposal",
                    "cross-vendor-three-way-dedupe-verdict",
                    "always-on-line-budget-with-displacement-plan",
                ],
                "worked_example": {
                    "scenario": "Run the sweep over a 60-skill vault after a batch of new skills landed.",
                    "params": {
                        "skill_corpus": ["skills", ".agents/skills"],
                        "existing_rules": "rules/common",
                        "min_skills_for_promotion": 3,
                        "rule_line_budget": 300,
                    },
                    "expected_trace": [
                        "scan-corpus -> 2 shards, 412 caveats with skill attribution; barrier quorum 1.0",
                        "cluster-principles -> 23 candidates; 14 appear in only ONE skill and are recorded as single-skill detail",
                        "cross-cutting-gate PASS (0 single-skill principles promoted)",
                        "check-script-enforceable -> 4 of the 9 remaining are decidable by an exact check (a path exists, a marker is present, a count matches) and are routed to SCRIPTS",
                        "script-first-gate PASS (0 enforceable principles proposed as rules)",
                        "emit-script-spec -> 4 specs, each naming a known-bad input that makes the gate exit non-zero",
                        "dedupe-against-existing -> of the 5 judgement-only principles: 2 NEW, 2 RESTATES-EXISTING (cited), 1 EXISTING-NEEDS-UPDATE",
                        "dedupe-gate PASS; update-existing-rule -> 1 correction with the old clause recorded verbatim",
                        "propose-rules -> 2 new rules costing 34 lines; projected total 286 <= 300; no displacement needed",
                        "budget-gate PASS",
                    ],
                    "expected_terminal_state": "SUCCESS:DOC-8307 with 2 rules proposed, 4 scripts specified and 2 restatements rejected",
                },
                "unverified": "UNVERIFIED that the sweep does not rediscover rules it already wrote; the dedupe stage is the control and its own test is the settling experiment - run the sweep on an unchanged corpus and require it to propose ZERO new rules, because every candidate should classify as RESTATES-EXISTING on the second pass.",
                "distinct_from": {
                    "bp-doc-01": "that captures from ONE branch; this scans the WHOLE corpus for cross-skill repetition",
                    "bp-doc-03": "that reconciles one FACT stated in many places and ends in a pointer rewrite; this clusters many caveats into a new principle and can end in a SCRIPT instead of a document",
                    "BP-MNT-05": "that inventories the portfolio; this reads the portfolio's content for repeated caveats",
                },
                "flagship_test": None,
                "flagship_rationale": "NOT flagship: its convergence property (a second pass over an unchanged corpus proposes zero new rules) requires a full skill vault and two sequential runs. The script-first veto ordering, the distinct-skill threshold and the displacement requirement ARE asserted by test_bp7_slice.py.",
            }
        },
    }


# ============================================================ 84 / BP-DOC-03


def ssot_documentation_reconcile() -> dict[str, Any]:
    u = lambda n: unit_id("DOC", 84, n)  # noqa: E731
    root = "command-center/knowledge/ssot-reconcile"
    return {
        "dsl_version": "1.0.0",
        "id": "ssot-documentation-reconcile",
        "name": "Single-source-of-truth reconcile: authority by measurability, then pointer rewrite",
        "description": (
            "Find every place a fact is stated, decide which statement is authoritative, and rewrite "
            "the others as POINTERS instead of restatements. The rule that makes it more than a "
            "search-and-replace is how authority is chosen: the authoritative source is the one that "
            "can be MEASURED, not the one that is most convenient - and when no statement is "
            "measurable the fact is marked UNVERIFIED everywhere rather than one being blessed "
            "arbitrarily. A contradiction is never resolved silently: the superseded statement and "
            "its correction go into a register, which is what stops a corrected fact from being "
            "re-learned wrong. A legitimately repeated context sentence must NOT be flagged, so the "
            "pass carries its own false-positive control."
        ),
        "version": "1.0.0",
        "kind": "workflow",
        "categories": [CAT_DATA, CAT_META],
        "tags": [
            "bp-doc-03",
            "ssot",
            "contradiction",
            "superseded-register",
            "pointer-rewrite",
        ],
        "flagship": True,
        "params": {
            "fact_or_topic": {
                "type": "string",
                "required": True,
                "min_length": 3,
                "description": "The fact being reconciled, stated as the question it answers - e.g. 'how many coverage thresholds does the gate enforce'.",
            },
            "doc_roots": {
                "type": "array",
                "required": True,
                "min_items": 1,
                "items": {"type": "path"},
                "description": "Documentation roots to search. One fan-out shard per root; a missed root is a silent contradiction left live.",
            },
            "search_terms": {
                "type": "array",
                "required": True,
                "min_items": 1,
                "items": {"type": "string"},
                "description": "The literal terms and paraphrases to search for. Semantic search misses paraphrases, so the term list is explicit and auditable.",
            },
            "measurability_probe": {
                "type": "string",
                "required": True,
                "min_length": 5,
                "description": "The command or check that would MEASURE the fact. Authority is assigned to the statement this probe agrees with.",
            },
            "allow_unverified_everywhere": {
                "type": "boolean",
                "default": True,
                "description": "When no statement is measurable, mark the fact UNVERIFIED in every location rather than blessing one arbitrarily.",
            },
        },
        "roles": {
            "statement-finder": {
                "description": "Mechanically finds every statement of the fact. Deterministic search, no judgement.",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "medium",
                "authority": "advisory",
                "independence": "independent",
                "tool_permissions": [
                    "Read",
                    "Grep",
                    "Glob",
                    "Write(command-center/knowledge/**)",
                ],
            },
            "authority-adjudicator": {
                "description": "Runs the measurability probe and assigns authority to the statement it agrees with. Holds the veto over an unmeasurable blessing.",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "high",
                "authority": "judge",
                "independence": "independent",
                "tool_permissions": [
                    "Read",
                    "Grep",
                    "Bash:python",
                    "Write(command-center/knowledge/**)",
                ],
                "speaking_rights": "always",
            },
            "false-positive-auditor": {
                "description": "Distinguishes a real contradiction from a sentence that legitimately repeats context for readability.",
                "model": "gpt-5-codex",
                "vendor": "openai",
                "effort": "high",
                "authority": "veto",
                "independence": "cross-examining",
                "cross_vendor_required": True,
                "tool_permissions": ["Read", "Grep", "mcp__codex__codex"],
            },
            "rewriter": {
                "description": "Rewrites each non-authoritative statement as a pointer to the authoritative one.",
                "model": "opus",
                "vendor": "anthropic",
                "effort": "medium",
                "authority": "advisory",
                "independence": "informed",
                "tool_permissions": [
                    "Read",
                    "Edit",
                    "Write(command-center/knowledge/**)",
                ],
                "write_paths": ["docs/**", "command-center/**"],
            },
        },
        "tool_policy": tool_policy(
            allow=[
                "Read",
                "Grep",
                "Glob",
                "Edit",
                "Bash:python",
                "Write(command-center/knowledge/**)",
                "mcp__codex__codex",
            ],
            deny=["Bash", "Bash:git", "WebFetch"],
            network="none",
            write_paths=["docs/**", f"{root}/**"],
            forbid_write_paths=[
                "command-center/WORK-UNIT-CATALOG.json",
                "platform/schema/**",
            ],
            source_policy={"offline_only": True, "require_provenance": True},
        ),
        "model_routing": {
            "strategy": "vendor-diverse",
            "default": {"model": "opus", "vendor": "anthropic", "effort": "high"},
            "routes": [
                {
                    "when": "stage_role == false-positive-auditor",
                    "target": {
                        "model": "gpt-5-codex",
                        "vendor": "openai",
                        "effort": "high",
                    },
                    "reason": "the finder that flagged a sentence is the least able to see that the repetition was deliberate",
                }
            ],
            "forbid_downgrade_below": "opus",
        },
        "gates": {
            "no-legitimate-repeat-flagged": gate_expr(
                "legitimate_repeats_flagged_as_contradiction == 0",
                "repair",
            ),
            "authority-is-measurable": gate_expr(
                "authoritative_source_agrees_with_probe == true OR fact_marked_unverified_everywhere == true",
                "escalate-to-human",
            ),
            "superseded-registered": gate_expr(
                "contradictions_resolved_silently == 0 AND superseded_register_written == true",
                "fail",
            ),
            "reconcile-complete": gate_predicate_v1(list(range(1, 13)), "repair"),
        },
        "stages": [
            {
                "id": "search-statements",
                "title": "S0 - find EVERY statement of the fact, mechanically",
                "kind": "fanout",
                "over": {
                    "source": "param",
                    "ref": "doc_roots",
                    "item_var": "doc_root",
                    "key_field": "doc_root",
                },
                "max_concurrency": 6,
                "arrival_stagger_ms": 100,
                "max_items": 64,
                "on_item_failure": "abort",
                "body": [
                    {
                        "id": "search-one-root",
                        "title": "Search one documentation root",
                        "kind": "task",
                        "role": "statement-finder",
                        "timeout_seconds": 1200,
                        "tool_permissions": [
                            "Read",
                            "Grep",
                            "Glob",
                            "Write(command-center/knowledge/**)",
                        ],
                        "cache": cache(
                            f"{root}/cache/search",
                            ["stage_id", "item_key", "inputs_hash", "tool_versions"],
                            ttl=86400,
                        ),
                        "work_unit": work_unit(
                            uid=u(1),
                            title="Find every statement of the fact in one documentation root",
                            target="Search one root for every declared term and paraphrase, recording each hit with its file:line and the VALUE it asserts, so the comparison step operates on values rather than on prose.",
                            inputs=[
                                "item.doc_root",
                                "params.search_terms",
                                "params.fact_or_topic",
                            ],
                            dependencies=[],
                            model="opus",
                            vendor="anthropic",
                            role="statement-finder",
                            basis="extracting the asserted VALUE from a sentence is judgement; finding the sentence is not",
                            tools=[
                                "Read",
                                "Grep",
                                "Glob",
                                "Write(command-center/knowledge/**)",
                            ],
                            substrate="local-parallel",
                            timeout_seconds=1200,
                            output_path=f"{root}/statements/found-statements.jsonl",
                            output_schema=_sch("contradiction-pairs"),
                            evidence="every hit with file:line, the verbatim sentence, and the extracted value - plus the exact search terms used, so a missed paraphrase is diagnosable",
                            tests=[
                                "all statements of a fact stated with three different values are found, not just the first two",
                                "the search terms are recorded, so a paraphrase the term list could not match is a known gap rather than an invisible one",
                                "both-states control: a root with no statement of the fact yields zero hits and says so, rather than the shard being reported as unsearched",
                            ],
                            reviewer="the false-positive-auditor, which reads the verbatim sentences",
                            sentinel_condition="every hit carries file:line, the sentence and an extracted value or an explicit no-value marker",
                            retry="two strikes then widen the term list once and record the widening",
                            failure_classes=[
                                "paraphrase-missed",
                                "root-unreadable",
                                "partial-artifact",
                            ],
                            owner_approval=False,
                            mechanism="deterministic multi-term search with per-hit value extraction and a recorded term list",
                        ),
                        "produces": [
                            artifact(
                                f"{root}/statements/found-statements.jsonl",
                                _sch("contradiction-pairs"),
                                min_bytes=32,
                                sentinel=f"SUCCESS:{u(1)}",
                                consumers=[
                                    "search-join",
                                    "compare-values",
                                    "audit-false-positives",
                                ],
                            )
                        ],
                    }
                ],
                "barrier": {
                    "mode": "all",
                    "on_partial": "fail",
                    "reject_result_matching": [
                        "started in the background",
                        "no files found",
                    ],
                    "verify_artifact_exists": True,
                },
            },
            {
                "id": "search-join",
                "title": "Every root must be searched - a missed root leaves a contradiction live",
                "kind": "barrier",
                "depends_on": ["search-statements"],
                "barrier": {
                    "mode": "all",
                    "on_partial": "fail",
                    "require_stages": ["search-statements"],
                    "verify_artifact_exists": True,
                },
                "joins": ["search-statements"],
            },
            {
                "id": "compare-values",
                "title": "S1 - compare the asserted values and enumerate the contradictions",
                "kind": "task",
                "depends_on": ["search-join"],
                "role": "statement-finder",
                "timeout_seconds": 1200,
                "checkpoint": True,
                "tool_permissions": [
                    "Read",
                    "Bash:python",
                    "Write(command-center/knowledge/**)",
                ],
                "work_unit": work_unit(
                    uid=u(2),
                    title="Group the statements by asserted value and enumerate the disagreements",
                    target="Partition the found statements by the value they assert and list every distinct value with its locations, so the size of the disagreement is a count rather than an impression.",
                    inputs=[
                        f"{root}/statements/found-statements.jsonl",
                        "params.fact_or_topic",
                    ],
                    dependencies=[u(1)],
                    model="opus",
                    vendor="anthropic",
                    role="statement-finder",
                    basis="grouping by value is mechanical, so it is written as an exact partition rather than an LLM judgement over the whole set",
                    tools=["Read", "Bash:python", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=1200,
                    output_path=f"{root}/value-comparison.json",
                    output_schema=_sch("contradiction-report"),
                    evidence="a value-to-locations map covering every found statement, with the count of distinct values stated explicitly",
                    tests=[
                        "a fact stated with three different values yields three groups, and every found statement lands in exactly one",
                        "a statement with no extractable value is grouped as NO-VALUE rather than silently dropped",
                    ],
                    reviewer="the authority-adjudicator, which needs the value groups to compare against the probe",
                    sentinel_condition="every found statement is assigned to exactly one value group and the distinct-value count is recorded",
                    retry="two strikes then emit the ungrouped statement list rather than forcing a partition",
                    failure_classes=[
                        "value-unextractable",
                        "coverage-unreconciled",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="exact value partition over found statements with a distinct-value count",
                ),
                "produces": [
                    artifact(
                        f"{root}/value-comparison.json",
                        _sch("contradiction-report"),
                        min_bytes=256,
                        sentinel=f"SUCCESS:{u(2)}",
                        consumers=["audit-false-positives", "designate-authority"],
                    )
                ],
            },
            {
                "id": "audit-false-positives",
                "title": "A sentence that legitimately repeats context is NOT a contradiction",
                "kind": "task",
                "depends_on": ["compare-values"],
                "role": "false-positive-auditor",
                "timeout_seconds": 1800,
                "tool_permissions": ["Read", "Grep", "mcp__codex__codex"],
                "work_unit": work_unit(
                    uid=u(3),
                    title="Separate real contradictions from deliberate context repetition",
                    target="For each flagged statement decide whether it CONTRADICTS the others or merely repeats agreed context for readability, because flagging a legitimate repeat turns a reconcile into vandalism.",
                    inputs=[
                        f"{root}/value-comparison.json",
                        f"{root}/statements/found-statements.jsonl",
                    ],
                    dependencies=[u(1), u(2)],
                    model="gpt-5-codex",
                    vendor="openai",
                    role="false-positive-auditor",
                    basis="the finder that flagged the sentence cannot see that the repetition was deliberate; a different vendor can",
                    tools=["Read", "Grep", "mcp__codex__codex"],
                    substrate="local-serialized",
                    timeout_seconds=1800,
                    output_path=f"{root}/false-positive-audit.json",
                    output_schema=_sch("confirmation-audit"),
                    evidence="per statement, a CONTRADICTS or LEGITIMATE-REPEAT verdict with the surrounding context that justifies it",
                    tests=[
                        "a legitimately-repeated context sentence with the SAME value is classified LEGITIMATE-REPEAT and is not rewritten",
                        "a statement with a DIFFERENT value is classified CONTRADICTS even when its surrounding prose reads like context",
                        "both-states control: a real three-way disagreement yields three CONTRADICTS verdicts, so the auditor is not absolving everything",
                    ],
                    reviewer="the statement-finder, which may contest a LEGITIMATE-REPEAT verdict by citing the differing value",
                    sentinel_condition="every statement carries one of the two verdicts with its justifying context",
                    retry="two strikes then classify as LEGITIMATE-REPEAT, since a missed reconcile is recoverable and a wrong rewrite is not",
                    failure_classes=[
                        "false-positive-contradiction",
                        "detector-failure",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="cross-vendor contradiction-versus-legitimate-repeat discrimination",
                    not_a_duplicate_because="the value comparison partitions by VALUE mechanically; this decides whether a same-or-similar sentence was MEANT to restate, which no partition can answer",
                ),
                "produces": [
                    artifact(
                        f"{root}/false-positive-audit.json",
                        _sch("confirmation-audit"),
                        min_bytes=256,
                        sentinel=f"SUCCESS:{u(3)}",
                        consumers=[
                            "false-positive-gate",
                            "designate-authority",
                            "rewrite-as-pointers",
                        ],
                    )
                ],
            },
            {
                "id": "false-positive-gate",
                "title": "The pass carries its own false-positive control",
                "kind": "gate",
                "depends_on": ["audit-false-positives"],
                "gate_ref": "no-legitimate-repeat-flagged",
            },
            {
                "id": "designate-authority",
                "title": "S2 - authority goes to the MEASURABLE statement, not the convenient one",
                "kind": "task",
                "depends_on": ["false-positive-gate"],
                "role": "authority-adjudicator",
                "timeout_seconds": 1800,
                "tool_permissions": [
                    "Read",
                    "Grep",
                    "Bash:python",
                    "Write(command-center/knowledge/**)",
                ],
                "work_unit": work_unit(
                    uid=u(4),
                    title="Run the measurability probe and assign authority to the statement it agrees with",
                    target="Execute the declared measurability probe, compare its result against each value group, and designate the agreeing statement authoritative - or, when the probe agrees with none, mark the fact UNVERIFIED everywhere rather than blessing a statement arbitrarily.",
                    inputs=[
                        f"{root}/value-comparison.json",
                        f"{root}/false-positive-audit.json",
                        "params.measurability_probe",
                        "params.allow_unverified_everywhere",
                    ],
                    dependencies=[u(2), u(3)],
                    model="opus",
                    vendor="anthropic",
                    role="authority-adjudicator",
                    basis="the judge authority is where the anti-convenience rule is enforced and cannot be delegated to the finder",
                    tools=[
                        "Read",
                        "Grep",
                        "Bash:python",
                        "Write(command-center/knowledge/**)",
                    ],
                    substrate="local-serialized",
                    timeout_seconds=1800,
                    output_path=f"{root}/authority-designation.json",
                    output_schema=_sch("decision-record"),
                    evidence="the probe command, its verbatim output, and which value group it agrees with - or an explicit statement that it agrees with none",
                    tests=[
                        "the designated authority is the statement the probe AGREES with, even when another location is more prominent or more convenient to cite",
                        "when the probe agrees with no statement, the fact is marked UNVERIFIED in every location and no statement is designated authoritative",
                        "the probe's own output is recorded verbatim, so a later reader can re-run it rather than trusting this designation",
                    ],
                    reviewer="the false-positive-auditor, cross-examining whether the probe actually measures the fact in question",
                    sentinel_condition="one value group is designated authoritative with the probe output recorded, or the fact is marked UNVERIFIED everywhere",
                    retry="two strikes then mark UNVERIFIED everywhere rather than designating on a third attempt at the same probe",
                    failure_classes=[
                        "no-measurable-source",
                        "probe-measures-wrong-thing",
                        "detector-failure",
                    ],
                    owner_approval=False,
                    mechanism="probe-driven authority designation with UNVERIFIED-everywhere as the honest fallback",
                ),
                "produces": [
                    artifact(
                        f"{root}/authority-designation.json",
                        _sch("decision-record"),
                        min_bytes=256,
                        sentinel=f"SUCCESS:{u(4)}",
                        consumers=[
                            "measurability-gate",
                            "rewrite-as-pointers",
                            "register-superseded",
                        ],
                    )
                ],
            },
            {
                "id": "measurability-gate",
                "title": "No measurable source means UNVERIFIED everywhere, not an arbitrary blessing",
                "kind": "gate",
                "depends_on": ["designate-authority"],
                "gate_ref": "authority-is-measurable",
            },
            {
                "id": "rewrite-as-pointers",
                "title": "S3 - rewrite every non-authoritative statement as a POINTER",
                "kind": "loop",
                "depends_on": ["measurability-gate"],
                "loop_var": "rewrite_pass",
                "body": [
                    {
                        "id": "rewrite-one-batch",
                        "title": "Rewrite one batch of restatements into pointers",
                        "kind": "task",
                        "role": "rewriter",
                        "timeout_seconds": 1800,
                        "tool_permissions": [
                            "Read",
                            "Edit",
                            "Write(command-center/knowledge/**)",
                        ],
                        "work_unit": work_unit(
                            uid=u(5),
                            title="Replace a batch of restatements with pointers to the authoritative source",
                            target="Rewrite each CONTRADICTS statement as a pointer to the authoritative location, leaving LEGITIMATE-REPEAT sentences untouched, and record every edit so the pass is reversible.",
                            inputs=[
                                f"{root}/authority-designation.json",
                                f"{root}/false-positive-audit.json",
                            ],
                            dependencies=[u(3), u(4)],
                            model="opus",
                            vendor="anthropic",
                            role="rewriter",
                            basis="writing a pointer that still reads well in its surrounding prose is authoring work, not substitution",
                            tools=[
                                "Read",
                                "Edit",
                                "Write(command-center/knowledge/**)",
                            ],
                            substrate="local-serialized",
                            timeout_seconds=1800,
                            output_path=f"{root}/pointer-rewrites.json",
                            output_schema=_sch("traceability-matrix"),
                            evidence="per edit: the file:line, the removed value, the pointer written, and the before-text so the rewrite is reversible",
                            tests=[
                                "a LEGITIMATE-REPEAT sentence is left byte-identical",
                                "each rewritten location points at the authoritative file:line and no longer asserts its own value",
                                "the before-text is recorded for every edit, so the whole pass can be reverted",
                            ],
                            reviewer="the authority-adjudicator, which re-reads a sample of rewrites against the designation",
                            sentinel_condition="every CONTRADICTS statement is either rewritten as a pointer or listed as unrewritable with a reason",
                            retry="two strikes then leave the statement in place and list it as an unresolved restatement",
                            failure_classes=[
                                "rewrite-broke-prose",
                                "pointer-dangling",
                                "partial-artifact",
                            ],
                            owner_approval=False,
                            mechanism="reversible pointer rewrite that spares legitimate repeats",
                        ),
                        "produces": [
                            artifact(
                                f"{root}/pointer-rewrites.json",
                                _sch("traceability-matrix"),
                                min_bytes=128,
                                sentinel=f"SUCCESS:{u(5)}",
                                consumers=["register-superseded", "drift-check"],
                            )
                        ],
                    }
                ],
                "convergence": {
                    "max_iterations": 10,
                    "min_iterations": 1,
                    "converged_when": "unresolved_restatements == 0",
                    "no_progress_rounds": 2,
                    "metrics": [
                        {
                            "name": "unresolved_restatements",
                            "direction": "decrease",
                            "target": 0,
                        }
                    ],
                    "on_no_convergence": "emit-partial",
                },
            },
            {
                "id": "register-superseded",
                "title": "S4 - a contradiction is never resolved silently",
                "kind": "task",
                "depends_on": ["rewrite-as-pointers"],
                "role": "authority-adjudicator",
                "timeout_seconds": 1200,
                "tool_permissions": ["Read", "Write(command-center/knowledge/**)"],
                "work_unit": work_unit(
                    uid=u(6),
                    title="Write the superseded-guidance register: what each location used to claim, and the correction",
                    target="Record every superseded statement with its old value, its new pointer and the correction, so a corrected fact cannot be re-learned wrong from a cached copy or an old branch.",
                    inputs=[
                        f"{root}/pointer-rewrites.json",
                        f"{root}/authority-designation.json",
                    ],
                    dependencies=[u(4), u(5)],
                    model="opus",
                    vendor="anthropic",
                    role="authority-adjudicator",
                    basis="the register is the durable half of the reconcile and belongs to the role that assigned authority",
                    tools=["Read", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=1200,
                    output_path=f"{root}/superseded-register.json",
                    output_schema=_sch("supersession-graph"),
                    evidence="one register entry per superseded statement carrying its old value verbatim, the authoritative value, and the probe that settled it",
                    tests=[
                        "every rewritten location has a register entry; a rewrite with no entry is a silent resolution and fails the gate",
                        "the old value is recorded verbatim, so someone who remembers the old number can find out why it changed",
                    ],
                    reviewer="one independent adversarial reviewer in a fresh context who samples entries and re-runs the probe",
                    sentinel_condition="the register covers every rewritten location with old value, new value and the settling probe",
                    retry="two strikes then fail: an unregistered supersession defeats the purpose of the pass",
                    failure_classes=[
                        "silent-resolution",
                        "supersession-dangling",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="superseded-guidance register carrying the old value and the settling probe",
                ),
                "produces": [
                    artifact(
                        f"{root}/superseded-register.json",
                        _sch("supersession-graph"),
                        min_bytes=256,
                        sentinel=f"SUCCESS:{u(6)}",
                        consumers=["superseded-gate", "command-center/MANIFEST.json"],
                    )
                ],
            },
            {
                "id": "superseded-gate",
                "title": "Silent resolution is how a corrected fact gets re-learned wrong",
                "kind": "gate",
                "depends_on": ["register-superseded"],
                "gate_ref": "superseded-registered",
            },
            {
                "id": "drift-check",
                "title": "S4b - add a drift check so the NEXT divergence is detected, not discovered",
                "kind": "task",
                "depends_on": ["superseded-gate"],
                "role": "authority-adjudicator",
                "timeout_seconds": 1200,
                "tool_permissions": [
                    "Read",
                    "Bash:python",
                    "Write(command-center/knowledge/**)",
                ],
                "work_unit": work_unit(
                    uid=u(7),
                    title="Emit a drift check that fails when the fact is re-stated away from the authoritative source",
                    target="Specify a check that re-runs the measurability probe and the search, and fails when any location asserts a value again instead of pointing - so the next divergence is caught rather than rediscovered months later.",
                    inputs=[
                        f"{root}/superseded-register.json",
                        f"{root}/pointer-rewrites.json",
                        "params.measurability_probe",
                    ],
                    dependencies=[u(5), u(6)],
                    model="opus",
                    vendor="anthropic",
                    role="authority-adjudicator",
                    basis="designing a check that fails closed on an empty search walk is the difference between a gate and a no-op",
                    tools=["Read", "Bash:python", "Write(command-center/knowledge/**)"],
                    substrate="local-serialized",
                    timeout_seconds=1200,
                    output_path=f"{root}/drift-check-spec.json",
                    output_schema=_sch("drift-report"),
                    evidence="the check's input enumeration, its fail-closed rule on an empty walk, its terminal marker, and a named known-bad state that makes it exit non-zero",
                    tests=[
                        "the spec names a known-bad state (a location re-asserting a value) that makes the check FAIL - a check that has never gone red is indistinguishable from a no-op",
                        "an empty search walk fails CLOSED rather than reporting nothing-found as a pass",
                    ],
                    reviewer="the false-positive-auditor, checking the drift check would not fire on a legitimate repeat",
                    sentinel_condition="the spec carries a fail-closed rule, a terminal marker and a named known-bad state",
                    retry="two strikes then emit the check as advisory-only and say so, rather than shipping an unfalsifiable gate",
                    failure_classes=[
                        "no-op-gate",
                        "gate-spec-unfalsifiable",
                        "partial-artifact",
                    ],
                    owner_approval=False,
                    mechanism="fail-closed drift-check specification with a named known-bad state",
                ),
                "produces": [
                    artifact(
                        f"{root}/drift-check-spec.json",
                        _sch("drift-report"),
                        min_bytes=128,
                        sentinel=f"SUCCESS:{u(7)}",
                        consumers=[
                            "reconcile-complete-gate",
                            "command-center/MANIFEST.json",
                        ],
                    )
                ],
            },
            {
                "id": "reconcile-complete-gate",
                "title": "The shared completion predicate over the reconcile",
                "kind": "gate",
                "depends_on": ["drift-check"],
                "gate_ref": "reconcile-complete",
            },
        ],
        "stopping_rules": [
            {
                "id": "all-statements-reconciled",
                "expression": "unresolved_restatements == 0 AND superseded_register_written == true",
                "applies_to": "workflow",
                "minimum_conditions": "roots_searched >= roots_total",
                "on_stop": "complete",
            },
            {
                "id": "no-measurable-source-marks-unverified",
                "expression": "authoritative_source_agrees_with_probe == false AND fact_marked_unverified_everywhere == true",
                "applies_to": "workflow",
                "on_stop": "emit-partial",
            },
            {
                "id": "false-positive-halts-the-rewrite",
                "expression": "legitimate_repeats_flagged_as_contradiction > 0",
                "applies_to": "workflow",
                "on_stop": "escalate",
            },
        ],
        "retry_policy": {
            "strategy": "two-strikes-then-pivot",
            "max_attempts": 3,
            "backoff_seconds": 15,
            "jitter": True,
            "retry_on": ["paraphrase-missed", "value-unextractable"],
            "no_retry_on": [
                "silent-resolution",
                "false-positive-contradiction",
                "no-measurable-source",
            ],
            "pivot": {
                "after_attempts": 2,
                "enumerate_alternatives_min": 2,
                "escalate_to": "measurability-gate",
            },
        },
        "failure_policy": failure_policy(
            "degrade-loudly",
            [
                "paraphrase-missed",
                "no-measurable-source",
                "silent-resolution",
                "false-positive-contradiction",
            ],
            escalate_to="measurability-gate",
            quarantine_path=f"{root}/quarantine",
        ),
        "resume": resume(
            f"{root}/checkpoints",
            "fanout-item",
            ["workflow_id", "workflow_version", "stage_id", "item_key", "inputs_hash"],
        ),
        "replay": replay_deterministic(
            20260810,
            f"{root}/replay.jsonl",
            verify="semantic-equal",
            record=["params", "inputs", "tool_calls", "tool_results", "model_outputs"],
            forbid=["clock", "random", "network", "filesystem-order"],
            on_divergence="record-discrepancy",
        ),
        "cache": cache(
            f"{root}/cache",
            [
                "workflow_version",
                "stage_id",
                "item_key",
                "inputs_hash",
                "tool_versions",
            ],
            scope="workflow",
            ttl=86400,
        ),
        "dry_run": dry_run(
            f"{root}/dry-run-plan.json",
            [
                "Edit",
                "Write(command-center/knowledge/**)",
                "mcp__codex__codex",
                "Bash:python",
            ],
            emits=["plan", "artifact-diff", "permission-report", "graph"],
        ),
        "estimate": estimate(
            basis="static-declared",
            confidence="likely",
            cost_expected=2.6,
            cost_max=12.0,
            seconds_expected=3600,
            seconds_max=14400,
            tokens_expected=500000,
            risk="low",
            reversibility="reversible",
            blast_radius="edits documentation under docs/** and command-center/**; every edit records its before-text so the whole pass is revertible, and the schema tree is in forbid_write_paths",
            owner_approval=False,
        ),
        "portability": portability(
            f"{root}/export/ssot-documentation-reconcile.bundle.json"
        ),
        "lineage": lineage(
            [
                card(f"{LIBRARY}#BP-DOC-03", "DISTILL"),
                card("exec-reframe-sota-and-ssot#track-B", "DISTILL"),
                card("cmd-update-docs", "COMPOSE"),
                card("tool-harness-drift", "COMPOSE"),
            ]
        ),
        "outputs": {
            "statements": artifact(
                f"{root}/value-comparison.json",
                _sch("contradiction-report"),
                min_bytes=256,
                consumers=["command-center/MANIFEST.json"],
            ),
            "rewrite_plan": artifact(
                f"{root}/pointer-rewrites.json",
                _sch("traceability-matrix"),
                min_bytes=128,
                consumers=["command-center/MANIFEST.json"],
            ),
            "superseded_register": artifact(
                f"{root}/superseded-register.json",
                _sch("supersession-graph"),
                min_bytes=256,
                consumers=["command-center/MANIFEST.json", "pre-pr-knowledge-capture"],
            ),
        },
        "x_extensions": {
            "bp7": {
                "card": "BP-DOC-03",
                "card_index_in_library": 84,
                "family": "D16-documentation",
                "primary_category": CAT_DATA,
                "mechanism_signature": [
                    "exhaustive-multi-term-statement-search",
                    "exact-value-partition-of-statements",
                    "cross-vendor-legitimate-repeat-control",
                    "authority-by-measurability-not-convenience",
                    "superseded-guidance-register-plus-drift-check",
                ],
                "worked_example": {
                    "scenario": "This program's own coverage count: one doc says the gate enforces 5 thresholds, two others say 6, and a fourth sentence repeats 'the gate enforces the project thresholds' as context without a number.",
                    "params": {
                        "fact_or_topic": "how many coverage thresholds does the gate enforce",
                        "doc_roots": ["docs", "command-center", "rules"],
                        "search_terms": [
                            "coverage threshold",
                            "thresholds enforced",
                            "coverage-thresholds.json",
                        ],
                        "measurability_probe": "jq '.thresholds | length' .coverage-thresholds.json",
                        "allow_unverified_everywhere": True,
                    },
                    "expected_trace": [
                        "search-statements -> 3 roots searched in parallel; 7 hits; barrier mode all, on_partial fail (a missed root would leave a contradiction live)",
                        "compare-values -> 3 groups: value 5 (1 location), value 6 (2 locations), NO-VALUE (4 locations)",
                        "audit-false-positives -> the 4 NO-VALUE sentences are LEGITIMATE-REPEAT; the 5-versus-6 pair is CONTRADICTS",
                        "false-positive-gate PASS (0 legitimate repeats flagged)",
                        "designate-authority -> the probe prints 6; the value-6 group is authoritative. Note the value-5 location was the most prominent doc, and was NOT chosen",
                        "measurability-gate PASS",
                        "rewrite-as-pointers -> pass 1 rewrites the value-5 location as a pointer; unresolved_restatements 1 -> 0; the 4 legitimate repeats are byte-identical",
                        "register-superseded -> 1 entry: old value 5, authoritative 6, settled by the recorded probe output",
                        "superseded-gate PASS; drift-check -> a spec that fails when any location asserts a bare number again, fail-closed on an empty walk",
                    ],
                    "expected_terminal_state": "SUCCESS:DOC-8407",
                },
                "unverified": "UNVERIFIED as a reusable pass - semantic search misses paraphrases, so the recorded search-term list is the honest bound on coverage rather than a claim of completeness. Settling experiment = reconcile one known-contradictory fact end to end and confirm every restatement now points at the measured source, then re-run the drift check against a deliberately re-asserted value and require it to fire.",
                "distinct_from": {
                    "BP-MNT-01": "that reconciles CODE between the live tree and the repo; this reconciles a FACT across documents and ends in a pointer rewrite",
                    "bp-doc-02": "that clusters many caveats into a new principle and can end in a SCRIPT; this takes ONE fact and adjudicates which of its statements is authoritative",
                    "bp-doc-01": "that creates new knowledge from new work; this removes duplicate statements of knowledge that already exists",
                },
                "flagship_test": "platform/lib/workflows/test_ssot_documentation_reconcile.py",
            }
        },
    }


BLUEPRINTS = [
    pre_pr_knowledge_capture,
    rules_distill_sweep,
    ssot_documentation_reconcile,
]
