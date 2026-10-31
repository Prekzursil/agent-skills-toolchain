"""P12 refutation probe: can the 12 completion conditions be SATISFIED without the
property each names?

Method: construct receipts against the SHIPPED reducer (platform/lib/completion_predicate.py,
imported, not re-implemented) and record the reducer's own verdict. Every attack carries a
both-states control: the attack fixture, plus the corresponding HONEST-BROKEN fixture the
condition is supposed to reject, so a "SATISFIED" reading cannot be a blind detector.

Run:  python platform/lib/_p12_refute_predicate.py
Out:  platform/lib/_p12_refute_predicate_out.json  (+ terminal marker on stdout)
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from completion_predicate import (  # noqa: E402
    ABSOLUTE_MIN_BYTES,
    CLASS_SIZE_FLOORS,
    Outcome,
    PredicateOptions,
    Verdict,
    evaluate,
)

RESULTS: list[dict[str, Any]] = []


def _sha256_lf(p: Path) -> str:
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_manifest(root: Path, entries: list[tuple[str, Path]]) -> Path:
    mp = root / "MANIFEST.json"
    mp.write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "path": rel,
                        "bytes": p.stat().st_size,
                        "present": True,
                        "sha256": _sha256_lf(p),
                    }
                    for rel, p in entries
                ]
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    return mp


def record(
    attack: str,
    condition: int,
    property_named: str,
    outcome: Outcome,
    verdict: Verdict,
    basis: str,
    control: dict[str, Any],
    why: str,
) -> None:
    RESULTS.append(
        {
            "attack": attack,
            "condition": condition,
            "property_named_by_the_condition": property_named,
            "reducer_outcome": outcome.value,
            "overall_verdict": verdict.value,
            "reducer_basis": basis,
            "both_states_control": control,
            "refutation": why,
        }
    )


# ------------------------------------------------------------------ A: the full COMPLETE forgery


def build_forgery(root: Path) -> tuple[dict[str, Any], PredicateOptions]:
    """A receipt that reaches COMPLETE while:
    - no test ever ran        (condition 7 is a self-declaration)
    - no reviewer ever looked (condition 9: reviewer_id == the author, independent:true)
    - no consumer ever read   (condition 12: probe.raw_output is a hand-typed string)
    - no control ever fired   (condition 8 is two booleans)
    - the artifact is a stub  (condition 3: receipt declares its own threshold)
    - the evidence is ONE probe declared twice (condition 6 skips independence unless the
      per-item verdict is CONFIRMED/REFUTED)
    """
    art = root / "stub.json"
    # 96 bytes of nothing, but it must carry the sentinel and parse as JSON.
    payload = {"note": "SUCCESS:ZZ-0001 nothing was measured", "pad": "x" * 24}
    art.write_text(json.dumps(payload), encoding="utf-8")
    schema = root / "permissive.schema.json"
    schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")
    mp = _write_manifest(root, [("stub.json", art)])

    one_probe = {
        "role": "source",
        "method": "read",
        "command": "cat stub.json",
        "fingerprint": "fp-identical",
        "raw_output": "{}",
    }
    receipt = {
        "unit_id": "ZZ-0001",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ZZ-0001 nothing was measured",
        "min_bytes_threshold": 1,  # self-declared; floor is raised only to 64
        "artifacts": [
            {
                "path": "stub.json",
                "role": "primary",
                "artifact_class": "json",
                "exists": True,
            }
        ],
        "evidence": [
            # Two items, ONE probe. verdict is PARTIAL, so the same-probe-rerun and
            # method-independence checks are never reached.
            {
                "anchor": "stub.json:1",
                "verdict": "PARTIAL",
                "probes": [dict(one_probe)],
            },
            {
                "anchor": "stub.json:1",
                "verdict": "PARTIAL",
                "probes": [dict(one_probe)],
            },
        ],
        "tests": [
            {"id": "t-never-ran", "result": "PASS", "command": "pytest -q"},
        ],
        "negative_controls": [
            {
                "id": "nc-never-ran",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "produced_by": {"agent": "agent-alpha", "vendor": "anthropic"},
        "reviewer": {
            "reviewer_id": "agent-alpha",  # THE AUTHOR
            "verdict": "PASS",
            "independent": True,  # self-declared
            "vendor": "anthropic",
        },
        "defects": [],
        "manifest_registration": {"registered": True, "manifest_path": "MANIFEST.json"},
        "downstream_consumers": [
            {
                "consumer": "nobody",
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {"raw_output": "ok"},
            }
        ],
    }
    opts = PredicateOptions(
        repo_root=root,
        output_schema="permissive.schema.json",
        min_evidence_anchors=2,
        require_cross_vendor_review=False,
    )
    return receipt, opts


def attack_a(root: Path) -> dict[str, Any]:
    receipt, opts = build_forgery(root)
    res = evaluate(receipt, opts)
    art_bytes = (root / "stub.json").stat().st_size

    # Both-states control: the reducer is NOT blind. Break one measured condition and
    # confirm the same fixture flips to INCOMPLETE.
    broken = json.loads(json.dumps(receipt))
    broken["sentinel"] = "SUCCESS:ZZ-0001 a sentinel not in the artifact"
    res_broken = evaluate(broken, opts)

    control = {
        "known_broken_fixture": "sentinel absent from the artifact text",
        "verdict_on_broken": res_broken.verdict.value,
        "condition_5_on_broken": res_broken.condition(5).outcome.value,
        "detector_fires_on_known_broken": res_broken.verdict is not Verdict.COMPLETE,
    }
    for n, prop in (
        (3, "artifact is non-empty and exceeds a meaningful minimum size"),
        (6, "required evidence anchors exist"),
        (7, "required tests ran and passed"),
        (8, "negative controls or mutations fail as expected"),
        (9, "independent reviewer status is PASS"),
        (12, "downstream consumers can read it"),
    ):
        c = res.condition(n)
        record(
            f"A-forgery/c{n}",
            n,
            prop,
            c.outcome,
            res.verdict,
            c.basis,
            control,
            {
                3: (
                    f"artifact is {art_bytes} B. The receipt declared min_bytes_threshold=1; the "
                    f"reducer raised it only to ABSOLUTE_MIN_BYTES={ABSOLUTE_MIN_BYTES}. "
                    f"CLASS_SIZE_FLOORS['json']={CLASS_SIZE_FLOORS['json']} is never applied to "
                    "the comparison - it appears only inside an error string - so the receipt "
                    "sets its own bar and a stub clears it."
                ),
                6: (
                    "both evidence items carry the SAME probe fingerprint 'fp-identical' and the "
                    "same method. The same-probe-rerun and method-independence checks live inside "
                    "`if verdict in {CONFIRMED, REFUTED}`, so labelling the item PARTIAL skips "
                    "them and no verifier probe is required at all."
                ),
                7: (
                    "no test process was started by anything in this probe. The reducer reads "
                    "result=='PASS' and a non-empty command string; it never executes the command "
                    "and never consults a test log."
                ),
                8: (
                    "no control was run. fired_on_bad_state/silent_on_good_state are two booleans "
                    "the receipt writes about itself."
                ),
                9: (
                    "reviewer_id == produced_by.agent ('agent-alpha'). independent:true is a "
                    "self-declared flag that is never cross-checked against produced_by. "
                    "command-center/catalog-slices/CNF-1.json (CNF-0121 tests_required[0]) "
                    "contracts that 'a receipt with a reviewer field containing the author must "
                    "be rejected'; this reducer accepts it."
                ),
                12: (
                    "no consumer process ran. executed/read_ok/exit_code are receipt fields and "
                    "probe.raw_output is the literal string 'ok'."
                ),
            }[n],
        )
    return {
        "verdict": res.verdict.value,
        "counts": res.counts,
        "sentinel_line": res.sentinel_line,
        "artifact_bytes": art_bytes,
        "control": control,
        "per_condition": {
            c.n: {"outcome": c.outcome.value, "basis": c.basis} for c in res.conditions
        },
    }


# --------------------------------------------------- B: condition 2 digest skip (uppercase hex)


def attack_b(root: Path) -> dict[str, Any]:
    """Condition 2 claims it always re-hashes. It skips the re-hash unless the declared digest
    is lowercase 64-hex - and still reports 're-hashed against the receipt'."""
    d = root / "b"
    d.mkdir(exist_ok=True)
    art = d / "a.json"
    art.write_text(json.dumps({"real": "content", "pad": "y" * 40}), encoding="utf-8")
    schema = d / "s.schema.json"
    schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")
    _write_manifest(d, [("a.json", art)])
    wrong = "0" * 64  # a digest that matches nothing

    def run(declared_sha: str | None) -> Any:
        r = {
            "unit_id": "ZZ-0002",
            "state": "SUCCESS",
            "sentinel": "SUCCESS:ZZ-0002 x",
            "artifacts": [
                {
                    "path": "a.json",
                    "role": "primary",
                    "artifact_class": "json",
                    **({"sha256": declared_sha} if declared_sha else {}),
                }
            ],
        }
        return evaluate(r, PredicateOptions(repo_root=d))

    lower = run(wrong)  # known-broken: must be caught
    upper = run(wrong.replace("0", "A"))  # same wrongness, uppercase
    absent = run(None)
    prefixed = run("sha256:" + wrong)

    for label, res, why in (
        (
            "uppercase-hex",
            upper,
            "a 64-char uppercase digest fails the lowercase-only _SHA256_HEX guard, so the "
            "re-hash branch is skipped entirely",
        ),
        (
            "sha256-prefixed",
            prefixed,
            "a 'sha256:'-prefixed digest also fails the regex and skips the re-hash",
        ),
        (
            "absent",
            absent,
            "no digest declared at all: nothing is re-hashed",
        ),
    ):
        c = res.condition(2)
        record(
            f"B-digest-skip/{label}",
            2,
            "expected artifact exists (module docstring: 'RE-HASHES the bytes on disk ... A "
            "declared digest is never trusted')",
            c.outcome,
            res.verdict,
            c.basis,
            {
                "known_broken_fixture": "lowercase 64-hex digest of all zeros (same wrong value)",
                "condition_2_on_broken": lower.condition(2).outcome.value,
                "detector_fires_on_known_broken": lower.condition(2).outcome
                is Outcome.UNSATISFIED,
            },
            why
            + ". The SATISFIED basis string still asserts the artifacts were 're-hashed "
            "against the receipt', so the report claims a measurement that did not run.",
        )
    return {
        "lowercase_wrong": lower.condition(2).outcome.value,
        "uppercase_wrong": upper.condition(2).outcome.value,
        "prefixed_wrong": prefixed.condition(2).outcome.value,
        "absent": absent.condition(2).outcome.value,
        "uppercase_basis": upper.condition(2).basis,
    }


# --------------------------------------------------------- C: condition 4 jsonl false negative


def attack_c(root: Path) -> dict[str, Any]:
    """Condition 4 json.loads() the WHOLE file, so a legitimate multi-line .jsonl artifact is
    reported as 'does not parse as JSON'. Direction: fails closed, but it makes every jsonl
    unit uncompletable, and CLASS_SIZE_FLOORS carries a 'jsonl' entry so jsonl is expected."""
    d = root / "c"
    d.mkdir(exist_ok=True)
    art = d / "log.jsonl"
    art.write_text(
        "\n".join(json.dumps({"i": i, "pad": "z" * 30}) for i in range(6)) + "\n",
        encoding="utf-8",
    )
    schema = d / "s.schema.json"
    schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")
    _write_manifest(d, [("log.jsonl", art)])
    r = {
        "unit_id": "ZZ-0003",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ZZ-0003 x",
        "artifacts": [
            {"path": "log.jsonl", "role": "primary", "artifact_class": "jsonl"}
        ],
    }
    res = evaluate(r, PredicateOptions(repo_root=d, output_schema="s.schema.json"))
    single = d / "one.jsonl"
    single.write_text(json.dumps({"i": 0, "pad": "z" * 40}), encoding="utf-8")
    r2 = dict(r)
    r2["artifacts"] = [
        {"path": "one.jsonl", "role": "primary", "artifact_class": "jsonl"}
    ]
    res2 = evaluate(r2, PredicateOptions(repo_root=d, output_schema="s.schema.json"))
    c = res.condition(4)
    record(
        "C-jsonl-parse",
        4,
        "artifact parses against its schema",
        c.outcome,
        res.verdict,
        c.basis,
        {
            "known_good_fixture": "a single-line .jsonl (one JSON document)",
            "condition_4_on_single_line": res2.condition(4).outcome.value,
            "detector_discriminates": res2.condition(4).outcome is Outcome.SATISFIED,
        },
        "a valid 6-record JSON Lines artifact is UNSATISFIED because the evaluator calls "
        "json.loads() on the entire file instead of per line; the same fixture with one record "
        "passes, proving the failure is the line-delimited form, not the content.",
    )
    return {
        "multiline_jsonl": c.outcome.value,
        "multiline_basis": c.basis,
        "single_line_jsonl": res2.condition(4).outcome.value,
    }


# --------------------------------------------- D: condition 4 mixed-artifact partial validation


def attack_d(root: Path) -> dict[str, Any]:
    """Condition 4 returns SATISFIED when at least one primary artifact validated, even if
    another primary artifact was never validated at all."""
    d = root / "d"
    d.mkdir(exist_ok=True)
    good = d / "ok.json"
    good.write_text(json.dumps({"k": 1, "pad": "q" * 40}), encoding="utf-8")
    md = d / "report.md"
    md.write_text("SUCCESS:ZZ-0004 x\n" + "prose " * 40, encoding="utf-8")
    schema = d / "s.schema.json"
    schema.write_text(
        json.dumps({"type": "object", "required": ["k"]}), encoding="utf-8"
    )
    _write_manifest(d, [("ok.json", good), ("report.md", md)])
    r = {
        "unit_id": "ZZ-0004",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ZZ-0004 x",
        "artifacts": [
            {"path": "ok.json", "role": "primary", "artifact_class": "json"},
            {"path": "report.md", "role": "primary", "artifact_class": "markdown"},
        ],
    }
    res = evaluate(r, PredicateOptions(repo_root=d, output_schema="s.schema.json"))
    only_md = dict(r)
    only_md["artifacts"] = [
        {"path": "report.md", "role": "primary", "artifact_class": "markdown"}
    ]
    res_md = evaluate(
        only_md, PredicateOptions(repo_root=d, output_schema="s.schema.json")
    )
    c = res.condition(4)
    record(
        "D-mixed-artifact",
        4,
        "artifact parses against its schema",
        c.outcome,
        res.verdict,
        c.basis,
        {
            "known_broken_fixture": "the markdown artifact ALONE",
            "condition_4_alone": res_md.condition(4).outcome.value,
            "detector_fires_on_known_broken": res_md.condition(4).outcome
            is Outcome.NOT_CHECKED,
        },
        "with a json + a markdown primary, condition 4 reports SATISFIED 'validated against "
        "s.schema.json' although the markdown was skipped as 'not JSON-bearing'. The same "
        "markdown alone is correctly NOT-CHECKED, so pairing it with any JSON artifact "
        "launders an unvalidated primary into a pass.",
    )
    return {
        "mixed": c.outcome.value,
        "mixed_basis": c.basis,
        "markdown_alone": res_md.condition(4).outcome.value,
        "per_artifact": c.detail.get("results"),
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="p12-refute-") as td:
        root = Path(td)
        out = {
            "probe": "platform/lib/_p12_refute_predicate.py",
            "reducer_under_test": "platform/lib/completion_predicate.py",
            "A_full_forgery": attack_a(root),
            "B_digest_skip": attack_b(root),
            "C_jsonl_parse": attack_c(root),
            "D_mixed_artifact": attack_d(root),
            "findings": RESULTS,
        }
    dest = HERE / "_p12_refute_predicate_out.json"
    dest.write_text(json.dumps(out, indent=1), encoding="utf-8")
    forged = out["A_full_forgery"]["verdict"]
    print(json.dumps(out["A_full_forgery"], indent=1)[:1800])
    print()
    print("A: forged receipt verdict =", forged)
    print("A: control on known-broken =", out["A_full_forgery"]["control"])
    print("B:", json.dumps(out["B_digest_skip"], indent=1))
    print("C:", json.dumps(out["C_jsonl_parse"], indent=1))
    print("D:", json.dumps(out["D_mixed_artifact"], indent=1))
    print(f"wrote {dest}")
    ok_control = out["A_full_forgery"]["control"]["detector_fires_on_known_broken"]
    if forged == "COMPLETE" and ok_control:
        print("SUCCESS:p12-refute-predicate REFUTED forgery=COMPLETE control=fires")
        return 0
    print(f"FAILED:p12-refute-predicate forgery={forged} control={ok_control}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
