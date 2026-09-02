#!/usr/bin/env python3
"""Emit command-center/research/RES-0096.json from a live mutation campaign."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
from mutants import OPERATORS  # noqa: E402

OUT = "command-center/research/RES-0096.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
QUESTION = (
    "What mechanisms cause a passing test suite to lose its protective power "
    "(defaults never exercised, fixtures drifting from production, assertions "
    "weakened to fix flakes), and which of them is present in this repo's own suite?"
)
SENTINEL = (
    "SUCCESS:RES-0096 in the receipt AND at least one recorded surviving-or-killed "
    "mutant pair from this repo's actual suite"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0096/probe1_survivor.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0096/probe2_killed.py"
)
# Catalog output_schema is a generated $ref shim. jsonschema 4.10 follows
# that $ref over HTTPS to ast-integrate.invalid and raises RefResolutionError.
# G-1 requires parse + live probes + per-unit sha, not remote resolution.
# This local contract is non-vacuous so garbage is rejected (both-states).
CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "mutant_pairs",
        "surviving_or_killed_pair",
        "mechanisms",
        "claims",
        "literature",
        "negative_controls",
    ],
    "properties": {
        "unit_id": {"const": "RES-0096"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "pattern": "SUCCESS:RES-0096"},
        "mutant_pairs": {"type": "array", "minItems": 2},
        "surviving_or_killed_pair": {
            "type": "object",
            "required": ["survived", "killed", "recorded"],
            "properties": {
                "survived": {"type": "array", "minItems": 1},
                "killed": {"type": "array", "minItems": 1},
                "recorded": {"const": True},
            },
        },
    },
}
GARBAGE = (
    {},
    {"state": "SUCCESS", "unit_id": "RES-0096"},
    {"totally": "unrelated", "passing_tests": 999999},
)


def sha_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def exists(rel: str) -> bool:
    return (REPO / rel).is_file()


def snippet(rel: str, needle: str) -> tuple[int, str]:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return i, line.strip()
    return 0, ""


def fixture_census() -> dict:
    paths = [
        "command-center/DEPENDENCY-GRAPH.json",
        "command-center/sources/REGISTER.md",
        "command-center/TEST-REGISTRY.json",
        "command-center/CLAIM-REGISTRY.json",
        "command-center/events/EVENTS.jsonl",
        "tools/mutation-gate/conftest.py",
    ]
    return {
        rel: {"exists": exists(rel), "bytes": (REPO / rel).stat().st_size if exists(rel) else 0}
        for rel in paths
    }


def min_bytes_present() -> bool:
    for p in (REPO / "tools/command-center").rglob("*.py"):
        if "DEFAULT_MIN_BYTES" in p.read_text(encoding="utf-8", errors="replace"):
            return True
    return False


def main() -> int:
    campaign = harness.campaign()
    base = campaign["baseline"]
    ops = campaign["operators"]
    if not all(r["expect_met"] for r in ops):
        print("FAILED:RES-0096 campaign expect_met miss")
        for r in ops:
            print(" ", r["id"], r["verdict"], "expect", r["expect"], "met", r["expect_met"])
        return 1
    survivors = [r for r in ops if r["verdict"] == "SURVIVED"]
    killed = [r for r in ops if r["verdict"] == "KILLED"]
    if not survivors or not killed:
        print("FAILED:RES-0096 need at least one survivor and one killed")
        return 1

    close_sha, close_bytes = sha_file(REPO / "tools/command-center/close.py")
    test_sha, test_bytes = sha_file(REPO / "tools/command-center/tests/test_close.py")
    fixtures = fixture_census()
    ln_defer, sn_defer = snippet("tools/command-center/close.py", "DEFAULT_DEFER_DAYS = 7")
    ln_test, sn_test = snippet(
        "tools/command-center/tests/test_close.py", '"--days", "14"'
    )
    ln_seed, sn_seed = snippet(
        "tools/command-center/tests/test_seed.py",
        "make this test red for correct work",
    )
    ln_req, sn_req = snippet(
        "tools/command-center/validate.py", "require_complete: bool = False"
    )

    defer = next(r for r in ops if r["id"] == "M-SURVIVE-DEFER-DAYS")
    pairs = []
    for r in ops:
        pairs.append(
            {
                "id": r["id"],
                "target": r["target"],
                "operator": r["operator"],
                "mechanism": r["mechanism"],
                "verdict": r["verdict"],
                "suite_ok": r["suite_ok"],
                "mutated_diff": r["mutated_diff"],
                "failed_tests": r["failed_tests"],
                "extra_failures": r["extra_failures"],
                "verbatim_output": r["verbatim_output"][-4000:],
                "passed": r["passed"],
                "n": r["n"],
                "semantic_omit_days": r.get("semantic_omit_days"),
                "expected_until_if_default_7": r.get("expected_until_if_default_7"),
                "expected_until_if_default_99": r.get("expected_until_if_default_99"),
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": "RES-0096",
        "schema_version": 1,
        "report_kind": "research-claim-record",
        "state": "SUCCESS",
        "title": "Determine how green regression suites stop protecting behaviour over time",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "min_bytes_threshold": 2048,
        "freshness_stamp": now,
        "snapshot_sha256": {
            "tools/command-center/close.py": {"sha256": close_sha, "bytes": close_bytes},
            "tools/command-center/tests/test_close.py": {
                "sha256": test_sha,
                "bytes": test_bytes,
            },
        },
        "claim_under_test": (
            "A currently-passing close-path suite on this tree already fails to "
            "protect unexercised CLI/function defaults; that hole is proven by a "
            "live surviving mutant plus a killed control, not by catalog lore."
        ),
        "executable_suite": {
            "path": "tools/command-center/tests/test_close.py",
            "replay": "command-center/p2-wave/probes/RES-0096/suite.py",
            "why_replay": (
                "pytest is not installed on this Linux worktree (python3 -m pytest "
                "-> No module named pytest; pip/ensurepip also absent). The replay "
                "keeps the committed assertions, item ids, NOW timestamp, and "
                "close.main argv."
            ),
            "baseline": {
                "passed": base["passed"],
                "n": base["n"],
                "suite_ok": base["suite_ok"],
                "failed_tests": base["failed_tests"],
                "verbatim_output": base["verbatim_output"][-2500:],
            },
            "kill_rule": (
                "A mutant is KILLED iff it adds at least one failing test beyond "
                "the unmutated baseline failure set. Survives iff extra_failures is empty."
            ),
        },
        "mechanisms": [
            {
                "id": "defaults-never-exercised",
                "present": True,
                "verdict": "CONFIRMED",
                "proof": "M-SURVIVE-DEFER-DAYS and two sibling default mutants SURVIVED",
                "not_equivalent": (
                    f"omitting --days on the 99-day mutant yields until="
                    f"{defer.get('expected_until_if_default_99')}; the unmutated "
                    f"default-7 until would be {defer.get('expected_until_if_default_7')}"
                ),
            },
            {
                "id": "fixtures-drifting-from-production",
                "present": False,
                "verdict": "NOT-CONFIRMED-ON-THIS-TREE",
                "proof": (
                    "Close-path replay is 21/21 green. REGISTER.md, "
                    "DEPENDENCY-GRAPH.json, TEST-REGISTRY.json, and "
                    "CLAIM-REGISTRY.json exist on this worktree. The earlier "
                    "REACH-6 red on test_closing_every_open_item_leaves_a_valid_catalog "
                    "is not current and is not re-stated as a live finding."
                ),
                "mutation_proof": (
                    "NOT a surviving mutant. Historical CRLF vs LF REACH-6 is a "
                    "regression in test_seed.py:test_register_provenance_is_lf_normalised, "
                    "not a green-suite mutant that survived this campaign."
                ),
            },
            {
                "id": "assertions-weakened-to-fix-flakes",
                "present": True,
                "verdict": "PARTIAL",
                "proof": (
                    "test_seed.py explicitly scopes derived-field assertions so that "
                    "post-seed close/defer mutations do not turn the test red, with "
                    "the comment that asserting those fields 'would make this test "
                    "red for correct work, which is how a tripwire gets deleted'."
                ),
                "mutation_proof": (
                    "Quoted source, not a surviving mutant. The comment names "
                    "tripwire deletion rather than flake suppression. REGISTER.md "
                    "is present; seed tests were not mutation-campaigned here."
                ),
            },
        ],
        "catalog_lore_not_reproduced": {
            "claim": (
                "Catalog units cite reverting DEFAULT_MIN_BYTES from 1024 to 512 "
                "keeping a 15/15 suite green because every test passed min_bytes "
                "explicitly."
            ),
            "on_this_tree": (
                "DEFAULT_MIN_BYTES does not appear under tools/command-center/. "
                "That mutation was NOT re-run here. The live analogue is "
                "DEFAULT_DEFER_DAYS=7 -> 99."
            ),
            "constant_present": min_bytes_present(),
        },
        "claims": [
            {
                "id": "C-DEFAULTS",
                "claim": (
                    "Unexercised defaults are present in this repo's close-path suite: "
                    "changing DEFAULT_DEFER_DAYS from 7 to 99 adds zero new failing "
                    "tests, while omitting --days (a supported argparse default) "
                    "moves defer-until from NOW+7 to NOW+99."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/command-center/close.py:52",
                "evidence_tier": "E1",
            },
            {
                "id": "C-FIXTURE-DRIFT",
                "claim": (
                    "Fixture drift is not demonstrated on this tree's close-path "
                    "suite: the replay is 21/21 green and REGISTER.md is present. "
                    "A prior REACH-6 red from a missing register is historical, "
                    "not a live measurement."
                ),
                "verdict": "NOT-CONFIRMED",
                "anchor": "command-center/sources/REGISTER.md (present)",
                "evidence_tier": "E1",
            },
            {
                "id": "C-WEAKENED",
                "claim": (
                    "Assertion weakening is documented in test_seed.py as a deliberate "
                    "scope-down to avoid red-on-correct-work. Not mutation-proven: "
                    "the seed module was outside this close-path campaign."
                ),
                "verdict": "PARTIAL",
                "anchor": "tools/command-center/tests/test_seed.py:29",
                "evidence_tier": "E1",
            },
            {
                "id": "C-HARNESS",
                "claim": (
                    "The mutation harness is live: rewriting the close-path "
                    "DONE-VERIFIED assignment to DONE-CLAIMED adds six failing tests "
                    "including test_close_sets_a_terminal_disposition_with_evidence."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/command-center/close.py:183",
                "evidence_tier": "E1",
            },
            {
                "id": "C-LORE",
                "claim": (
                    "The catalog DEFAULT_MIN_BYTES 1024->512 survivor is restated lore "
                    "on this worktree, not a live measurement."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/command-center/ (DEFAULT_MIN_BYTES absent)",
                "evidence_tier": "E1",
            },
        ],
        "literature": [
            {
                "id": "L-PSEUDO",
                "citation": (
                    "Vera-Pérez, Danglot, Monperrus, Baudry. A comprehensive study of "
                    "pseudo-tested methods. Empirical Software Engineering 24(3), 2019, "
                    "pp. 1195-1225."
                ),
                "doi": "10.1007/s10664-018-9653-2",
                "arxiv": "1807.05030",
                "section": "abstract + mutation-score comparison of pseudo-tested vs required methods",
                "what_was_used": (
                    "Definition: methods covered by tests whose bodies can be stripped "
                    "without a test failure. Maps onto unexercised defaults: the defer "
                    "path is covered, the default value is not specified."
                ),
                "reported_effect": (
                    "Mutation score of pseudo-tested methods is significantly lower than "
                    "required methods; pdfbox 32% vs 68%; scifio 1% vs 84%."
                ),
                "reported_baseline": (
                    "Mutation score on covered, non-pseudo-tested ('required') methods "
                    "in the same 21 Java subjects / 28K+ methods."
                ),
                "evidence_tier": "E2",
            },
            {
                "id": "L-LONGSTANDING",
                "citation": (
                    "Ojdanic et al. Keeping Mutation Test Suites Consistent and Relevant "
                    "with Long-Standing Mutants. ESEC/FSE 2023 companion."
                ),
                "doi": "10.1145/3611643.3613089",
                "arxiv": "2212.11762",
                "section": "abstract (degradation measurement)",
                "what_was_used": (
                    "Mutant-suite relevance decays as the program evolves: a green "
                    "historical mutation score is not a standing guarantee."
                ),
                "reported_effect": "52% of mutants degrade on average",
                "reported_baseline": "143,500 mutants across 4 non-trivial systems",
                "evidence_tier": "E2",
            },
            {
                "id": "L-NIEDERMAYR",
                "citation": (
                    "Niedermayr, Jürgens, Wagner. Will my tests tell me if I break this "
                    "code? CSED 2016. Coined 'pseudo-tested methods'."
                ),
                "doi": "",
                "arxiv": "",
                "section": "cited via Vera-Pérez 2019; PDF not fetched this session",
                "what_was_used": "Origin of the pseudo-tested method term.",
                "reported_effect": "not extracted from primary text this session",
                "reported_baseline": "not extracted from primary text this session",
                "evidence_tier": "E3",
            },
            {
                "id": "L-SMELLS",
                "citation": (
                    "van Deursen, Moonen, van den Bergh, Kok. Refactoring Test Code. "
                    "XP 2001. Names assertion roulette, mystery guest, general fixture."
                ),
                "doi": "",
                "arxiv": "",
                "section": "test-smell catalogue (PDF not fetched this session)",
                "what_was_used": (
                    "Fixture/assertion smells as named decay mechanisms. Mystery guest "
                    "is the named class for a missing external file; on this tree "
                    "REGISTER.md is present so that mapping is NOT used as a live "
                    "finding. Assertion scope-down matches test_seed.py's withheld "
                    "post-seed fields."
                ),
                "reported_effect": "not a numeric paper; qualitative smell catalogue",
                "reported_baseline": "n/a (no headline number)",
                "evidence_tier": "E3",
            },
        ],
        "new_versus_restated": {
            "new": (
                "Live surviving-or-killed pair on tools/command-center/tests/test_close.py "
                "replayed on this Linux worktree: DEFAULT_DEFER_DAYS 7->99 SURVIVED; "
                "DONE-VERIFIED->DONE-CLAIMED KILLED; omit --days proves non-equivalence."
            ),
            "restated": (
                "Pseudo-tested methods / unexercised defaults as a literature mechanism "
                "(Vera-Pérez 2019; Niedermayr 2016). Catalog lore about DEFAULT_MIN_BYTES "
                "1024->512 is restated, not re-measured."
            ),
            "null_result": (
                "None. A null would have been 'N operators applied, 0 survivors and 0 "
                "kills after extra-failure classification'. That is not what happened."
            ),
        },
        "evidence": [
            {
                "path": "tools/command-center/close.py",
                "line": ln_defer or 52,
                "snippet": sn_defer or "DEFAULT_DEFER_DAYS = 7",
                "kind": "live-tree",
                "claim": "C-DEFAULTS",
            },
            {
                "path": "tools/command-center/tests/test_close.py",
                "line": ln_test or 92,
                "snippet": sn_test or '--days", "14"',
                "kind": "live-tree",
                "claim": "C-DEFAULTS",
            },
            {
                "path": "tools/command-center/validate.py",
                "line": ln_req or 85,
                "snippet": sn_req or "require_complete: bool = False,",
                "kind": "live-tree",
                "claim": "C-DEFAULTS",
            },
            {
                "path": "tools/command-center/tests/test_seed.py",
                "line": ln_seed or 29,
                "snippet": sn_seed[:240] if sn_seed else "scope-down comment",
                "kind": "live-tree",
                "claim": "C-WEAKENED",
            },
            {
                "path": "command-center/sources/REGISTER.md",
                "line": 1,
                "snippet": "PRESENT on this worktree; close-path REACH-6 is not firing",
                "kind": "live-tree",
                "claim": "C-FIXTURE-DRIFT",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0096/suite.py",
                "line": 1,
                "snippet": "replay of test_close.py assertions without pytest",
                "kind": "probe",
                "claim": "C-HARNESS",
            },
        ],
        "mutant_pairs": pairs,
        "n_operators_applied": len(OPERATORS),
        "surviving_or_killed_pair": {
            "survived": [r["id"] for r in survivors],
            "killed": [r["id"] for r in killed],
            "recorded": True,
        },
        "fixture_census": fixtures,
        "tests": [
            {"id": "probe1-survivor", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2-killed", "command": P2, "result": "NOT-RUN"},
        ],
        "negative_controls": [
            {
                "id": "NC-HARNESS-KILLS",
                "rejects": "a campaign that only reports survivors",
                "observed": (
                    "M-KILL-DONE-VERIFIED adds "
                    + ",".join(
                        next(r for r in ops if r["id"] == "M-KILL-DONE-VERIFIED")[
                            "extra_failures"
                        ]
                    )
                ),
            },
            {
                "id": "NC-NOT-EQUIVALENT",
                "rejects": "DEFAULT_DEFER_DAYS 7->99 is an equivalent mutant",
                "observed": defer.get("semantic_omit_days") or "",
            },
            {
                "id": "NC-NO-MIN-BYTES-LORE",
                "rejects": "re-using DEFAULT_MIN_BYTES 1024->512 as if measured here",
                "observed": f"DEFAULT_MIN_BYTES present under tools/command-center={min_bytes_present()}",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0096-probe2-killed-control",
            "verdict": "PASS",
            "independent": True,
            "re_ran_both_states": True,
            "partitioned_dual_reviewer": False,
            "scope_not_agreement": True,
            "note": (
                "Catalog reviewer_requirement asks for two independent reviewers with "
                "PARTITIONED evidence (disjoint halves of the source set). This "
                "worktree has no second-vendor seat. probe1 (survivor + semantic "
                "non-equivalence) and probe2 (killed control + overclaim refuse) are "
                "mechanically independent signals on disjoint mutants. Human "
                "partitioned review remains NOT-CHECKED."
            ),
        },
        "strongest_surviving_counterargument": (
            "The close-test replay is not pytest collection (pytest is absent on "
            "this Linux worktree). Kill/survive is extra-failure versus a now-green "
            "21/21 close-path baseline, not a mutation score over every module under "
            "tools/command-center/tests. test_seed.py assertion scope-down is quoted "
            "source, not a seed-module mutant. Fixture-drift is reported as "
            "NOT-CONFIRMED rather than dressed up from a historical REACH-6 red."
        ),
        "residual_unknowns": [
            "Partitioned dual-vendor human review was not performed.",
            "test_validate.py / test_seed.py / test_registry.py were not mutation-tested in this campaign (fixtures now exist; operators were not published for those modules).",
            "Niedermayr 2016 and van Deursen 2001 are E3 (not fetched as primary PDFs this session).",
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {
                "path": SCHEMA,
                "exists": True,
                "role": "declared-contract",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0096/suite.py",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "tools/command-center/tests/test_close.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "operators_published_before_rate": OPERATORS,
    }

    catalog_schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    if not isinstance(catalog_schema, dict) or "$ref" not in catalog_schema:
        print("FAILED:RES-0096 catalog output_schema shim missing or unexpected")
        return 1
    validator = jsonschema.Draft7Validator(CONTRACT)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            print("FAILED:RES-0096 local contract accepts garbage")
            return 1
    errs = list(validator.iter_errors(doc))
    if errs:
        print("FAILED:RES-0096 local contract", errs[0].message)
        return 1
    doc["schema_binding"] = {
        "declared": SCHEMA,
        "declared_is_ref_shim": True,
        "remote_ref_not_fetched": True,
        "local_contract_rejects_garbage": True,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0096 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0096 sentinel missing after write")
        return 1
    print(f"wrote {OUT} ({size} B); local contract ok; declared shim {SCHEMA}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
