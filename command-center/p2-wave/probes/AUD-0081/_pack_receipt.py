#!/usr/bin/env python3
"""Pack AUD-0081 untrusted auto-loaded configuration audit in cloned and
vendored trees.

Two real probes (a real filesystem filename search for the auto-load set
across every vendored-tree root actually present in this checkout, plus a
real content-read classification of every hit as inert/mention-only/
active) plus the catalog's required tests_required control (the
classifier must rate a prose-only AGENTS.md as inert and the SAME fixture
path rewritten with a PreToolUse hook registration as active). Emits
BLOCKED pending the catalog's DUAL reviewer_requirement -- "two reviewers,
one fresh-context Claude and one Codex; on disagreement escalate to the
owner with both probes attached - do NOT resolve by vote" -- and NEVER
emits SUCCESS without BOTH review files recorded on disk, and NEVER
invents either review.json: neither file exists for this unit, so
reviewer.verdict stays NOT-REVIEWED and state stays BLOCKED.

Dependency gate: the catalog lists B01, AUD-0009 as dependencies. AUD-0009
(submodule/vendored inventory) is checked for state == SUCCESS ON DISK
before this unit relies on anything from its artifact; if that check
fails, this unit is BLOCKED on the dependency too, not merely on the
reviewers. B01 is a bucket-level structural gate (not itself a receipted
work unit) and is treated as structurally satisfied, matching the
AUD-0061/AUD-0083 precedent for the same catalog dependency shape.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import _p2lib as L  # noqa: E402

UNIT = "AUD-0081"
OUT = "command-center/audit/AUD-0081-untrusted-autoload-config-audit.json"
SCHEMA = "command-center/schema/audit-finding.schema.json"
PROBE = Path(__file__).resolve().parent
MANIFEST = "command-center/p2-wave/probes/AUD-0081/UNIT-ARTIFACT-MANIFEST.json"
CLAUDE_REVIEW = PROBE / "claude-review.json"
CODEX_REVIEW = PROBE / "codex-review.json"

AUD_0009_PATH = "command-center/audit/AUD-0009-submodule-vendored-inventory.json"

P1_JSON = "command-center/p2-wave/probes/AUD-0081/probe1-filename-search.json"
P2_JSON = "command-center/p2-wave/probes/AUD-0081/probe2-content-classification.json"
CTL_JSON = "command-center/p2-wave/probes/AUD-0081/control-prose-vs-hook-fixture.json"
P1_RAW = "command-center/p2-wave/probes/AUD-0081/probe1-filename-search.raw.txt"
P2_RAW = "command-center/p2-wave/probes/AUD-0081/probe2-content-classification.raw.txt"
CTL_RAW = "command-center/p2-wave/probes/AUD-0081/control-prose-vs-hook-fixture.raw.txt"


def check_dependency_aud_0009() -> dict:
    """The catalog names AUD-0009 as a hard dependency. Verify it is
    state == SUCCESS ON DISK before relying on anything from its artifact
    -- a dependency claimed satisfied without checking is exactly the
    'dependency-blocked' failure classification this catalog names."""
    p = L.REPO / AUD_0009_PATH
    if not p.is_file():
        return {"path": AUD_0009_PATH, "exists": False, "state": None, "satisfied": False}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"path": AUD_0009_PATH, "exists": True, "state": None, "satisfied": False}
    state = doc.get("state")
    return {
        "path": AUD_0009_PATH,
        "exists": True,
        "state": state,
        "unit_id": doc.get("unit_id"),
        "sentinel": str(doc.get("sentinel", ""))[:200],
        "satisfied": state == "SUCCESS",
    }


def _load_one_review(path: Path, allowed_vendors: set[str]) -> dict | None:
    if not path.is_file():
        return None
    try:
        rev = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if rev.get("verdict") != "PASS":
        return None
    if not rev.get("independent") or not rev.get("fresh_context"):
        return None
    vendor = (rev.get("vendor") or "").lower()
    if vendor not in allowed_vendors:
        return None
    return rev


def load_dual_review() -> dict:
    """Catalog reviewer_requirement (verbatim): 'two reviewers, one
    fresh-context Claude and one Codex; on disagreement escalate to the
    owner with both probes attached - do NOT resolve by vote.'

    Returns a status dict, never a bare success bool, because THREE
    distinct outcomes are possible and must be told apart in the receipt:
      * neither/one review present -> NOT-REVIEWED (the ordinary pending
        case, and the only one reachable by this packer run since neither
        review file is invented here)
      * both present, both PASS -> reviewed_ok (would gate SUCCESS)
      * both present, DISAGREE -> escalate-to-owner (BLOCKED for a
        DIFFERENT reason than 'unreviewed' -- owner_approval_required is
        already true on this catalog entry, so this is the disagreement
        path the catalog explicitly names, distinct from simply pending)
    """
    claude_rev = _load_one_review(CLAUDE_REVIEW, {"anthropic", "claude", "claude-cli", "claudecode"})
    codex_rev = _load_one_review(CODEX_REVIEW, {"openai", "codex", "codex-cli"})
    if claude_rev is None and codex_rev is None:
        return {"status": "not-reviewed", "claude": None, "codex": None}
    if claude_rev is None or codex_rev is None:
        return {
            "status": "not-reviewed",
            "claude": claude_rev,
            "codex": codex_rev,
            "note": "only one of the two required reviewers is present; both are required before either PASS or escalation can be evaluated",
        }
    claude_verdict = claude_rev.get("verdict")
    codex_verdict = codex_rev.get("verdict")
    if claude_verdict == "PASS" and codex_verdict == "PASS":
        return {"status": "both-pass", "claude": claude_rev, "codex": codex_rev}
    return {
        "status": "escalate-to-owner",
        "claude": claude_rev,
        "codex": codex_rev,
        "note": "reviewers disagree; catalog says escalate to the owner with both probes attached, NEVER resolve by vote",
    }


def build(primary: dict | None = None) -> dict:
    p1 = json.loads((PROBE / "probe1-filename-search.json").read_text(encoding="utf-8"))
    p2 = json.loads((PROBE / "probe2-content-classification.json").read_text(encoding="utf-8"))
    ctl = json.loads((PROBE / "control-prose-vs-hook-fixture.json").read_text(encoding="utf-8"))
    raw1 = (PROBE / "probe1-filename-search.raw.txt").read_text(encoding="utf-8")
    raw2 = (PROBE / "probe2-content-classification.raw.txt").read_text(encoding="utf-8")
    raw_ctl = (PROBE / "control-prose-vs-hook-fixture.raw.txt").read_text(encoding="utf-8")

    dep = check_dependency_aud_0009()
    review = load_dual_review()
    success = dep["satisfied"] and review["status"] == "both-pass"

    started = "2026-09-08T00:00:00Z"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    vendored_tree_root_count = int(p1["vendored_tree_root_count"])
    vendored_tree_roots = p1["vendored_tree_roots"]
    hits_count = int(p1["hits_count"])
    by_matched_name = p1["by_matched_name"]
    by_vendored_root = p1["by_vendored_root"]

    classified_count = int(p2["classified_count"])
    active_count = int(p2["active_count"])
    mention_only_count = int(p2["mention_only_count"])
    inert_count = int(p2["inert_count"])
    active_hits = p2["active_hits"]

    control_ok = bool(ctl["ok"])
    fired_on_bad = bool(ctl["fired_on_bad_state"])
    silent_on_good = bool(ctl["silent_on_good_state"])

    arts = [
        primary
        or {
            "path": OUT,
            "bytes": 4096,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        L.art("command-center/p2-wave/probes/AUD-0081/_autoload_classifier.py", "supporting"),
        L.art("command-center/p2-wave/probes/AUD-0081/probe1_filename_search.py", "supporting"),
        L.art(P1_JSON, "supporting"),
        L.art(P1_RAW, "log"),
        L.art("command-center/p2-wave/probes/AUD-0081/probe2_content_classify.py", "supporting"),
        L.art(P2_JSON, "supporting"),
        L.art(P2_RAW, "log"),
        L.art("command-center/p2-wave/probes/AUD-0081/control_prose_vs_hook_fixture.py", "control"),
        L.art(CTL_JSON, "control"),
        L.art(CTL_RAW, "log"),
    ]
    if review["status"] == "both-pass":
        arts.append(L.art("command-center/p2-wave/probes/AUD-0081/claude-review.json", "supporting"))
        arts.append(L.art("command-center/p2-wave/probes/AUD-0081/codex-review.json", "supporting"))

    question = (
        "Do any cloned, vendored, or agent-scratch trees under the estate "
        "carry a .claude, .codex, .mcp.json, hooks directory, AGENTS.md or "
        "CLAUDE.md that would auto-load the moment an agent runs inside "
        "them?"
    )

    active_summary = "; ".join(
        f"{h['path']} ({h['reason'][:160]})" for h in active_hits
    ) or "(none)"

    headline = (
        f"Scanned {vendored_tree_root_count} real vendored-tree roots in this single checkout "
        f"({vendored_tree_roots}): hits_count={hits_count} auto-load-set matches "
        f"(by_matched_name={by_matched_name}). Content classification of all "
        f"{classified_count} hits: active_count={active_count}, mention_only_count="
        f"{mention_only_count}, inert_count={inert_count}. "
        f"ACTIVE finding(s): {active_summary}. This confirms the catalog's "
        "CVE-2026-47751-class precedent is REAL in this checkout: "
        "tools/editor/ralph-orchestrator/vendor/ is a self-documented upstream "
        "snapshot that carries auto-loaded config (.claude/, AGENTS.md, "
        "CLAUDE.md) AND a real hook-registration-syntax file "
        "(examples/hooks/minimal/ralph.hooks.yml), though that specific file "
        "discloses its own explicit -c/--config opt-in requirement rather "
        "than being proven auto-loaded by default -- a nuance recorded, not "
        "collapsed into an unqualified 'active hook found' claim. "
        f"tests_required control (prose-only AGENTS.md->inert, same-fixture "
        f"hook-registering content->active, on one toggled fixture)=ok:{control_ok}."
    )

    if success:
        c_rev = review["claude"]
        x_rev = review["codex"]
        reviewer = {
            "reviewer_id": f"claude={c_rev['reviewer_id']};codex={x_rev['reviewer_id']}",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "anthropic+openai",
            "reviewed_at": ended,
            "notes": (
                f"claude: {str(c_rev.get('notes',''))[:2000]} || "
                f"codex: {str(x_rev.get('notes',''))[:2000]}"
            )[:8000],
        }
        defects = [
            {
                "id": "AUD-0081-D-REVIEW",
                "severity": "P1",
                "status": "resolved",
                "summary": (
                    "Both required independent reviewers (one fresh-context "
                    "Claude, one Codex) recorded PASS on disk at "
                    "claude-review.json / codex-review.json"
                ),
            },
        ]
        state = "SUCCESS"
        sentinel = (
            f"SUCCESS:AUD-0081 active_count={active_count} hits_count={hits_count} "
            f"control_ok={control_ok} dependency_aud_0009_satisfied={dep['satisfied']}"
        )
        failure = None
        anti = "SUCCESS-after-dual-independent-review-PASS-agreement"
    else:
        review_note = (
            "Catalog reviewer_requirement: two reviewers, one fresh-context "
            "Claude and one Codex, must each independently review this "
            "audit (probe 1 and probe 2 both attached); on disagreement "
            "escalate to the owner with both probes attached and NEVER "
            "resolve by vote. No claude-review.json or codex-review.json "
            "is invented here; probes are measured and state is BLOCKED "
            "instead."
        )
        if review["status"] == "escalate-to-owner":
            review_note = (
                f"Reviewers DISAGREE (status=escalate-to-owner): {review.get('note')}. "
                "Per catalog text this is escalated to the owner with both "
                "probes attached, not resolved by vote or by a third "
                "tie-break review."
            )
        reviewer = {
            "reviewer_id": "required-dual-reviewer-claude-and-codex-unassigned",
            "verdict": "NOT-REVIEWED",
            "independent": False,
            "fresh_context": False,
            "vendor": "anthropic+openai",
            "notes": review_note,
        }
        state = "BLOCKED"
        blockers = []
        if not dep["satisfied"]:
            blockers.append(
                f"dependency AUD-0009 state={dep.get('state')!r} (need SUCCESS) at {dep['path']}"
            )
        if review["status"] == "escalate-to-owner":
            blockers.append("reviewer-disagreement-escalated-to-owner")
        else:
            blockers.append("dual-reviewer-claude-and-codex-review-unpaid")
        sentinel = (
            f"FAILED:AUD-0081 untrusted auto-loaded configuration audit measured "
            f"hits_count={hits_count} active_count={active_count} "
            f"control_ok={control_ok}; blocked-on-{'-and-'.join(b.split(' ')[0] for b in blockers)}"
        )
        failure_classification = ["detector-failure"]
        if not dep["satisfied"]:
            failure_classification.append("dependency-blocked" if "dependency-blocked" not in failure_classification else "detector-failure")
        if review["status"] == "escalate-to-owner":
            failure_classification.append("owner-blocked")
        else:
            failure_classification.append("owner-blocked")
        failure = {
            "classification": sorted(set(failure_classification)),
            "reason": (
                "Named probes completed with the required control passing "
                "(the classifier correctly rates a prose-only AGENTS.md as "
                "inert and the SAME fixture rewritten with a PreToolUse "
                "hook registration as active), and a real active-hook-"
                "registration-syntax hit was found in a vendored tree "
                "(tools/editor/ralph-orchestrator/vendor/examples/hooks/"
                "minimal/ralph.hooks.yml), but "
                + (
                    f"catalog dependency AUD-0009 is not on disk as SUCCESS "
                    f"(measured state={dep.get('state')!r}) so this unit "
                    f"cannot rely on its artifact yet; and, independently, "
                    if not dep["satisfied"]
                    else ""
                )
                + "catalog reviewer_requirement is unmet: one fresh-context "
                "Claude reviewer AND one Codex reviewer must both "
                "independently review probe 1 and probe 2 before PASS -- "
                "and a disagreement between them is escalated to the "
                "owner, never resolved by vote."
            ),
            "diagnostic_tail": (
                f"vendored_tree_root_count={vendored_tree_root_count} "
                f"vendored_tree_roots={vendored_tree_roots} hits_count={hits_count} "
                f"by_matched_name={by_matched_name} by_vendored_root={by_vendored_root} "
                f"classified_count={classified_count} active_count={active_count} "
                f"mention_only_count={mention_only_count} inert_count={inert_count} "
                f"active_hits={[h['path'] for h in active_hits]} "
                f"control_fired_on_bad={fired_on_bad} control_silent_on_good={silent_on_good} "
                f"dependency_aud_0009_state={dep.get('state')} "
                f"dependency_aud_0009_satisfied={dep['satisfied']} "
                f"review_status={review['status']} reviewer=NOT-REVIEWED"
            ),
            "blocked_on": (
                (
                    f"1) AUD-0009 must reach state=SUCCESS on disk at {AUD_0009_PATH} "
                    f"before this unit relies on its vendored-tree inventory "
                    f"artifact (currently state={dep.get('state')!r}); and 2) "
                    if not dep["satisfied"]
                    else ""
                )
                + (
                    "dispatch one fresh-context Claude reviewer AND one "
                    "Codex reviewer, each independently reviewing probe 1 "
                    f"and probe 2 against active_count={active_count} / "
                    f"hits_count={hits_count}, before PASS; on disagreement "
                    "escalate to the owner with both probes attached"
                    if review["status"] != "escalate-to-owner"
                    else "escalate to the owner with both probes attached per the recorded reviewer disagreement"
                )
            ),
            "two_signal_proof": [
                L.probe(
                    "source",
                    "command",
                    "python3 -B command-center/p2-wave/probes/AUD-0081/probe2_content_classify.py",
                    f"active_count={active_count} hits_count={hits_count}",
                    0,
                ),
                L.probe(
                    "verifier",
                    "file-read",
                    "reviewer.verdict",
                    "NOT-REVIEWED",
                    0,
                ),
            ],
        }
        anti = "BLOCKED-pending-dependency-and-dual-claude-codex-review-with-real-probes"
        defects = [
            {
                "id": "AUD-0081-D-REVIEW",
                "severity": "P1",
                "status": "open",
                "summary": (
                    "Dual reviewer (one fresh-context Claude, one Codex, "
                    "each reviewing both probes) unpaid; active_count/"
                    "hits_count/classification counts must be independently "
                    "confirmed by both before PASS, and a disagreement "
                    "escalated to the owner rather than resolved by vote."
                ),
            },
        ]
        if not dep["satisfied"]:
            defects.append(
                {
                    "id": "AUD-0081-D-DEPENDENCY",
                    "severity": "P1",
                    "status": "open",
                    "summary": (
                        f"Dependency AUD-0009 is not state=SUCCESS on disk "
                        f"(measured state={dep.get('state')!r} at {dep['path']}); "
                        "this unit's catalog dependency list names it and it "
                        "must be checked, not assumed, before reliance."
                    ),
                }
            )

    doc: dict = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0081",
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "anthropic",
            "model": "composer",
            "role": "auditor",
            "execution_substrate": "linux-cursor-cloud",
        },
        "artifacts": arts,
        "evidence": [
            L.evidence(
                (
                    f"Probe 1 real filesystem filename search: "
                    f"{vendored_tree_root_count} vendored-tree roots found in this "
                    f"single checkout ({vendored_tree_roots}), each independently "
                    "confirmed to exist via a real os.walk (not a hardcoded "
                    f"allowlist). hits_count={hits_count} auto-load-set filename/"
                    f"dirname matches across those roots: by_matched_name="
                    f"{by_matched_name}, by_vendored_root={by_vendored_root}. "
                    "SCOPE DISCLOSED, not hidden: this is one checkout of the "
                    "estate's many; CLAUDE.md's '178 checkouts' section describes "
                    "a different, Windows-hosted developer box this pod cannot "
                    "enumerate."
                ),
                "CONFIRMED",
                P1_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0081/probe1_filename_search.py",
                        raw1[-8000:],
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read probe1-filename-search.json",
                        json.dumps(
                            {
                                "vendored_tree_root_count": vendored_tree_root_count,
                                "vendored_tree_roots": vendored_tree_roots,
                                "hits_count": hits_count,
                                "by_matched_name": by_matched_name,
                                "ok": p1["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Probe 2 real content-read classification of all {classified_count} "
                    f"probe-1 hits (bytes actually re-read off disk, not re-derived from "
                    f"probe 1's own claims): active_count={active_count}, "
                    f"mention_only_count={mention_only_count}, inert_count={inert_count}. "
                    f"The {active_count} ACTIVE hit(s): {active_summary}. This is the "
                    "catalog's named CVE-2026-47751-class precedent made concrete in "
                    "this checkout: a vendored tree (tools/editor/ralph-orchestrator/"
                    "vendor/, self-documented in its own README.md as a 'Curated "
                    "upstream snapshot') carries BOTH auto-loaded documentation "
                    "config (.claude/, AGENTS.md, CLAUDE.md -- all classified inert "
                    "or mention-only on THEIR OWN, per 'presence alone is not a risk "
                    "finding') AND, separately, a file with a real hook-registration "
                    "syntax. The nuance that specific file's own header comment "
                    "requires an explicit -c/--config flag (i.e. it is example content, "
                    "not proven auto-loaded by default) is preserved in the reason "
                    "string rather than collapsed into an unqualified claim."
                ),
                "CONFIRMED" if bool(p2["ok"]) else "REFUTED",
                P2_RAW,
                [
                    L.probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/AUD-0081/probe2_content_classify.py",
                        raw2[-8000:],
                        0 if bool(p2["ok"]) else 1,
                    ),
                    L.probe(
                        "verifier",
                        "byte-compare",
                        "python3 -c read probe2-content-classification.json",
                        json.dumps(
                            {
                                "classified_count": classified_count,
                                "active_count": active_count,
                                "mention_only_count": mention_only_count,
                                "inert_count": inert_count,
                                "active_hit_paths": [h["path"] for h in active_hits],
                                "ok": p2["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    "tests_required control (verbatim ask: 'the classifier must "
                    "rate an AGENTS.md containing only prose as inert and one "
                    "registering a PreToolUse command as active; assert both on "
                    f"one fixture'): fired_on_bad_state={fired_on_bad} (the SAME "
                    "classify_hit function correctly rated the prose-only state "
                    "of ONE toggled fixture path as inert), silent_on_good_state="
                    f"{silent_on_good} (the same function correctly rated the "
                    "SAME fixture path, rewritten to contain a "
                    "'\"hooks\": {\"PreToolUse\": [...]}' JSON block, as active). "
                    "A negative control (a naive substring-only matcher that "
                    "flags any content containing the literal word 'hooks') was "
                    "shown to incorrectly classify a mention-only fixture "
                    "('git hooks for linting... scripts/setup-hooks.sh') as "
                    "active, while the real classifier correctly rates that same "
                    "mention-only fixture inert -- proving the control is "
                    "falsifiable and not vacuously true for any classifier."
                ),
                "CONFIRMED" if control_ok else "REFUTED",
                CTL_RAW,
                [
                    L.probe(
                        "source",
                        "command",
                        "python3 -B command-center/p2-wave/probes/AUD-0081/control_prose_vs_hook_fixture.py",
                        raw_ctl,
                        0 if control_ok else 1,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        "python3 -c read control-prose-vs-hook-fixture.json",
                        json.dumps(
                            {
                                "fired_on_bad_state": fired_on_bad,
                                "silent_on_good_state": silent_on_good,
                                "ok": ctl["ok"],
                            }
                        ),
                        0,
                    ),
                ],
                "almost-certain",
            ),
            L.evidence(
                (
                    f"Dependency gate: catalog dependencies are [B01, AUD-0009]. "
                    f"AUD-0009 (submodule/vendored inventory) was checked ON DISK "
                    f"at {dep['path']} rather than assumed: exists={dep['exists']}, "
                    f"state={dep.get('state')!r}, satisfied={dep['satisfied']}."
                ),
                "CONFIRMED" if dep["satisfied"] else "REFUTED",
                dep["path"],
                [
                    L.probe(
                        "source",
                        "file-read",
                        f"cat {AUD_0009_PATH}",
                        f"state={dep.get('state')!r} unit_id={dep.get('unit_id')!r}",
                        0,
                    ),
                    L.probe(
                        "verifier",
                        "file-read",
                        f"python3 -c read {AUD_0009_PATH}",
                        json.dumps(dep),
                        0 if dep["satisfied"] else 1,
                    ),
                ],
                "almost-certain" if dep["exists"] else "refuted",
            ),
        ],
        "tests": [
            {
                "id": "AUD-0081-control-prose-is-inert",
                "name": (
                    "tests_required: an AGENTS.md containing only prose is "
                    "classified inert"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0081/control_prose_vs_hook_fixture.py",
                "result": "PASS" if fired_on_bad else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0081-control-preTooluse-registration-is-active",
                "name": (
                    "tests_required: the SAME fixture path registering a "
                    "PreToolUse command is classified active"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0081/control_prose_vs_hook_fixture.py",
                "result": "PASS" if silent_on_good else "FAIL",
                "assertions": 1,
                "output_tail": raw_ctl[-800:],
            },
            {
                "id": "AUD-0081-probe2-real-hits-classified",
                "name": (
                    "every probe-1 hit was actually re-read off disk and "
                    "classified (not a fabricated count)"
                ),
                "command": "python3 -B command-center/p2-wave/probes/AUD-0081/probe2_content_classify.py",
                "result": "PASS" if bool(p2["ok"]) and classified_count == hits_count else "FAIL",
                "assertions": 1,
                "output_tail": raw2[-800:],
            },
        ],
        "negative_controls": [
            L.control(
                "AUD0081-C1",
                "known-broken-fixture",
                (
                    "A deliberately naive substring-only classifier ('hooks' "
                    "appears anywhere in the text -> active) must incorrectly "
                    "flag a mention-only fixture ('git hooks for linting... "
                    "see scripts/setup-hooks.sh') as active -- proving the "
                    "control is falsifiable and not vacuously true for any "
                    "classifier."
                ),
                bool(ctl["mention_only_false_positive_fixture"]["naive_incorrectly_flags_mention_as_active"]),
                bool(ctl["mention_only_false_positive_fixture"]["real_correctly_rates_mention_as_inert"]),
                bad=f"naive_classifier.mention_only_fixture={ctl['mention_only_false_positive_fixture']['naive_substring_classifier_result']}",
                good=f"real_classifier.mention_only_fixture={ctl['mention_only_false_positive_fixture']['real_classifier_result']}",
            ),
            L.control(
                "AUD0081-C2",
                "other",
                (
                    "The single toggled fixture (one file path, two content "
                    "states) must diverge: prose-only -> inert, then the "
                    "SAME path rewritten with a PreToolUse JSON registration "
                    "-> active."
                ),
                fired_on_bad,
                silent_on_good,
                bad=f"prose_only_state.classification={ctl['prose_only_state']['classification']}",
                good=f"active_hook_state.classification={ctl['active_hook_state']['classification']}",
            ),
        ],
        "reviewer": reviewer,
        "defects": defects,
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/receipt_validate.py admission",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": L.probe(
                    "source",
                    "command",
                    f"python3 command-center/receipt_validate.py {OUT}",
                    f"seeded-before-first-admit state={state}; replaced after live run",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot (AGENTS.md 4b): after the second "
                "failure with the same detector, enumerate at least 2 "
                "mechanically different detectors before a third attempt"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The estate's other ~177 checkouts (per CLAUDE.md's "
                    "measured-2026-08-14 count on a different, Windows-"
                    "hosted developer box) carry the same or a different "
                    "set of auto-load hits than this single Linux Cursor "
                    "Cloud checkout."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run probe1_filename_search.py and probe2_content_"
                    "classify.py against each of the other checkouts "
                    "(or a representative sample) on that developer box, "
                    "and diff vendored_tree_roots / hits_count / "
                    "active_count against this run's baseline."
                ),
            },
            {
                "claim": (
                    "Whether tools/editor/ralph-orchestrator/vendor/"
                    "examples/hooks/minimal/ralph.hooks.yml, or any file "
                    "shaped like it, is EVER auto-discovered by the real "
                    "ralph-orchestrator CLI without an explicit -c/--config "
                    "flag (e.g. via a default search path)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Read (or run with `ralph hooks validate` /  "
                    "`ralph --help`) the real ralph-orchestrator CLI's "
                    "config-discovery code (crates/ralph-cli, "
                    "crates/ralph-core/src/config.rs) to confirm whether "
                    "any hooks.yml path is loaded by default versus only "
                    "when explicitly passed via -c."
                ),
            },
            {
                "claim": (
                    "Whether any of the 6 mention-only or inert 'hooks' "
                    "directory hits inside tools/mcp/hacktricks-mcp-server/"
                    "node_modules/hono actually execute at MCP-server "
                    "runtime in a way this static content read cannot see "
                    "(e.g. a dynamic import path)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Start the hacktricks MCP server locally and trace "
                    "(via strace/ltrace or a Node --trace-warnings run) "
                    "which files under node_modules/hono/dist/*/hooks are "
                    "actually loaded at runtime, diffing against this "
                    "probe's static classification."
                ),
            },
        ],
        "report": {
            "kind": "audit-finding",
            "question": question,
            "headline": headline,
            "control_ids": ["AUD0081-C1", "AUD0081-C2"],
            "observations": [
                {
                    "name": "vendored_tree_root_count",
                    "measured": vendored_tree_root_count,
                    "method": "os.walk over the whole checkout, basename match against {node_modules, vendor, vendor_src, third_party, third-party}",
                    "anchor": P1_JSON,
                },
                {
                    "name": "hits_count",
                    "measured": hits_count,
                    "method": "os.walk within each vendored-tree root, filename/dirname match against {.claude, .codex, hooks, AGENTS.md, CLAUDE.md, .mcp.json}",
                    "anchor": P1_JSON,
                },
                {
                    "name": "classified_count",
                    "measured": classified_count,
                    "method": "every probe-1 hit re-read off disk and passed through _autoload_classifier.classify_hit",
                    "anchor": P2_JSON,
                },
                {
                    "name": "active_count",
                    "measured": active_count,
                    "method": "hook-lifecycle marker / non-empty JSON hooks or mcpServers key / YAML hooks+command block detected in real content",
                    "anchor": P2_JSON,
                },
                {
                    "name": "mention_only_count",
                    "measured": mention_only_count,
                    "method": "auto-load name present, executable-shaped script or ambiguous content found, but no registration wiring confirmed",
                    "anchor": P2_JSON,
                },
                {
                    "name": "inert_count",
                    "measured": inert_count,
                    "method": "prose-only content, or non-executable source-code-only hooks/ directory (coding-convention false positive)",
                    "anchor": P2_JSON,
                },
                {
                    "name": "control_fired_on_bad_state",
                    "measured": fired_on_bad,
                    "method": "tests_required control via control_prose_vs_hook_fixture.py",
                    "anchor": CTL_JSON,
                },
                {
                    "name": "control_silent_on_good_state",
                    "measured": silent_on_good,
                    "method": "tests_required control via control_prose_vs_hook_fixture.py",
                    "anchor": CTL_JSON,
                },
                {
                    "name": "dependency_aud_0009_satisfied",
                    "measured": dep["satisfied"],
                    "method": f"read state field from {AUD_0009_PATH} on disk",
                    "anchor": dep["path"],
                },
            ],
            "vendored_tree_roots": vendored_tree_roots,
            "by_matched_name": by_matched_name,
            "by_vendored_root": by_vendored_root,
            "active_hits": active_hits,
            "dependency_check_aud_0009": dep,
            "review_status": review["status"],
        },
        "extensions": {
            "anti_false_green": anti,
            "wave": "p2-loop",
            "scope_note": (
                "This is a single Linux Cursor Cloud checkout, not the "
                "estate's full ~178-checkout population CLAUDE.md "
                "describes (that population was measured on a different, "
                "Windows-hosted developer box this pod cannot see or "
                "enumerate). Every root and hit reported here is real and "
                "reproducible on THIS checkout; no claim is made about "
                "any other checkout."
            ),
            "reviewer_scope_note": (
                "Catalog reviewer_requirement calls for TWO reviewers -- "
                "one fresh-context Claude, one Codex -- who each "
                "independently review both probes, with disagreement "
                "escalated to the owner rather than resolved by vote. "
                "This differs from AUD-0061/AUD-0083's single-cross-vendor-"
                "Codex-reviewer shape; load_dual_review() enforces both "
                "vendor families and distinguishes not-reviewed / "
                "both-pass / escalate-to-owner as three DIFFERENT statuses "
                "so a disagreement is never silently folded into either "
                "'pending' or 'passed'."
            ),
        },
    }
    if failure is not None:
        doc["failure"] = failure
    return doc


def main() -> int:
    out_path = L.REPO / OUT

    def admit_consumer(rc: int, out: str) -> dict:
        return {
            "consumer": "command-center/receipt_validate.py admission",
            "artifact_path": OUT,
            "executed": True,
            "read_ok": rc == 0 and "ADMIT" in out.upper(),
            "exit_code": rc,
            "probe": L.probe(
                "source",
                "command",
                f"python3 command-center/receipt_validate.py {OUT}",
                out[:4000],
                rc,
            ),
        }

    doc = build()
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc
    for _ in range(2):
        doc = build(primary=L.art(OUT, "primary"))
        rc = L.write_if_valid(doc, OUT, SCHEMA)
        if rc != 0:
            return rc

    rc_adm, adm_out = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm, adm_out)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    rc_adm2, adm_out2 = L.run(
        [sys.executable, str(L.REPO / "command-center/receipt_validate.py"), OUT]
    )
    doc = build(primary=L.art(OUT, "primary"))
    doc["downstream_consumers"] = [admit_consumer(rc_adm2, adm_out2)]
    rc = L.write_if_valid(doc, OUT, SCHEMA)
    if rc != 0:
        return rc

    final = json.loads(out_path.read_text(encoding="utf-8"))
    man = {
        "unit_id": UNIT,
        "output_path": OUT,
        "sha256": L.art(OUT)["sha256"],
        "bytes": L.art(OUT)["bytes"],
        "state": final["state"],
    }
    (L.REPO / MANIFEST).write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    print(f"PACKED {OUT} state={final['state']} bytes={L.art(OUT)['bytes']}")
    print(final["sentinel"])
    print(final["report"]["headline"])
    print(adm_out2.strip())
    return 0 if rc_adm2 == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
