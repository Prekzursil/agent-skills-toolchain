"""Eight implementer-versus-confirmer disagreements with executable probes.

CNF-0118 (second-order sample) and CNF-0013 (discrepancy router) are absent on
this worktree. This corpus is the substitute disagreement list: each case has
raw source on disk, recorded reasoning on both sides, and a probe that can
return either verdict. Head count is recorded and ignored.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"


def _read(rel: str) -> str:
    return (FIX / rel).read_text(encoding="utf-8")


def _load_py(rel: str) -> dict:
    ns: dict = {}
    exec(_read(rel), ns)
    return ns


def _claim(rel: str) -> str:
    return _read(rel).strip()


def probe_d1() -> dict:
    ns = _load_py("d1/add.py")
    add = ns["add"]
    code_ok = add(2, 3) == 5
    sentence_ok = True
    err = ""
    try:
        add(None, 1)
    except TypeError as exc:
        sentence_ok = False
        err = type(exc).__name__
    supports = "implementer" if (code_ok and sentence_ok) else "confirmer"
    return {
        "id": "D1-add-never-fails",
        "code_ok": code_ok,
        "sentence_ok": sentence_ok,
        "supports": supports,
        "output": json.dumps(
            {
                "add_2_3": add(2, 3),
                "code_ok": code_ok,
                "add_None_1": err or "no-exception",
                "sentence_ok": sentence_ok,
            },
            sort_keys=True,
        ),
    }


def probe_d2() -> dict:
    ran = json.loads(_read("d2/ran.json"))
    inv = json.loads(_read("d2/inventory.json"))
    code_ok = set(ran).issubset(set(inv)) and len(ran) == 3
    sentence_ok = set(ran) == set(inv)
    supports = "implementer" if sentence_ok else "confirmer"
    return {
        "id": "D2-every-test-passes",
        "code_ok": code_ok,
        "sentence_ok": sentence_ok,
        "supports": supports,
        "output": json.dumps(
            {
                "ran": ran,
                "inventory_n": len(inv),
                "unrun": sorted(set(inv) - set(ran)),
                "code_ok": code_ok,
                "sentence_ok": sentence_ok,
            },
            sort_keys=True,
        ),
    }


def probe_d3() -> dict:
    ns = _load_py("d3/parser.py")
    parse = ns["parse"]
    json_ok = parse(_read("d3/ok.json"), "json") == {"ok": True}
    yaml_err = ""
    yaml_ok = True
    try:
        parse(_read("d3/sample.yaml"), "yaml")
    except ValueError as exc:
        yaml_ok = False
        yaml_err = str(exc)
    code_ok = json_ok
    sentence_ok = json_ok and yaml_ok
    supports = "implementer" if sentence_ok else "confirmer"
    return {
        "id": "D3-all-formats",
        "code_ok": code_ok,
        "sentence_ok": sentence_ok,
        "supports": supports,
        "output": json.dumps(
            {
                "json_ok": json_ok,
                "yaml_ok": yaml_ok,
                "yaml_err": yaml_err,
                "code_ok": code_ok,
                "sentence_ok": sentence_ok,
            },
            sort_keys=True,
        ),
    }


def probe_d4() -> dict:
    scanned = json.loads(_read("d4/scanned.json"))
    unscanned = json.loads(_read("d4/unscanned.json"))
    code_ok = scanned.get("findings") == []
    sentence_ok = code_ok and unscanned.get("findings") == []
    supports = "implementer" if sentence_ok else "confirmer"
    return {
        "id": "D4-zero-vulns-estate",
        "code_ok": code_ok,
        "sentence_ok": sentence_ok,
        "supports": supports,
        "output": json.dumps(
            {
                "scanned_findings": scanned.get("findings"),
                "unscanned_findings": unscanned.get("findings"),
                "code_ok": code_ok,
                "sentence_ok": sentence_ok,
            },
            sort_keys=True,
        ),
    }


def probe_d5() -> dict:
    ns = _load_py("d5/handler.py")
    handle = ns["handle"]
    ok_code = handle("/ok")
    missing_code = handle("/missing")
    code_ok = ok_code == 200
    sentence_ok = ok_code == 200 and missing_code == 200
    supports = "implementer" if sentence_ok else "confirmer"
    return {
        "id": "D5-always-200",
        "code_ok": code_ok,
        "sentence_ok": sentence_ok,
        "supports": supports,
        "output": json.dumps(
            {
                "GET_/ok": ok_code,
                "GET_/missing": missing_code,
                "code_ok": code_ok,
                "sentence_ok": sentence_ok,
            },
            sort_keys=True,
        ),
    }


def probe_d6() -> dict:
    ns = _load_py("d6/validate.py")
    validate = ns["validate"]
    missing_y_accepted = validate({"x": 1}) is True
    code_ok = not missing_y_accepted
    sentence_ok = code_ok
    supports = "implementer" if sentence_ok else "confirmer"
    return {
        "id": "D6-required-key-y",
        "code_ok": code_ok,
        "sentence_ok": sentence_ok,
        "supports": supports,
        "output": json.dumps(
            {
                "missing_y_accepted": missing_y_accepted,
                "code_ok": code_ok,
                "sentence_ok": sentence_ok,
            },
            sort_keys=True,
        ),
    }


def probe_d7() -> dict:
    ns = _load_py("d7/load.py")
    load = ns["load"]
    missing = FIX / "d7" / "no-such-file.json"
    got = load(str(missing))
    fail_closed = got.get("ok") is False
    code_ok = fail_closed
    sentence_ok = fail_closed
    supports = "implementer" if sentence_ok else "confirmer"
    return {
        "id": "D7-fail-closed-missing",
        "code_ok": code_ok,
        "sentence_ok": sentence_ok,
        "supports": supports,
        "output": json.dumps(
            {
                "missing_result": got,
                "fail_closed": fail_closed,
                "code_ok": code_ok,
                "sentence_ok": sentence_ok,
            },
            sort_keys=True,
        ),
    }


def probe_d8() -> dict:
    text = _read("d8/lines.txt")
    n = len(text.splitlines())
    votes = json.loads(_read("d8/votes.json"))
    code_ok = n == 8
    sentence_ok = n == 8
    supports = "implementer" if sentence_ok else "confirmer"
    return {
        "id": "D8-line-count-vs-votes",
        "code_ok": code_ok,
        "sentence_ok": sentence_ok,
        "supports": supports,
        "agent_votes": votes,
        "output": json.dumps(
            {
                "line_count": n,
                "claimed": 8,
                "agent_votes": votes,
                "code_ok": code_ok,
                "sentence_ok": sentence_ok,
            },
            sort_keys=True,
        ),
    }


# Implementer always filed CONFIRMED; confirmer always filed REFUTED.
# agent_votes are recorded so a later check can prove they were not the tie-break.
CASES = [
    {
        "id": "D1",
        "raw_source": "command-center/p2-wave/probes/CNF-0119/fixtures/d1/add.py",
        "claim_path": "command-center/p2-wave/probes/CNF-0119/fixtures/d1/claim.txt",
        "original_wording": None,  # filled at run
        "implementer_verdict": "CONFIRMED",
        "implementer_reasoning": "add(2,3)==5 in the unit test; therefore add never fails.",
        "confirmer_verdict": "REFUTED",
        "confirmer_reasoning": "The sentence quantifies over any Python values; add(None,1) raises.",
        "agent_votes": {"implementer": 1, "confirmer": 1},
        "expected_classification": "overclaim",
        "scoped": "add returns the sum of two numbers.",
        "probe": probe_d1,
    },
    {
        "id": "D2",
        "raw_source": "command-center/p2-wave/probes/CNF-0119/fixtures/d2/ran.json",
        "claim_path": "command-center/p2-wave/probes/CNF-0119/fixtures/d2/claim.txt",
        "original_wording": None,
        "implementer_verdict": "CONFIRMED",
        "implementer_reasoning": "The three tests that were run passed.",
        "confirmer_verdict": "REFUTED",
        "confirmer_reasoning": "Inventory has 12 tests; 9 were never run. 'Every' is wider than the run set.",
        "agent_votes": {"implementer": 1, "confirmer": 1},
        "expected_classification": "overclaim",
        "scoped": "The three tests that were run (t1, t2, t3) passed; nine inventory tests were not run.",
        "probe": probe_d2,
    },
    {
        "id": "D3",
        "raw_source": "command-center/p2-wave/probes/CNF-0119/fixtures/d3/parser.py",
        "claim_path": "command-center/p2-wave/probes/CNF-0119/fixtures/d3/claim.txt",
        "original_wording": None,
        "implementer_verdict": "CONFIRMED",
        "implementer_reasoning": "ok.json parses.",
        "confirmer_verdict": "REFUTED",
        "confirmer_reasoning": "yaml is refused; 'all formats' is false.",
        "agent_votes": {"implementer": 1, "confirmer": 1},
        "expected_classification": "overclaim",
        "scoped": "The parser accepts JSON and refuses other formats.",
        "probe": probe_d3,
    },
    {
        "id": "D4",
        "raw_source": "command-center/p2-wave/probes/CNF-0119/fixtures/d4/scanned.json",
        "claim_path": "command-center/p2-wave/probes/CNF-0119/fixtures/d4/claim.txt",
        "original_wording": None,
        "implementer_verdict": "CONFIRMED",
        "implementer_reasoning": "The scanned package has an empty findings list.",
        "confirmer_verdict": "REFUTED",
        "confirmer_reasoning": "An unscanned sibling records CVE-2015-4852. Estate-wide zero is unmeasured.",
        "agent_votes": {"implementer": 1, "confirmer": 1},
        "expected_classification": "overclaim",
        "scoped": "The scanned fixture-clean package has zero findings; the estate was not fully scanned.",
        "probe": probe_d4,
    },
    {
        "id": "D5",
        "raw_source": "command-center/p2-wave/probes/CNF-0119/fixtures/d5/handler.py",
        "claim_path": "command-center/p2-wave/probes/CNF-0119/fixtures/d5/claim.txt",
        "original_wording": None,
        "implementer_verdict": "CONFIRMED",
        "implementer_reasoning": "GET /ok returns 200.",
        "confirmer_verdict": "REFUTED",
        "confirmer_reasoning": "GET /missing returns 404; 'always' is false.",
        "agent_votes": {"implementer": 1, "confirmer": 1},
        "expected_classification": "overclaim",
        "scoped": "GET /ok returns 200; other paths return 404.",
        "probe": probe_d5,
    },
    {
        "id": "D6",
        "raw_source": "command-center/p2-wave/probes/CNF-0119/fixtures/d6/validate.py",
        "claim_path": "command-center/p2-wave/probes/CNF-0119/fixtures/d6/claim.txt",
        "original_wording": None,
        "implementer_verdict": "CONFIRMED",
        "implementer_reasoning": "validate() returns True for dict inputs, so invalid documents are handled.",
        "confirmer_verdict": "REFUTED",
        "confirmer_reasoning": "A dict missing required key y is accepted. That is a real defect, not wording.",
        "agent_votes": {"implementer": 1, "confirmer": 1},
        "expected_classification": "real-defect",
        "scoped": "validate() currently accepts any dict; it does not reject a document missing key y.",
        "probe": probe_d6,
    },
    {
        "id": "D7",
        "raw_source": "command-center/p2-wave/probes/CNF-0119/fixtures/d7/load.py",
        "claim_path": "command-center/p2-wave/probes/CNF-0119/fixtures/d7/claim.txt",
        "original_wording": None,
        "implementer_verdict": "CONFIRMED",
        "implementer_reasoning": "Missing files return an empty item list rather than crashing.",
        "confirmer_verdict": "REFUTED",
        "confirmer_reasoning": "ok=true with items=[] is fail-open, not fail-closed.",
        "agent_votes": {"implementer": 1, "confirmer": 1},
        "expected_classification": "real-defect",
        "scoped": "A missing file currently returns ok=true and items=[]. That is fail-open.",
        "probe": probe_d7,
    },
    {
        "id": "D8",
        "raw_source": "command-center/p2-wave/probes/CNF-0119/fixtures/d8/lines.txt",
        "claim_path": "command-center/p2-wave/probes/CNF-0119/fixtures/d8/claim.txt",
        "original_wording": None,
        "implementer_verdict": "CONFIRMED",
        "implementer_reasoning": "Three agents counted eight lines.",
        "confirmer_verdict": "REFUTED",
        "confirmer_reasoning": "splitlines() on the file is 7. Head count does not settle a line count.",
        "agent_votes": {"implementer": 3, "confirmer": 1},
        "expected_classification": "real-defect",
        "scoped": "The file contains 7 lines (LF splitlines), not 8.",
        "probe": probe_d8,
    },
]


def with_wording(case: dict) -> dict:
    row = dict(case)
    rel = case["claim_path"].split("fixtures/", 1)[1]
    row["original_wording"] = _claim(rel)
    return row
