"""Release-mode-aware evaluation of the 21 program stopping conditions.

IMP-0457: a condition that cannot apply under the binding release mode
resolves to an explicitly recorded NOT-APPLICABLE with an owner-visible
justification. It is never a silent TRUE pass and never a permanent FALSE
block. Under PRIVATE-CANARY / PUBLIC-MARKETPLACE the same condition is
REQUIRED.

Applicability lives on the condition table (``applicable_modes``). The
evaluator does not branch on condition id 13.
"""
from __future__ import annotations

import copy
import functools
import json
from pathlib import Path
from typing import Any, Callable, Iterable

REPO = Path(__file__).resolve().parents[2]

BINDING_RELEASE_MODE = "PR-ONLY"
BINDING_DECISION_ID = "OQ-3"
BINDING_DECISION_ANCHOR = (
    "command-center/OWNER-DECISIONS.md OQ-3; "
    "command-center/WORK-UNIT-CATALOG.json owner_questions OQ-3"
)

RELEASE_MODES = (
    "PR-ONLY",
    "PRIVATE-CANARY",
    "PUBLIC-MARKETPLACE",
)
ALL_MODES = frozenset(RELEASE_MODES)
VERDICTS = frozenset({"TRUE", "FALSE", "NOT-APPLICABLE"})
APPLICABILITY = frozenset({"REQUIRED", "NOT-APPLICABLE"})

C13_NA_JUSTIFICATION = (
    "Owner decision OQ-3 binds release mode to PR-ONLY: propose changes as "
    "pull requests, never a private canary and never a public marketplace "
    "release. Condition 13 as written ('release/canary succeeds', spec 11390) "
    "has no referent under that mode — there is no canary channel and no "
    "marketplace release that can succeed — so the as-written predicate is "
    "NOT-APPLICABLE, not TRUE (a silent pass) and not FALSE (a permanent "
    "block). This N/A is mode-conditional, not permanent: REL-0003 rejects "
    "marking 13 permanently N/A, and under PRIVATE-CANARY or "
    "PUBLIC-MARKETPLACE the same condition is REQUIRED. OQ-9 / REL-0003 "
    "(merged PR plus REL-0004/REL-0005/REL-0006 rehearsal) is a different "
    "predicate and is not scored as a silent TRUE here."
)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _spec(
    *,
    id: int,
    spec_line: int,
    text: str,
    text_confidence: str,
    catalog_anchor: str,
    settling_experiment: str,
    applicable_modes: frozenset[str] = ALL_MODES,
    na_owner_decision_id: str = "",
    na_justification: str = "",
    evaluator: str = "fail_closed",
) -> dict[str, Any]:
    return {
        "id": id,
        "spec_line": spec_line,
        "text": text,
        "text_confidence": text_confidence,
        "catalog_anchor": catalog_anchor,
        "settling_experiment": settling_experiment,
        "applicable_modes": frozenset(applicable_modes),
        "na_owner_decision_id": na_owner_decision_id,
        "na_justification": na_justification,
        "evaluator": evaluator,
    }


