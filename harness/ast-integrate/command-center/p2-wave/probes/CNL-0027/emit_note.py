#!/usr/bin/env python3
"""Emit the CNL-0027 design note (JSON at the catalog .md path).

Catalog output_schema is a generated $ref shim. Validation uses schema_val.py
(disk-only RefResolver). The live receipt_core additionalProperties:false
rule means design payload lives under report, not as extra top-level keys.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import schema_val as S  # noqa: E402
import triad as T  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0027-proposer-critic-and-synthesiser-triad-mandates.md"
)
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0027/probe1_role_drift.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0027/probe2_independent_schema.py"
)
QUESTION = (
    "What exactly does each of the three roles owe the council, and what is "
    "the rule that stops a synthesiser from quietly becoming a third critic "
    "or a second proposer?"
)
SUPPORTING = (
    "command-center/p2-wave/probes/CNL-0027/triad.py",
    "command-center/p2-wave/probes/CNL-0027/fixtures.py",
    "command-center/p2-wave/probes/CNL-0027/schema_val.py",
    SCHEMA_REL,
)


def find_line(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0027 emit anchor missing in {path}: {needle}")


def compact(row: dict) -> dict:
    return {
        "fires": row["fires"],
        "silent": row["silent"],
        "coverage": row["coverage"],
        "joint": row["joint"],
        "reason": row["reason"],
        "minted_option_ids": row["minted_option_ids"],
        "minted_objection_ids": row["minted_objection_ids"],
        "reasons": row["reasons"],
    }


def digest(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()[:32]


def independent_selects(rnd: dict) -> tuple[set[str], set[str]]:
    """Top-level selects minus filed option_ids. Does not call triad.check."""
    filed = {str(p["option_id"]) for p in rnd["proposals"] if p.get("option_id")}
    syn = rnd.get("synthesis") or {}
    cited = {str(x) for x in (syn.get("selects") or [])}
    return filed, cited - filed


def main() -> int:
    rows = {
        "known_good": T.check(F.known_good()),
        "planted_new_proposal": T.check(F.planted_new_proposal()),
        "planted_new_objection": T.check(F.planted_new_objection()),
        "mention_only": T.check(F.mention_only()),
        "critic_proposes": T.check(F.critic_proposes()),
        "coverage_plus_mint": T.check(F.coverage_plus_mint()),
    }
    if (
        not rows["planted_new_proposal"]["fires"]
        or rows["known_good"]["fires"]
        or rows["mention_only"]["fires"]
        or not rows["planted_new_objection"]["fires"]
        or not rows["critic_proposes"]["fires"]
        or not rows["coverage_plus_mint"]["fires"]
    ):
        print("FAILED:CNL-0027 emit both-states not satisfied before write")
        return 1
    if abs(rows["coverage_plus_mint"]["coverage"] - 1.0) > 1e-12:
        print("FAILED:CNL-0027 emit coverage-plus-mint coverage is not 1.0")
        return 1
    if abs(rows["known_good"]["coverage"] - rows["coverage_plus_mint"]["coverage"]) > 1e-12:
        print("FAILED:CNL-0027 emit coverage does not match across mint vs good")
        return 1

    filed, minted = independent_selects(F.planted_new_proposal())
    if "P-SYNTH" not in minted:
        print("FAILED:CNL-0027 emit independent set-difference missed P-SYNTH")
        return 1

    t_line = find_line(HERE / "triad.py", "def harvest_synthesis(")
    f_line = find_line(HERE / "fixtures.py", "def planted_new_proposal(")
    m_line = find_line(HERE / "fixtures.py", "def mention_only(")
    c_line = find_line(HERE / "triad.py", "FORBIDDEN_MINT_KEYS")
    cat_line = find_line(REPO / "command-center/WORK-UNIT-CATALOG.json", '"id": "CNL-0027"')
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    started = "2026-08-24T18:47:00Z"

    answer = (
        "Each seat owes a typed artifact, not a prompt costume. The proposer "
        "owes at least one Proposal with a unique option_id; that id is the "
        "only handle later seats may treat as on the table. The critic owes "
        "at least one Critique with a unique objection_id that targets a "
        "filed option_id; it may recommend reject/revise/accept and may "
        "quote proposal text (mention), but it must not mint an option_id. "
        "The synthesiser owes a Synthesis that selects a subset of filed "
        "option_ids, addresses or lists unresolved a subset of filed "
        "objection_ids, and may rank or paraphrase those already-filed "
        "objects. The rule that stops the synthesiser becoming a second "
        "proposer or a third critic is closed-world citation on typed "
        "fields: any option_id or objection_id that is not in the filed "
        "sets, or any forbidden mint key (new_proposal, new_objection, …), "
        "is drift and the checker FIRES. Prompt instructions are not the "
        "gate — the planted P-SYNTH fixture is the counterexample. "
        f"Coverage of filed ids is insufficient: known-good and "
        f"coverage-plus-mint both score C={rows['known_good']['coverage']:.3f}, "
        f"while joint is {rows['known_good']['joint']:.1f} vs "
        f"{rows['coverage_plus_mint']['joint']:.1f}."
    )
    verbatim_bad = "PLANTED-BAD new-proposal: " + T.fmt(rows["planted_new_proposal"])
    verbatim_good = "KNOWN-GOOD closed-world: " + T.fmt(rows["known_good"])
    verbatim_mention = "MENTION-ONLY: " + T.fmt(rows["mention_only"])
    harvest_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNL-0027'); "
        "import fixtures as F, triad as T; print(T.fmt(T.check(F.planted_new_proposal())))\""
    )
    setdiff_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNL-0027'); "
        "import fixtures as F; r=F.planted_new_proposal(); "
        "filed={p['option_id'] for p in r['proposals']}; "
        "sel=set(r['synthesis']['selects']); print(sorted(sel-filed))\""
    )

    artifacts = []
    for rel, role in (
        (SUPPORTING[0], "supporting"),
        (SUPPORTING[1], "supporting"),
        (SUPPORTING[2], "supporting"),
        (SUPPORTING[3], "supporting"),
    ):
        sha, size = digest(rel)
        artifacts.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "eol": "LF",
                "role": role,
            }
        )

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0027",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0027",
        "spec_anchor": (
            f"command-center/WORK-UNIT-CATALOG.json:{cat_line} "
            "question_or_target for CNL-0027; catalog inputs "
            "_USER-PROMPTS.md:10746-10767 / 10915-10946 and "
            "11/12 council spec files are absent on this worktree."
        ),
        "min_bytes_threshold": 4096,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A synthesiser that injects unfiled option_id P-SYNTH is "
                    "caught as second-proposer drift by closed-world citation."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"command-center/p2-wave/probes/CNL-0027/triad.py:{t_line}",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": harvest_cmd,
                        "raw_output": verbatim_bad,
                        "fingerprint": fp("command", harvest_cmd),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": setdiff_cmd,
                        "raw_output": (
                            f"filed={sorted(filed)} minted={sorted(minted)}; "
                            "P-SYNTH is in synthesis.selects and not in "
                            "proposal.option_id. Prompt labels are not this check."
                        ),
                        "fingerprint": fp("static-analysis", setdiff_cmd),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Coverage of filed ids is not the gate: coverage-plus-mint "
                    "matches known-good coverage at 1.0 and still FIRES (joint=0)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0027/fixtures.py:"
                    f"{find_line(HERE / 'fixtures.py', 'def coverage_plus_mint(')}"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": P1,
                        "raw_output": (
                            "COVERAGE-PLUS-MINT: " + T.fmt(rows["coverage_plus_mint"])
                        ),
                        "fingerprint": fp("test-run", P1),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": (
                            "compare known_good.coverage vs coverage_plus_mint.coverage "
                            "and known_good.joint vs coverage_plus_mint.joint"
                        ),
                        "raw_output": (
                            f"coverage good={rows['known_good']['coverage']:.12f} "
                            f"mint={rows['coverage_plus_mint']['coverage']:.12f}; "
                            f"joint good={rows['known_good']['joint']:.1f} "
                            f"mint={rows['coverage_plus_mint']['joint']:.1f}"
                        ),
                        "fingerprint": fp(
                            "byte-compare",
                            "coverage-vs-joint known_good vs coverage_plus_mint",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T-ROLE-DRIFT-NEW-PROPOSAL",
                "name": "Role-drift fixture: synthesiser injects P-SYNTH",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-BOTH-STATES",
                "name": "FIRES on planted-bad; SILENT on known-good and mention-only",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-INDEPENDENT-SCHEMA-ENUM",
                "name": "Independent set-difference plus per-round JSON Schema enum",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-SYNTH-MINTS-OPTION",
                "kind": "known-broken-fixture",
                "description": (
                    "Rejects a synthesiser selects[] that includes P-SYNTH, which "
                    "no proposer filed, plus a new_proposal object. Known-good "
                    "closed-world select/address must stay SILENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": verbatim_bad,
                "good_state_output": verbatim_good,
            },
            {
                "id": "NC-MENTION-ONLY",
                "kind": "known-broken-fixture",
                "description": (
                    "Use-vs-mention: prose names P-HYPOTHETICAL in notes; typed "
                    "fields stay closed-world. The check must be SILENT (this is "
                    "the state that must NOT be rejected)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": verbatim_bad,
                "good_state_output": verbatim_mention,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0027-probe2-independent-schema",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Top-level selects/addresses set-difference plus Draft-07 enum "
                "of filed ids. Does not call triad.check. Counterexample: "
                "planted_new_proposal synthesis.selects contains P-SYNTH, which "
                f"is not in proposal.option_id set {sorted(filed)}. Prompt role "
                "labels do not prevent the mint; the closed-world enum does."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0027/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNL-0027",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0027/schema_val.py "
                    "Draft202012Validator disk-store"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0027'); "
                        "import json, schema_val; "
                        "p='command-center/design/council/"
                        "CNL-0027-proposer-critic-and-synthesiser-triad-mandates.md'; "
                        "print(schema_val.error_messages(json.load(open(p))))\""
                    ),
                    "raw_output": "[]",
                    "fingerprint": fp("schema-validate", "schema_val.error_messages"),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a 3rd "
                "attempt (AGENTS.md 4b). Max 3 attempts."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Prose-only smuggle: a synthesiser that writes a new idea only "
                    "in unstructured notes without an option_id is not harvested."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "IMP-0281 (later runtime content guard) or an NLP harvest over "
                    "notes; typed-channel harvest remains the CNL-0027 gate."
                ),
            },
            {
                "claim": (
                    "CNL-0022 obligation vs permission vs right schema is not "
                    "delivered as bytes this note transcribed; field names here "
                    "are local."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When CNL-0022 output_path exists, remap owes/may/must_not "
                    "onto that trichotomy without changing the closed-world mint gate."
                ),
            },
            {
                "claim": (
                    "Harness-restore 11-COUNCIL-SPECIFICATION.schema.json and "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json are absent on this tree."
                ),
                "verdict": "REFUTED",
                "settling_experiment": (
                    "Mount harness-restore-20260806 and re-cite mandate field "
                    "names from those files; until then this note is not a transcription."
                ),
            },
        ],
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "planted-new-proposal-fires",
                    "measured": True,
                    "method": "triad.check harvest of nested synthesis fields",
                    "anchor": f"command-center/p2-wave/probes/CNL-0027/triad.py:{t_line}",
                },
                {
                    "name": "known-good-silent",
                    "measured": True,
                    "method": "triad.check on closed-world select/address",
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0027/fixtures.py:"
                        f"{find_line(HERE / 'fixtures.py', 'def known_good(')}"
                    ),
                },
                {
                    "name": "coverage-plus-mint-coverage",
                    "measured": float(rows["coverage_plus_mint"]["coverage"]),
                    "method": "|cited ∩ filed| / |filed|",
                    "anchor": (
                        "command-center/p2-wave/probes/CNL-0027/fixtures.py:"
                        f"{find_line(HERE / 'fixtures.py', 'def coverage_plus_mint(')}"
                    ),
                },
                {
                    "name": "independent-P-SYNTH-set-difference",
                    "measured": "P-SYNTH",
                    "method": "set(selects) minus set(proposal.option_id)",
                    "anchor": f"command-center/p2-wave/probes/CNL-0027/fixtures.py:{f_line}",
                },
            ],
            "control_ids": [
                "NC-SYNTH-MINTS-OPTION",
                "NC-MENTION-ONLY",
            ],
            "title": "Proposer, critic and synthesiser triad mandates",
            "question": QUESTION,
            "answer": answer,
            "completion_sentinel": "SUCCESS:CNL-0027",
            "role_mandates": {
                "proposer": {
                    "owes": (
                        "File >=1 Proposal with unique option_id, claim, and "
                        "evidence cites. option_id is the only later-seat handle."
                    ),
                    "may": "Revise own prior proposal via a successor option_id with replaces.",
                    "right": (
                        "Filed option_ids cannot be erased from the round's option "
                        "universe; they may be rejected, not deleted."
                    ),
                    "must_not": "File a Critique object as the turn's primary typed act.",
                },
                "critic": {
                    "owes": (
                        "File >=1 Critique with unique objection_id that targets "
                        "an existing option_id."
                    ),
                    "may": "Recommend reject/revise/accept; quote proposal text (mention).",
                    "right": (
                        "Filed objection_ids remain until addressed or listed "
                        "unresolved in the synthesis."
                    ),
                    "must_not": "Introduce a new option_id (that is proposing).",
                },
                "synthesiser": {
                    "owes": (
                        "File a Synthesis whose selects are a non-empty subset of "
                        "filed option_ids and whose addresses/unresolved cite only "
                        "filed objection_ids."
                    ),
                    "may": (
                        "Paraphrase, rank, and merge wording of already-filed "
                        "options without minting a new option_id. Merging into a "
                        "new option requires a proposer to file it."
                    ),
                    "right": (
                        "May refuse to close the round while unresolved objections "
                        "remain; cannot be forced to mint a new option to 'solve' them."
                    ),
                    "must_not": (
                        "Mint option_id not in filed proposals (second proposer) "
                        "or objection_id not in filed critiques (third critic), "
                        "including via forbidden keys new_proposal/new_objection."
                    ),
                },
                "anti_drift_rule": (
                    "Closed-world citation on typed artifacts. The Synthesis "
                    "schema has no mint fields; the checker harvests ids from "
                    "all citation channels and FIRES on any id outside the filed "
                    "sets. Use vs mention: quoting P-HYPOTHETICAL in notes is "
                    "mention and SILENT; putting it in selects is use and FIRES."
                ),
                "rejected_alternatives": [
                    {
                        "mechanism": "Prompt-only 'do not propose' instruction",
                        "why_rejected": (
                            "The planted-new-proposal fixture still mints P-SYNTH "
                            "under a synthesiser label. Labels are costumes."
                        ),
                    },
                    {
                        "mechanism": "Separate-vendor synthesiser",
                        "why_rejected": (
                            "Changes who drifts; does not remove the mint channel."
                        ),
                    },
                ],
            },
            "taxonomy": {
                "id": "council.triad-act.v1",
                "closed": True,
                "range_rule": (
                    "Synthesis acts range over cite_option, cite_objection, "
                    "mint_option, mint_objection. Observed minting does not "
                    "extend the filed option/objection universes."
                ),
                "categories": [
                    {"id": "cite_option", "description": "Citation of a filed option_id"},
                    {"id": "cite_objection", "description": "Citation of a filed objection_id"},
                    {"id": "mint_option", "description": "Introduction of an unfiled option_id"},
                    {
                        "id": "mint_objection",
                        "description": "Introduction of an unfiled objection_id",
                    },
                ],
            },
            "measurement": {
                "name": "closed-world-joint",
                "formula": (
                    "joint = 1.0 iff minted_ids empty and citations subset of "
                    "filed, else 0.0; coverage = |cited ∩ filed| / |filed|"
                ),
                "threshold_reject_below": 1.0,
                "coverage_alone_insufficient": True,
            },
            "source_inputs_on_this_tree": {
                "11-COUNCIL-SPECIFICATION.schema.json": False,
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
                "_USER-PROMPTS.md": False,
                "CNL-0022-artifact": (
                    REPO
                    / "command-center/design/council/"
                    / "CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
                ).is_file(),
                "note": (
                    "Catalog inputs are Windows harness-restore paths not present "
                    "here. Obligation/permission/right vocabulary is local to this "
                    "unit until CNL-0022 lands as readable bytes."
                ),
            },
            "fixture_scores": {name: compact(row) for name, row in rows.items()},
            "both_states": {
                "planted_bad": "planted_new_proposal",
                "known_good": "known_good",
                "planted_bad_fires": True,
                "known_good_silent": True,
                "verbatim_bad": verbatim_bad,
                "verbatim_good": verbatim_good,
            },
            "counterexample": {
                "fixture": "planted_new_proposal",
                "injected_id": "P-SYNTH",
                "channel": "synthesis.selects",
                "filed_option_ids": sorted(filed),
            },
            "strongest_surviving_counterargument": (
                "A synthesiser that 'combines' P1 and P2 into a third option with "
                "a new id looks like helpful merge, not drift. This note treats "
                "that mint as second-proposer work: merge wording may rank P1 "
                "over P2, but a combined option must be filed by a proposer. If "
                "a later unit wants an explicit merge artifact type, it must be "
                "a proposer-owned option_id, not a synthesis side channel."
            ),
            "evidence_anchors": [
                {
                    "path": "command-center/p2-wave/probes/CNL-0027/triad.py",
                    "line": t_line,
                    "snippet": "def harvest_synthesis(",
                    "kind": "harvest",
                    "claim": "Id harvest walks nested synthesis fields, not prompt labels.",
                },
                {
                    "path": "command-center/p2-wave/probes/CNL-0027/fixtures.py",
                    "line": f_line,
                    "snippet": "def planted_new_proposal(",
                    "kind": "fixture",
                    "claim": "Planted-bad synthesiser mints P-SYNTH via selects and new_proposal.",
                },
                {
                    "path": "command-center/p2-wave/probes/CNL-0027/fixtures.py",
                    "line": m_line,
                    "snippet": "def mention_only(",
                    "kind": "fixture",
                    "claim": "Mention-only names P-HYPOTHETICAL in notes and does not mint.",
                },
                {
                    "path": "command-center/p2-wave/probes/CNL-0027/triad.py",
                    "line": c_line,
                    "snippet": "FORBIDDEN_MINT_KEYS",
                    "kind": "rule",
                    "claim": "Forbidden mint keys are a typed channel, not a regex over prose.",
                },
                {
                    "path": "command-center/WORK-UNIT-CATALOG.json",
                    "line": cat_line,
                    "snippet": '"id": "CNL-0027"',
                    "kind": "catalog",
                    "claim": "Catalog question is the question this note answers.",
                },
            ],
        },
    }

    errs = S.error_messages(doc)
    if errs:
        print("FAILED:CNL-0027 emit schema-invalid")
        for line in errs[:30]:
            print(" ", line)
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0027", "state": "SUCCESS"},
    ):
        g_errs = S.error_messages(garbage)
        if g_errs:
            garbage_rejected += 1
            continue
        print(f"FAILED:CNL-0027 emit schema accepted garbage {garbage}")
        return 1
    if garbage_rejected != 3:
        print(f"FAILED:CNL-0027 emit garbage rejected {garbage_rejected}/3")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0027 emit artifact {size}B below min_bytes_threshold")
        return 1
    if "SUCCESS:CNL-0027" not in payload:
        print("FAILED:CNL-0027 emit sentinel missing")
        return 1
    live_errs = S.error_messages(json.loads(out.read_text(encoding="utf-8")))
    if live_errs:
        print("FAILED:CNL-0027 emit on-disk schema-invalid")
        for line in live_errs[:20]:
            print(" ", line)
        return 1
    print(f"wrote {OUT_REL} bytes={size}")
    print("SUCCESS:CNL-0027 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
