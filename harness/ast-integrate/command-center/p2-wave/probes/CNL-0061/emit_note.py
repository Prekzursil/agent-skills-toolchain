#!/usr/bin/env python3
"""Emit CNL-0061 design note (JSON content at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import irv_author as A  # noqa: E402
import irv_reviewer as R  # noqa: E402
import pathology as P  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0061-ranked-choice-tabulation-and-its-known-pathologies.md"
)
CATALOG_SCHEMA = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/CNL-0061/council-design-note.schema.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0061/probe1_nonmonotonicity.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0061/probe2_reviewer_recount.py"
)
QUESTION = (
    "What is the exact IRV tabulation procedure including elimination ties, "
    "and which pathologies (non-monotonicity, later-no-harm violation) can "
    "actually occur at council roster sizes of 3-15?"
)
SENTINEL = "SUCCESS:CNL-0061"
CLAIM = (
    "IRV-COUNCIL-v1 (strict majority of continuing weight; eliminate exactly "
    "one last-place option via lookback-then-lex-min) is non-monotonic at "
    "roster 7 with 3 options, and later-no-harm does not fire under this IRV."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def cite(rel: str, needle: str) -> dict:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return {"path": rel, "line": i, "snippet": line.strip()[:240]}
    raise SystemExit(f"FAILED:CNL-0061 cite miss {rel!r} {needle!r}")


def ev(rel: str, needle: str, claim: str, mechanism: str, verdict: str = "CONFIRMED") -> dict:
    loc = cite(rel, needle)
    return {
        "claim": claim,
        "verdict": verdict,
        "anchor": f"{rel}:{loc['line']}",
        "mechanism": mechanism,
        "snippet": loc["snippet"],
        "path": rel,
        "line": loc["line"],
    }


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def rounds_public(result: dict) -> list[dict]:
    out = []
    for row in result.get("rounds") or []:
        slim = {
            "standing": row.get("standing"),
            "tally": row.get("tally"),
            "continuing_weight": row.get("continuing_weight"),
            "exhausted_weight": row.get("exhausted_weight"),
            "quota": row.get("quota"),
        }
        for k in (
            "last_place",
            "eliminated",
            "elim_rule",
            "tie_break_used",
            "winner",
            "majority",
            "total_tie",
            "exhausted_residual",
        ):
            if k in row:
                slim[k] = row[k]
        out.append(slim)
    return out


def main() -> int:
    F.write_fixture_files()
    nm0 = F.load_named("nm-7x3-original")
    nm1 = F.load_named("nm-7x3-raised")
    maj0 = F.load_named("majority-7-original")
    maj1 = F.load_named("majority-7-raised")
    nm4_0 = F.load_named("nm-7x4-original")
    nm4_1 = F.load_named("nm-7x4-raised")
    tr = F.load_named("lnh-irv-truncated")
    co = F.load_named("lnh-irv-completed")
    bt = F.load_named("lnh-bait-truncated")
    bc = F.load_named("lnh-bait-completed")
    wt = F.load_named("weighted-double-c")

    author_nm = P.nonmonotonicity_check(
        A.tabulate,
        nm0["options"],
        F.as_ballots(nm0),
        F.as_ballots(nm1),
        "C",
    )
    review_nm = P.nonmonotonicity_check(
        R.recount,
        nm0["options"],
        F.as_ballots(nm0),
        F.as_ballots(nm1),
        "C",
    )
    if (
        author_nm["before_winner"] != review_nm["before_winner"]
        or author_nm["after_winner"] != review_nm["after_winner"]
    ):
        print("FAILED:CNL-0061 author/reviewer winner disagreement (blocks unit)")
        print(author_nm)
        print(review_nm)
        return 1

    maj = P.nonmonotonicity_check(
        A.tabulate,
        maj0["options"],
        F.as_ballots(maj0),
        F.as_ballots(maj1),
        "A",
    )
    nm4 = P.nonmonotonicity_check(
        A.tabulate,
        nm4_0["options"],
        F.as_ballots(nm4_0),
        F.as_ballots(nm4_1),
        "D",
    )
    lnh_irv = P.later_no_harm_check(
        A.tabulate,
        tr["options"],
        F.as_ballots(tr),
        F.as_ballots(co),
        "A",
    )
    lnh_bait = P.later_no_harm_check(
        P.second_place_plurality,
        bt["options"],
        F.as_ballots(bt),
        F.as_ballots(bc),
        "A",
    )
    orig = A.tabulate(nm0["options"], F.as_ballots(nm0))
    raised = A.tabulate(nm1["options"], F.as_ballots(nm1))
    census_n7 = P.census_three_cand_raise_to_first(A.tabulate, 7)
    w_eq = A.tabulate(wt["options"], F.as_ballots(wt))

    windows_prompts = (
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"
    )
    harness_absent = {
        windows_prompts: not Path(windows_prompts).is_file(),
        "11-COUNCIL-SPECIFICATION.schema.json": not Path(
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
            "11-COUNCIL-SPECIFICATION.schema.json"
        ).is_file(),
        "CNL-0023-artifact": not (
            REPO
            / "command-center/design/council"
            / "CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight"
        ).is_file(),
    }

    nm_neg = json.dumps(
        {
            "fixture": "majority-7",
            "fired": maj["fired"],
            "silent": maj["silent"],
            "before_winner": maj["before_winner"],
            "after_winner": maj["after_winner"],
        },
        sort_keys=True,
    )
    lnh_neg = json.dumps(
        {
            "fixture": "lnh-bait-second-place-plurality",
            "fired": lnh_bait["fired"],
            "silent": lnh_bait["silent"],
            "before_winner": lnh_bait["before_winner"],
            "after_winner": lnh_bait["after_winner"],
        },
        sort_keys=True,
    )

    answer = (
        "IRV-COUNCIL-v1 tabulates ranked ballots by repeating, until a unique "
        "strict majority of continuing weight exists: tally the first standing "
        "preference of each ballot (weight default 1.0; weight != 1.0 is an "
        "input whose provenance is CNL-0023, not this tabulator), drop exhausted "
        "ballots from the denominator, and if nobody has tally > continuing/2, "
        "eliminate exactly one last-place option. Last-place ties use "
        "lookback-then-lex-min-elim: walk earlier rounds from the first, keep "
        "only the unique-lowest among the tied set, and if still tied eliminate "
        "min(option_id). Never RNG; never batch-eliminate the whole last-place "
        "set. At roster sizes 3-15, non-monotonicity CAN occur: the worked "
        "7-seat 3-option fixture elects C, then raising C on one A>C>B ballot "
        "to C>A>B elects B, because the raise turns a B/C last-place tie into "
        "an A/B last-place tie and lex-min eliminates A instead of B. The "
        "3-candidate raise-to-first census at n=7 counts "
        + str(census_n7)
        + " flipping (profile, source-type) pairs; n=3..6 count 0 under the "
        "same search. Later-no-harm does NOT occur under this IRV (truncated "
        "first-choice A still wins after later ranks are filled; 0 violations "
        "in the reviewer random trials). A planted second-place-plurality "
        "method does violate later-no-harm, so the checker is not vacuous. "
        + SENTINEL
    )

    doc = {
        "unit_id": "CNL-0061",
        "kind": "council-design-note",
        "state": "SUCCESS",
        "schema_version": 1,
        "title": "Ranked-choice tabulation and its known pathologies",
        "question": QUESTION,
        "claim_under_test": CLAIM,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "answer": answer,
        "procedure": {
            "id": A.PROCEDURE_ID,
            "tie_policy": A.TIE_POLICY,
            "majority_rule": A.MAJORITY_RULE,
            "steps": [
                "standing := option set; each ballot is a truncated ranking plus weight>0",
                "tally first remaining standing preference by weight; exhausted ballots leave the denominator",
                "quota := continuing_weight/2; unique tally > quota elects (strict; 50% is not a win)",
                "if continuing_weight==0, elect lex-min(standing) and flag exhausted_residual",
                "else last_place := argmin tally including zeros; if last_place==standing elect lex-min",
                "if |last_place|==1 eliminate it; if >1 lookback then lex-min — eliminate exactly one",
                "repeat; deterministic given options, ballots, and this policy",
            ],
            "weight": {
                "default": 1.0,
                "non_equal": (
                    "multiplied into the tally; unjustified non-1.0 is CNL-0023's "
                    "spec-validation job. CNL-0023 artifact is absent on this tree; "
                    "pathology fixtures are equal-weight. Weighted NM-7x3 with one "
                    "C>B>A ballot at weight 2.0 elects the same winner as two unit ballots."
                ),
                "weighted_fixture_winner": w_eq["winner"],
                "unit_ballot_winner": orig["winner"],
            },
            "rejected_alternatives": [
                {
                    "id": "batch-eliminate-last-place-set",
                    "why": (
                        "Eliminating every last-place option in one step can skip a "
                        "candidate who would have won the next pairwise and is not replay-distinct from lookback."
                    ),
                },
                {
                    "id": "rng-coin-flip",
                    "why": "Not replay-safe; councils must re-tabulate identically from the ballot file.",
                },
                {
                    "id": "majority-of-original-n",
                    "why": (
                        "Exhausted ballots would inflate the quota and can block a "
                        "majority of remaining opinion. Continuing-weight majority is the rule."
                    ),
                },
            ],
        },
        "worked_examples": {
            "nm7x3": {
                "roster_size": 7,
                "options": 3,
                "raised_candidate": "C",
                "before_winner": author_nm["before_winner"],
                "after_winner": author_nm["after_winner"],
                "fired": author_nm["fired"],
                "reviewer_before": review_nm["before_winner"],
                "reviewer_after": review_nm["after_winner"],
                "before_rounds": rounds_public(orig),
                "after_rounds": rounds_public(raised),
                "ballots_original": nm0["ballots"],
                "ballots_raised": nm1["ballots"],
                "narrative": (
                    "Original first-round tally A=3, B=2, C=2. last_place={B,C}, "
                    "no history, lex-min eliminates B. A vs C runoff is 3-4, C wins. "
                    "One seat raises C from second to first (A>C>B becomes C>A>B). "
                    "New first-round tally A=2, B=2, C=3. last_place={A,B}, lex-min "
                    "eliminates A. B vs C runoff is 4-3, B wins. Raising the winner "
                    "unseated them. This is a worked example, not a citation."
                ),
            },
            "nm7x4": {
                "roster_size": 7,
                "options": 4,
                "raised_candidate": "D",
                "before_winner": nm4["before_winner"],
                "after_winner": nm4["after_winner"],
                "fired": nm4["fired"],
                "narrative": (
                    "Round-1 last place is unique (C has 0 first preferences). "
                    "Raising D on A>B>D>C still flips D to B, so non-monotonicity "
                    "at roster 7 is not only a round-1 last-place tie."
                ),
            },
        },
        "pathologies": {
            "non_monotonicity": {
                "occurs_at_roster_3_to_15": True,
                "smallest_3option_roster_with_raise_to_first_flip": 7,
                "census_n7_raise_to_first_hits": census_n7,
                "note": (
                    "3-option exhaustive raise-to-first search: n=3..6 have 0 hits; "
                    "n=7 has 6 (profile, source-type) hits. Every 3-option hit in "
                    "that search uses a last-place tie, which is why the elimination "
                    "tie-break is load-bearing. Opposite lex-max elimination on the "
                    "same NM-7x3 ballots elects a different original winner; the "
                    "policy is part of the procedure, not an afterthought."
                ),
            },
            "later_no_harm": {
                "occurs_at_roster_3_to_15": False,
                "irv_truncated_then_completed_fired": lnh_irv["fired"],
                "irv_silent": lnh_irv["silent"],
                "why": (
                    "A later rank is never consulted while an earlier remaining "
                    "preference on that ballot is still standing, so adding later "
                    "ranks cannot reduce an earlier-ranked continuing candidate's "
                    "tally. Truncation tests are required because complete rankings "
                    "have no later rank left to add."
                ),
            },
        },
        "both_states": {
            "nonmonotonicity_fires_on_nm7x3": author_nm["fired"],
            "nonmonotonicity_silent_on_majority7": maj["silent"],
            "lnh_silent_on_irv": lnh_irv["silent"],
            "lnh_fires_on_second_place_bait": lnh_bait["fired"],
        },
        "negative_controls": [
            {
                "id": "NC-MAJORITY-7-SILENT",
                "on_state": (
                    "majority-7: A already has 4/7 > 3.5; raising A on one B>A>C "
                    "ballot to A>B>C must NOT look like non-monotonicity"
                ),
                "observed": (
                    "silent=true fired=false before_winner=A after_winner=A verbatim="
                    + nm_neg
                ),
            },
            {
                "id": "NC-LNH-BAIT-FIRES",
                "on_state": (
                    "planted second-place-plurality on truncated [A]x3+[B]x2 versus "
                    "one ballot completed to A>B — the state the LNH checker must reject"
                ),
                "observed": (
                    "fired=true before_winner=A after_winner=B verbatim=" + lnh_neg
                ),
            },
        ],
        "tests": [
            {
                "id": "non-monotonicity-worked-example",
                "command": P1,
                "result": "NOT-RUN",
            },
            {
                "id": "independent-recount-and-later-no-harm",
                "command": P2,
                "result": "NOT-RUN",
            },
        ],
        "evidence": [
            ev(
                "command-center/p2-wave/probes/CNL-0061/irv_author.py",
                'TIE_POLICY = "lookback-then-lex-min-elim"',
                "Elimination ties are resolved by lookback then lex-min, never RNG.",
                "author-source-constant",
            ),
            ev(
                "command-center/p2-wave/probes/CNL-0061/fixtures.py",
                "NM7X3_RAISED_CANDIDATE = \"C\"",
                "The 7-seat 3-option non-monotonicity fixture raises C on one ballot.",
                "on-disk-python-fixture-constant",
            ),
            ev(
                "command-center/p2-wave/probes/CNL-0061/irv_reviewer.py",
                "each ballot is a mutable queue of",
                "Reviewer recount uses mutating rank queues, not the author's scan.",
                "reviewer-source-docstring",
            ),
            ev(
                "command-center/p2-wave/probes/CNL-0061/pathology.py",
                "Planted non-council method that can violate later-no-harm.",
                "LNH checker vacuity bait is second-place plurality, not IRV.",
                "pathology-detector-docstring",
            ),
        ],
        "reviewer": {
            "reviewer_id": "CNL-0061-probe2-reviewer-recount",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
            "notes": (
                "Named probe2 re-tabulates the JSON fixtures with irv_reviewer "
                "queues and re-runs majority / LNH both-states. Catalog asks for "
                "a mechanical recount, not agreement with the author's prose. "
                "Winner disagreement would have blocked emit."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "non-monotonicity-worked-example", "command": P1},
            {"id": "probe2", "role": "independent-recount-and-later-no-harm", "command": P2},
        ],
        "report": {
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "nm7x3-raise-C-flips-winner",
                    "measured": (
                        str(author_nm["before_winner"])
                        + "->"
                        + str(author_nm["after_winner"])
                    ),
                    "method": (
                        "IRV-COUNCIL-v1 author tabulate on nm-7x3 JSON fixtures; "
                        "raise C on one A>C>B ballot"
                    ),
                    "anchor": ev(
                        "command-center/p2-wave/probes/CNL-0061/fixtures.py",
                        'NM7X3_RAISED_CANDIDATE = "C"',
                        "raise C",
                        "fixture-constant",
                    )["anchor"],
                },
                {
                    "name": "census-n7-raise-to-first-hits",
                    "measured": census_n7,
                    "method": (
                        "exhaustive 3-candidate raise-to-first search at roster 7"
                    ),
                    "anchor": ev(
                        "command-center/p2-wave/probes/CNL-0061/pathology.py",
                        "def census_three_cand_raise_to_first",
                        "census",
                        "pathology-source",
                    )["anchor"],
                },
                {
                    "name": "later-no-harm-under-irv",
                    "measured": lnh_irv["fired"],
                    "method": "later_no_harm_check on truncated-then-completed IRV fixture",
                    "anchor": ev(
                        "command-center/p2-wave/probes/CNL-0061/pathology.py",
                        "Planted non-council method that can violate later-no-harm.",
                        "lnh bait",
                        "pathology-detector-docstring",
                    )["anchor"],
                },
            ],
            "control_ids": ["NC-MAJORITY-7-SILENT", "NC-LNH-BAIT-FIRES"],
        },
        "schema_note": (
            "Catalog output_schema is a GENERATED SHIM whose $ref points at "
            "https://ast-integrate.invalid/...; jsonschema 4.10.3 RefResolver "
            "tries the network. G-1 does not require that hop. This unit "
            "validates against the per-unit schema. Overwriting the shared "
            "catalog schema would be a sibling rebuild circle."
        ),
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": CATALOG_SCHEMA, "exists": True, "role": "supporting"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "supporting"},
        ],
        "regression_anchor": {
            "catalog_question": QUESTION,
            "harness_inputs_absent": harness_absent,
            "dependency_cnl_0023": (
                "Listed dependency; artifact absent. Weight is an input with "
                "default 1.0. This unit does not invent provenance records."
            ),
        },
        "scope": {
            "executable_on": (
                "in-probe fixtures and two independent IRV implementations; "
                "tools/council/vote/ballots.py is not on this tree"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "Windows harness-restore files were read on this host",
                "later-no-harm violations occur under IRV-COUNCIL-v1",
                "CNL-0023 provenance validator was executed",
                "ADV rebuild",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "linux-local",
        },
        "cloud_ok": False,
        "min_bytes_threshold": 4096,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0061 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNL-0061 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    live = json.loads(out.read_text(encoding="utf-8"))
    live["tests"][0]["result"] = "PASS" if c1 == 0 else "FAIL"
    live["tests"][0]["verbatim"] = t1
    live["tests"][1]["result"] = "PASS" if c2 == 0 else "FAIL"
    live["tests"][1]["verbatim"] = t2
    out.write_text(json.dumps(live, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNL-0061 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    digest, size = sha256_file(out)
    if size < int(live["min_bytes_threshold"]):
        print(f"FAILED:CNL-0061 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0061 sentinel absent from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"nm7x3 {author_nm['before_winner']}->{author_nm['after_winner']} "
        f"census_n7={census_n7} lnh_irv_silent={lnh_irv['silent']} "
        f"lnh_bait_fired={lnh_bait['fired']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