CONDITIONS: list[dict[str, Any]] = [
    _spec(
        id=1,
        spec_line=11378,
        text=(
            "Every selected option id is IMPLEMENTED, SUPERSEDED, or "
            "REJECTED-WITH-OWNER-REASONING."
        ),
        text_confidence="QUOTED",
        catalog_anchor=(
            "CC-0024 CANONICAL_LINES[11378]; SYN-0028 / stopping condition 1"
        ),
        settling_experiment=(
            "Join every selected option id to a terminal disposition; a "
            "missing join is FALSE (fail closed), not a pass."
        ),
        evaluator="options_terminal",
    ),
    _spec(
        id=2,
        spec_line=11379,
        text=(
            "All contracted artifacts exist and pass schema/manifest checks."
        ),
        text_confidence="RECONSTRUCTED",
        catalog_anchor=(
            "PROGRAM-STOPPING-SCORECARD.json condition 2; spec line 11379 "
            "verbatim absent on this worktree"
        ),
        settling_experiment=(
            "Place _USER-PROMPTS.md:11379 and re-encode; meanwhile fail "
            "closed unless every catalogued output_path exists."
        ),
        evaluator="contracted_artifacts",
    ),
    _spec(
        id=3,
        spec_line=11380,
        text=(
            "All P0/P1 defects are closed or proven externally blocked."
        ),
        text_confidence="RECONSTRUCTED",
        catalog_anchor=(
            "PROGRAM-STOPPING-SCORECARD.json condition 3; spec line 11380 "
            "verbatim absent on this worktree"
        ),
        settling_experiment="Close each live P0/P1 then re-run this evaluator.",
        evaluator="p0_p1_closed",
    ),
    _spec(
        id=4,
        spec_line=11381,
        text="No required test is red.",
        text_confidence="QUOTED",
        catalog_anchor=(
            "WORK-UNIT-CATALOG.json SYN-0043 tests_required: "
            "'condition 4 (no required test is red)'"
        ),
        settling_experiment=(
            "Read the required-test ledger; any red is FALSE. A missing "
            "ledger is FALSE, not a vacuous pass."
        ),
        evaluator="required_tests",
    ),
    _spec(
        id=5,
        spec_line=11382,
        text=(
            "Important test suites include negative controls or mutations "
            "that have been observed to FAIL."
        ),
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11382]; _USER-PROMPTS.md:11382",
        settling_experiment=(
            "For each important suite, resolve a negative control to an "
            "executable artifact that has been observed to FAIL."
        ),
        evaluator="negative_controls",
    ),
    _spec(
        id=6,
        spec_line=11383,
        text="Clean install, update, rollback, and uninstall pass.",
        text_confidence="RECONSTRUCTED",
        catalog_anchor=(
            "PROGRAM-STOPPING-SCORECARD.json condition 6; spec line 11383 "
            "verbatim absent on this worktree"
        ),
        settling_experiment=(
            "Re-run the plugin lifecycle battery including hard-kill and "
            "health-check both-states."
        ),
        evaluator="lifecycle",
    ),
    _spec(
        id=7,
        spec_line=11384,
        text=(
            "Compatibility-matrix cells may only be marked supported by a "
            "recorded test run; an untested cell is not a pass."
        ),
        text_confidence="RECONSTRUCTED",
        catalog_anchor="ARC-0095 inputs cite _USER-PROMPTS.md:11384",
        settling_experiment=(
            "Produce a compatibility-matrix instance whose SUPPORTED cells "
            "all carry a test_run pointer."
        ),
        evaluator="compat_matrix",
    ),
    _spec(
        id=8,
        spec_line=11385,
        text="Intended improvement without material regression.",
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11385]; TST-0324",
        settling_experiment=(
            "Function over a results ledger with run ids; UNMEASURED is "
            "FALSE here (this unit forbids NOT-CHECKED as a stopping verdict)."
        ),
        evaluator="benchmark",
    ),
    _spec(
        id=9,
        spec_line=11386,
        text="Independent confirmers pass.",
        text_confidence="RECONSTRUCTED",
        catalog_anchor=(
            "PROGRAM-STOPPING-SCORECARD.json condition 9; spec line 11386 "
            "verbatim absent on this worktree"
        ),
        settling_experiment="Re-run confirmer probes; require CONFIRMED.",
        evaluator="confirmers",
    ),
    _spec(
        id=10,
        spec_line=11387,
        text=(
            "Adversarial refuters cannot produce an unresolved load-bearing "
            "counterexample."
        ),
        text_confidence="RECONSTRUCTED",
        catalog_anchor=(
            "PROGRAM-STOPPING-SCORECARD.json condition 10; spec line 11387 "
            "verbatim absent on this worktree"
        ),
        settling_experiment=(
            "Close the P12 false-COMPLETE counterexample or stop citing "
            "predicate=COMPLETE as evidence those properties hold."
        ),
        evaluator="refuters",
    ),
    _spec(
        id=11,
        spec_line=11388,
        text=(
            "Release-time re-execution of vulnerability and license scanners "
            "(a stored implementation-time scan does not satisfy)."
        ),
        text_confidence="RECONSTRUCTED",
        catalog_anchor="ADV-0016 spec_anchor _USER-PROMPTS.md:11112, 11129, 11388",
        settling_experiment=(
            "Re-run vuln and license scanners at merge-candidate time and "
            "emit SBOM + license inventory artifacts."
        ),
        evaluator="scanners",
    ),
    _spec(
        id=12,
        spec_line=11389,
        text="Docs and code agree.",
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11389]; ARC-0106 / ADV-0112",
        settling_experiment=(
            "Diff documented commands against measured behaviour; a missing "
            "measurement is FALSE, not a pass."
        ),
        evaluator="docs_code",
    ),
    _spec(
        id=13,
        spec_line=11390,
        text="Release/canary succeeds.",
        text_confidence="QUOTED",
        catalog_anchor=(
            "ARC-0097 / REL-0003 / CC-0015: stop condition 13, spec 11390, "
            "'release/canary succeeds'"
        ),
        settling_experiment=(
            "Under PRIVATE-CANARY observe a canary succeeding; under "
            "PUBLIC-MARKETPLACE observe a marketplace release succeeding. "
            "Under PR-ONLY the as-written referent does not exist (N/A with "
            "OQ-3 justification). The REL-0003 amendment is a different "
            "predicate."
        ),
        applicable_modes=frozenset({"PRIVATE-CANARY", "PUBLIC-MARKETPLACE"}),
        na_owner_decision_id=BINDING_DECISION_ID,
        na_justification=C13_NA_JUSTIFICATION,
        evaluator="release_or_canary",
    ),
    _spec(
        id=14,
        spec_line=11391,
        text="Rollback is tested.",
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 fixture line 11391; REL / ADV-0119",
        settling_experiment=(
            "A recorded rollback/downgrade rehearsal (REL-0006 or equivalent) "
            "must exist and be green."
        ),
        evaluator="rollback",
    ),
    _spec(
        id=15,
        spec_line=11392,
        text=(
            "Every open unknown has a named settling experiment and an "
            "owner-visible impact statement."
        ),
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11392]",
        settling_experiment=(
            "Reconcile UNKNOWNS-REGISTER.md against residual / UNVERIFIED "
            "tags; each open unknown needs both halves."
        ),
        evaluator="unknowns",
    ),
    _spec(
        id=16,
        spec_line=11393,
        text=(
            "At least 160 workflow candidates classified with provenance and "
            "licence records."
        ),
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11393]; WFA-0123",
        settling_experiment=(
            "Count only rows that are classified AND have resolved "
            "provenance AND a fetched licence."
        ),
        evaluator="wf_candidates",
    ),
    _spec(
        id=17,
        spec_line=11394,
        text=(
            "At least 96 materially distinct workflow blueprints executable "
            "under the selected quality tiers."
        ),
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11394]; WFA-0124",
        settling_experiment=(
            "Demonstrate an executor running blueprints end to end; schema "
            "validation alone is not executability."
        ),
        evaluator="blueprints_executable",
    ),
    _spec(
        id=18,
        spec_line=11395,
        text="At least 48 council protocols remain distinct from presets.",
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11395]; SYN-0031 :11393-11396",
        settling_experiment=(
            "Count council protocols and prove protocol ids intersect preset "
            "ids in the empty set."
        ),
        evaluator="protocols_distinct",
    ),
    _spec(
        id=19,
        spec_line=11396,
        text="At least 64 editable presets.",
        text_confidence="QUOTED",
        catalog_anchor="CC-0024 CANONICAL_LINES[11396]; SYN-0031 :11393-11396",
        settling_experiment="Independent recount of editable presets.",
        evaluator="presets",
    ),
    _spec(
        id=20,
        spec_line=11397,
        text="The final synthesis has been meta-reviewed.",
        text_confidence="RECONSTRUCTED",
        catalog_anchor=(
            "PROGRAM-STOPPING-SCORECARD.json condition 20; spec line 11397 "
            "verbatim absent on this worktree"
        ),
        settling_experiment=(
            "A third agent reviews both the Phase-14 synthesis and its "
            "re-derivation; this evaluator is not that review."
        ),
        evaluator="meta_review",
    ),
    _spec(
        id=21,
        spec_line=11398,
        text=(
            "The shared completion predicate returns true for the program."
        ),
        text_confidence="RECONSTRUCTED",
        catalog_anchor=(
            "PROGRAM-STOPPING-SCORECARD.json condition 21; spec line 11398 "
            "verbatim absent on this worktree"
        ),
        settling_experiment=(
            "IMP-0415 shared reducer over live program evidence; exit-zero "
            "alone must not return COMPLETE."
        ),
        evaluator="completion_predicate",
    ),
]

CONDITION_BY_ID: dict[int, dict[str, Any]] = {c["id"]: c for c in CONDITIONS}


def _receipt_state(uid: str) -> str | None:
    path = REPO / "command-center" / "receipts" / f"{uid}.json"
    if not path.is_file():
        return None
    doc = _load_json(path)
    if not isinstance(doc, dict):
        return "UNPARSEABLE"
    return str(doc.get("state") or "")


def _is_candidate_row(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    rid = str(row.get("id") or "")
    if not rid or rid.startswith("_") or "manifest" in rid.lower():
        return False
    return True


def _has_provenance(row: dict[str, Any]) -> bool:
    prov = row.get("provenance")
    if isinstance(prov, dict):
        return any(str(v).strip() for v in prov.values() if v is not None)
    if isinstance(prov, list):
        return len(prov) > 0
    if isinstance(prov, str):
        return bool(prov.strip())
    return False


def _has_license(row: dict[str, Any]) -> bool:
    lic = row.get("license")
    return isinstance(lic, str) and bool(lic.strip())


def _count_wf_candidates() -> dict[str, Any]:
    total = 0
    classified = 0
    floor_met_rows = 0
    files_read = []
    registry = REPO / "platform" / "registry"
    for n in range(1, 6):
        path = registry / f"workflow-candidates-{n}.json"
        files_read.append(path.relative_to(REPO).as_posix())
        data = _load_json(path)
        if not isinstance(data, list):
            continue
        for row in data:
            if not _is_candidate_row(row):
                continue
            total += 1
            if row.get("classification"):
                classified += 1
            if (
                row.get("classification")
                and _has_provenance(row)
                and _has_license(row)
            ):
                floor_met_rows += 1
    return {
        "files": files_read,
        "candidate_rows": total,
        "classified": classified,
        "with_provenance_and_license": floor_met_rows,
        "floor": 160,
        "met": floor_met_rows >= 160,
    }


def _councilspec_ids(directory: Path) -> list[str]:
    ids: list[str] = []
    if not directory.is_dir():
        return ids
    for path in sorted(directory.glob("*.councilspec.json")):
        doc = _load_json(path)
        cid = ""
        if isinstance(doc, dict):
            cid = str(doc.get("id") or doc.get("name") or "")
        if not cid:
            cid = path.stem
        ids.append(cid)
    return ids


@functools.lru_cache(maxsize=1)
def live_observations() -> dict[str, Any]:
    """Cheap on-disk observations. Missing evidence stays fail-closed."""
    marketplace = REPO / "tools" / "marketplace"
    rel6 = _receipt_state("REL-0006")
    rel4 = _receipt_state("REL-0004")
    rel5 = _receipt_state("REL-0005")
    imp0415 = _receipt_state("IMP-0415")
    p12 = REPO / "platform" / "lib" / "_p12_refute_predicate.py"
    executor_hits = [
        REPO / "platform" / "lib" / "wfdsl" / "execute.py",
        REPO / "platform" / "lib" / "workflow_executor.py",
        REPO / "platform" / "workflows" / "executor.py",
    ]
    proto_ids = _councilspec_ids(REPO / "platform" / "council" / "protocols")
    preset_ids = _councilspec_ids(REPO / "platform" / "council" / "presets")
    overlap = sorted(set(proto_ids) & set(preset_ids))
    wf = _count_wf_candidates()
    unknowns = REPO / "command-center" / "UNKNOWNS-REGISTER.md"
    rollback_md = REPO / "command-center" / "ROLLBACK-MANIFEST.md"
    owner = REPO / "command-center" / "OWNER-DECISIONS.md"
    owner_text = owner.read_text(encoding="utf-8") if owner.is_file() else ""
    return {
        "user_prompts_present": (REPO / "_USER-PROMPTS.md").is_file()
        or (REPO / "command-center" / "_USER-PROMPTS.md").is_file(),
        "owner_decisions_present": owner.is_file(),
        "oq3_pr_only": "PR-ONLY" in owner_text
        and "never a private canary" in owner_text.lower(),
        "marketplace_tree_present": marketplace.is_dir(),
        "sbom_instance_count": int(
            (REPO / "platform" / "marketplace" / "sbom.json").is_file()
        ),
        "rel0004_state": rel4,
        "rel0005_state": rel5,
        "rel0006_state": rel6,
        "imp0415_state": imp0415,
        "p12_refuter_present": p12.is_file(),
        "executor_paths_present": [p.as_posix() for p in executor_hits if p.is_file()],
        "protocol_count": len(proto_ids),
        "preset_count": len(preset_ids),
        "protocol_preset_overlap": overlap,
        "wf_candidates": wf,
        "unknowns_register_present": unknowns.is_file(),
        "rollback_manifest_present": rollback_md.is_file(),
        "canary_succeeded": False,
        "marketplace_release_succeeded": False,
        "compat_matrix_instance": (
            REPO / "command-center" / "compatibility-matrix.json"
        ).is_file(),
        "phase14_synthesis": (
            REPO / "command-center" / "PHASE14-SYNTHESIS.md"
        ).is_file(),
    }


EvalFn = Callable[[dict[str, Any], dict[str, Any]], tuple[str, str]]


def _false(msg: str) -> tuple[str, str]:
    return "FALSE", msg


def _true(msg: str) -> tuple[str, str]:
    return "TRUE", msg


def _eval_options_terminal(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    return _false(
        "No selected-option disposition join is on this worktree; OQ-1 "
        "names a delegated list but terminal IMPLEMENTED/SUPERSEDED/"
        "REJECTED-WITH-OWNER-REASONING states are not recorded per id."
    )


def _eval_contracted_artifacts(
    spec: dict[str, Any], obs: dict[str, Any]
) -> tuple[str, str]:
    del spec
    bits = []
    if not obs["marketplace_tree_present"]:
        bits.append("tools/marketplace/ absent")
    if obs["imp0415_state"] is None:
        bits.append("command-center/receipts/IMP-0415.json absent")
    if bits:
        return _false("; ".join(bits))
    return _false(
        "Contracted-artifact census not green; fail closed rather than "
        "inferring a pass from partial presence."
    )


def _eval_p0_p1(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec, obs
    return _false(
        "Live P0/P1 census was not re-closed by this unit; fail closed. "
        "Scorecard and CC-0015 still treat several P1s as open."
    )


def _eval_required_tests(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec, obs
    return _false(
        "Required-test ledger was not re-executed here; a missing ledger "
        "cannot be a vacuous TRUE."
    )


def _eval_negative_controls(
    spec: dict[str, Any], obs: dict[str, Any]
) -> tuple[str, str]:
    del spec, obs
    return _false(
        "Important-suite negative-control observed-FAIL census was not "
        "re-run by this unit."
    )


def _eval_lifecycle(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    rels = (
        obs["rel0004_state"],
        obs["rel0005_state"],
        obs["rel0006_state"],
    )
    if any(str(s or "").upper() != "SUCCESS" for s in rels):
        return _false(
            "REL-0004/REL-0005/REL-0006 are not all SUCCESS on disk "
            f"(states={list(rels)}); install/upgrade/rollback rehearsal "
            "is not green."
        )
    return _false("Lifecycle failure-path (hard-kill lock, health integrity) not proven.")


def _eval_compat(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    if not obs["compat_matrix_instance"]:
        return _false(
            "No compatibility-matrix instance at "
            "command-center/compatibility-matrix.json (schemas are not instances)."
        )
    return _false("Compatibility-matrix instance present but cells not verified here.")


def _eval_benchmark(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec, obs
    return _false(
        "No program-level baseline-vs-after benchmark ledger with run ids "
        "was found; UNMEASURED is FALSE under this unit's tri-state."
    )


def _eval_confirmers(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec, obs
    return _false("Independent confirmer suite was not re-run to all-CONFIRMED.")


def _eval_refuters(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    if obs["p12_refuter_present"]:
        return _false(
            "platform/lib/_p12_refute_predicate.py is present; the P12 "
            "false-COMPLETE counterexample remains a load-bearing unresolved "
            "refutation unless a later unit closed it."
        )
    return _false("No evidence that unresolved refuter counterexamples are gone.")


def _eval_scanners(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    return _false(
        f"Release-time vuln/license scan artifacts missing "
        f"(sbom_instance_count={obs['sbom_instance_count']})."
    )


def _eval_docs_code(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec, obs
    return _false(
        "Docs/code agreement was not re-measured by this unit; fail closed."
    )


def _eval_release_or_canary(
    spec: dict[str, Any], obs: dict[str, Any]
) -> tuple[str, str]:
    del spec
    if obs["canary_succeeded"]:
        return _true("canary_succeeded=true")
    if obs["marketplace_release_succeeded"]:
        return _true("marketplace_release_succeeded=true")
    return _false(
        "As written, condition 13 needs a canary or marketplace release to "
        "succeed. Observed canary_succeeded=false and "
        "marketplace_release_succeeded=false on this worktree."
    )


def _eval_rollback(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    st = str(obs["rel0006_state"] or "").upper()
    if st == "SUCCESS":
        return _true("command-center/receipts/REL-0006.json state=SUCCESS")
    extra = ""
    if obs["rollback_manifest_present"]:
        extra = (
            " command-center/ROLLBACK-MANIFEST.md exists as procedure text, "
            "not as an executed rehearsal receipt."
        )
    return _false(f"REL-0006 state={obs['rel0006_state']!r}.{extra}")


def _eval_unknowns(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    if not obs["unknowns_register_present"]:
        return _false("command-center/UNKNOWNS-REGISTER.md missing")
    return _false(
        "UNKNOWNS-REGISTER.md is present but completeness against live "
        "residuals was not proven by this unit; fail closed."
    )


def _eval_wf_candidates(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    wf = obs["wf_candidates"]
    n = wf["with_provenance_and_license"]
    msg = (
        f"classified+provenance+licence rows={n} floor={wf['floor']} "
        f"candidate_rows={wf['candidate_rows']}"
    )
    if wf["met"]:
        return _true(msg)
    return _false(msg)


def _eval_blueprints(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    if obs["executor_paths_present"]:
        return _false(
            "Executor path present but end-to-end executability of 96 "
            "blueprints was not demonstrated here."
        )
    return _false(
        "No workflow executor module at the probed paths; schema-valid "
        "blueprints are not executable."
    )


def _eval_protocols(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    n = obs["protocol_count"]
    overlap = obs["protocol_preset_overlap"]
    if n >= 48 and not overlap:
        return _true(f"protocol_count={n} >= 48; overlap_with_presets=0")
    if overlap:
        return _false(
            f"protocol_count={n}; protocol/preset id overlap={overlap[:12]}"
        )
    return _false(f"protocol_count={n} < 48")


def _eval_presets(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    n = obs["preset_count"]
    if n >= 64:
        return _true(f"editable preset councilspec count={n} >= 64")
    return _false(f"editable preset councilspec count={n} < 64")


def _eval_meta_review(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    if obs["phase14_synthesis"]:
        return _false(
            "PHASE14-SYNTHESIS.md exists but a third-agent meta-review of "
            "the final synthesis is not this unit."
        )
    return _false("Final-synthesis meta-review artifact not present.")


def _eval_completion(spec: dict[str, Any], obs: dict[str, Any]) -> tuple[str, str]:
    del spec
    st = obs["imp0415_state"]
    return _false(
        f"Shared completion predicate is not program-TRUE here "
        f"(IMP-0415 receipt state={st!r})."
    )


EVALUATORS: dict[str, EvalFn] = {
    "options_terminal": _eval_options_terminal,
    "contracted_artifacts": _eval_contracted_artifacts,
    "p0_p1_closed": _eval_p0_p1,
    "required_tests": _eval_required_tests,
    "negative_controls": _eval_negative_controls,
    "lifecycle": _eval_lifecycle,
    "compat_matrix": _eval_compat,
    "benchmark": _eval_benchmark,
    "confirmers": _eval_confirmers,
    "refuters": _eval_refuters,
    "scanners": _eval_scanners,
    "docs_code": _eval_docs_code,
    "release_or_canary": _eval_release_or_canary,
    "rollback": _eval_rollback,
    "unknowns": _eval_unknowns,
    "wf_candidates": _eval_wf_candidates,
    "blueprints_executable": _eval_blueprints,
    "protocols_distinct": _eval_protocols,
    "presets": _eval_presets,
    "meta_review": _eval_meta_review,
    "completion_predicate": _eval_completion,
    "fail_closed": lambda spec, obs: _false(
        f"no evaluator wired for condition {spec.get('id')}"
    ),
}


def applicability(condition_id: int, release_mode: str) -> str:
    spec = CONDITION_BY_ID[int(condition_id)]
    modes: Iterable[str] = spec["applicable_modes"]
    if release_mode in modes:
        return "REQUIRED"
    return "NOT-APPLICABLE"


def evaluate_condition(
    condition_id: int,
    release_mode: str = BINDING_RELEASE_MODE,
    observations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate one stopping condition under ``release_mode``."""
    if release_mode not in ALL_MODES:
        raise ValueError(f"unknown release_mode {release_mode!r}")
    spec = CONDITION_BY_ID[int(condition_id)]
    obs = observations if observations is not None else live_observations()
    app = applicability(spec["id"], release_mode)
    row: dict[str, Any] = {
        "id": spec["id"],
        "spec_line": spec["spec_line"],
        "text": spec["text"],
        "text_confidence": spec["text_confidence"],
        "catalog_anchor": spec["catalog_anchor"],
        "applicable_modes": sorted(spec["applicable_modes"]),
        "applicability": app,
        "settling_experiment": spec["settling_experiment"],
        "owner_visible_justification": "",
        "owner_decision_id": "",
        "release_mode": release_mode,
    }
    if app == "NOT-APPLICABLE":
        just = str(spec.get("na_justification") or "").strip()
        oid = str(spec.get("na_owner_decision_id") or "").strip()
        row["verdict"] = "NOT-APPLICABLE"
        row["owner_visible_justification"] = just
        row["owner_decision_id"] = oid
        row["evidence"] = just
        return row
    fn = EVALUATORS.get(spec["evaluator"], EVALUATORS["fail_closed"])
    verdict, evidence = fn(spec, obs)
    if verdict not in {"TRUE", "FALSE"}:
        verdict, evidence = _false(f"evaluator returned {verdict!r}")
    row["verdict"] = verdict
    row["evidence"] = evidence
    return row


def validate_rows(
    rows: list[dict[str, Any]],
    release_mode: str = BINDING_RELEASE_MODE,
) -> list[str]:
    """Return validation errors. Empty list means the table is well-formed.

    N/A without a recorded justification is rejected. TRUE on an inapplicable
    condition is a silent pass. FALSE on an inapplicable condition is a
    permanent block. Expected applicability is taken from the condition table
    and ``release_mode``, not from a self-declared row field.
    """
    errors: list[str] = []
    if release_mode not in ALL_MODES:
        errors.append(f"unknown-release-mode:{release_mode}")
        return errors
    if len(rows) != 21:
        errors.append(f"expected-21-conditions got={len(rows)}")
    seen: set[int] = set()
    for row in rows:
        if not isinstance(row, dict):
            errors.append("row-not-object")
            continue
        try:
            cid = int(row.get("id") or 0)
        except (TypeError, ValueError):
            errors.append("row-id-unparseable")
            continue
        if cid not in CONDITION_BY_ID:
            errors.append(f"condition-{cid}:unknown-id")
            continue
        if cid in seen:
            errors.append(f"condition-{cid}:duplicate")
        seen.add(cid)
        expected = applicability(cid, release_mode)
        declared = str(row.get("applicability") or "")
        if declared and declared not in APPLICABILITY:
            errors.append(f"condition-{cid}:invalid-applicability:{declared}")
        elif declared and declared != expected:
            errors.append(
                f"condition-{cid}:applicability-mismatch expected={expected} "
                f"declared={declared}"
            )
        verdict = str(row.get("verdict") or "")
        just = str(row.get("owner_visible_justification") or "").strip()
        oid = str(row.get("owner_decision_id") or "").strip()
        if expected == "NOT-APPLICABLE":
            if verdict == "TRUE":
                errors.append(f"condition-{cid}:inapplicable-as-silent-pass")
            elif verdict == "FALSE":
                errors.append(f"condition-{cid}:inapplicable-as-permanent-block")
            elif verdict == "NOT-APPLICABLE":
                if not just:
                    errors.append(
                        f"condition-{cid}:not-applicable-without-justification"
                    )
                expected_oid = str(
                    CONDITION_BY_ID[cid].get("na_owner_decision_id") or ""
                ).strip()
                if expected_oid and not oid:
                    errors.append(
                        f"condition-{cid}:not-applicable-without-owner-decision-id"
                    )
            else:
                errors.append(f"condition-{cid}:invalid-verdict:{verdict}")
        else:
            if verdict == "NOT-APPLICABLE":
                errors.append(f"condition-{cid}:required-marked-not-applicable")
            elif verdict not in {"TRUE", "FALSE"}:
                errors.append(f"condition-{cid}:invalid-verdict:{verdict}")
    missing = [i for i in range(1, 22) if i not in seen]
    if missing and len(rows) == 21:
        errors.append(f"missing-ids:{missing}")
    return errors


def _tally(rows: list[dict[str, Any]]) -> dict[str, int]:
    out = {"TRUE": 0, "FALSE": 0, "NOT-APPLICABLE": 0}
    for row in rows:
        v = str(row.get("verdict") or "")
        if v in out:
            out[v] += 1
    return out


def evaluate_all(release_mode: str = BINDING_RELEASE_MODE) -> dict[str, Any]:
    """Evaluate all 21 conditions under ``release_mode``."""
    if release_mode not in ALL_MODES:
        raise ValueError(f"unknown release_mode {release_mode!r}")
    if len(CONDITIONS) != 21 or [c["id"] for c in CONDITIONS] != list(range(1, 22)):
        raise RuntimeError("condition table is not 1..21")
    obs = live_observations()
    rows = [evaluate_condition(c["id"], release_mode, obs) for c in CONDITIONS]
    errors = validate_rows(rows, release_mode=release_mode)
    tally = _tally(rows)
    required_false = [
        r["id"]
        for r in rows
        if r["applicability"] == "REQUIRED" and r["verdict"] == "FALSE"
    ]
    program_may_stop = (not errors) and (not required_false) and tally["TRUE"] + tally[
        "NOT-APPLICABLE"
    ] == 21
    return {
        "release_mode": release_mode,
        "binding_release_mode": BINDING_RELEASE_MODE,
        "binding_decision_id": BINDING_DECISION_ID,
        "binding_decision_anchor": BINDING_DECISION_ANCHOR,
        "condition_count": len(rows),
        "conditions": rows,
        "errors": errors,
        "valid": not errors,
        "tally": tally,
        "required_false_ids": required_false,
        "program_may_stop": program_may_stop,
        "observations": {
            "user_prompts_present": obs["user_prompts_present"],
            "oq3_pr_only": obs["oq3_pr_only"],
            "wf_candidates": obs["wf_candidates"],
            "protocol_count": obs["protocol_count"],
            "preset_count": obs["preset_count"],
        },
    }


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    c13 = next(r for r in result["conditions"] if r["id"] == 13)
    na_count = sum(
        1 for r in result["conditions"] if r["verdict"] == "NOT-APPLICABLE"
    )
    return {
        "c13_applicability": c13["applicability"],
        "c13_verdict": c13["verdict"],
        "c13_justification_recorded": bool(
            str(c13.get("owner_visible_justification") or "").strip()
        ),
        "na_count": na_count,
        "valid": result["valid"],
        "program_may_stop": result["program_may_stop"],
        "tally": result["tally"],
    }


def both_states() -> dict[str, Any]:
    """PR-ONLY marks condition 13 N/A; canary/marketplace keep it REQUIRED."""
    pr = evaluate_all("PR-ONLY")
    canary = evaluate_all("PRIVATE-CANARY")
    market = evaluate_all("PUBLIC-MARKETPLACE")
    pr_s = _summary(pr)
    ca_s = _summary(canary)
    mk_s = _summary(market)
    both = (
        pr_s["c13_applicability"] == "NOT-APPLICABLE"
        and pr_s["c13_verdict"] == "NOT-APPLICABLE"
        and pr_s["c13_justification_recorded"]
        and ca_s["c13_applicability"] == "REQUIRED"
        and ca_s["c13_verdict"] != "NOT-APPLICABLE"
        and mk_s["c13_applicability"] == "REQUIRED"
        and mk_s["c13_verdict"] != "NOT-APPLICABLE"
        and pr_s["na_count"] == 1
        and ca_s["na_count"] == 0
        and mk_s["na_count"] == 0
        and pr["valid"]
        and canary["valid"]
        and market["valid"]
    )
    return {
        "both_states": both,
        "pr_only": pr_s,
        "private_canary": ca_s,
        "public_marketplace": mk_s,
    }


def _mutate_c13(rows: list[dict[str, Any]], **fields: Any) -> list[dict[str, Any]]:
    out = copy.deepcopy(rows)
    for row in out:
        if int(row.get("id") or 0) == 13:
            row.update(fields)
    return out


def planted_unjustified_na_errors() -> list[str]:
    result = evaluate_all("PR-ONLY")
    planted = _mutate_c13(
        result["conditions"],
        owner_visible_justification="",
        owner_decision_id="",
        evidence="",
    )
    return validate_rows(planted, release_mode="PR-ONLY")


def planted_silent_pass_errors() -> list[str]:
    result = evaluate_all("PR-ONLY")
    planted = _mutate_c13(
        result["conditions"],
        verdict="TRUE",
        evidence="planted silent pass",
    )
    return validate_rows(planted, release_mode="PR-ONLY")


def planted_permanent_block_errors() -> list[str]:
    result = evaluate_all("PR-ONLY")
    planted = _mutate_c13(
        result["conditions"],
        verdict="FALSE",
        evidence="planted permanent block",
    )
    return validate_rows(planted, release_mode="PR-ONLY")


def main() -> int:
    result = evaluate_all(BINDING_RELEASE_MODE)
    both = both_states()
    print(
        json.dumps(
            {
                "binding_release_mode": BINDING_RELEASE_MODE,
                "valid": result["valid"],
                "errors": result["errors"],
                "tally": result["tally"],
                "program_may_stop": result["program_may_stop"],
                "both_states": both["both_states"],
                "c13": next(r for r in result["conditions"] if r["id"] == 13),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["valid"] and both["both_states"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
