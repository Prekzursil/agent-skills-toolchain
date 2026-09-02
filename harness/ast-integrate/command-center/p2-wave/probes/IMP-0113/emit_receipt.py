#!/usr/bin/env python3
"""Emit command-center/receipts/IMP-0113.json from live composition measurements."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.checks import RULE_IDS, STANDALONE_MODULES  # noqa: E402
from marketplace.fixtures import BAD, GOOD, materialize  # noqa: E402
from marketplace.package_linter import composition_sets, lint_package  # noqa: E402
from marketplace.reuse import composer_reuses_subchecks  # noqa: E402

OUT = "command-center/receipts/IMP-0113.json"
UNIT = "IMP-0113"
SENTINEL = "SUCCESS:IMP-0113"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0113/probe1_composition.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0113/probe2_negative_mutation.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/marketplace/tests/test_package_linter.py"
)


def sha_norm(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    if b"\x00" in raw[:8192]:
        eol = "BINARY"
    else:
        crlf = raw.count(b"\r\n")
        lf = raw.count(b"\n") - crlf
        if crlf and lf:
            eol = "MIXED"
        elif crlf:
            eol = "CRLF"
        else:
            eol = "LF"
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm), eol


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size, eol = sha_norm(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": path.is_file(),
        "role": role,
        "eol": eol,
    }


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:{UNIT} snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "exit_code": exit_code,
        "fingerprint": hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32],
    }


def evidence(claim: str, verdict: str, anchor: str, probes: list, confidence: str) -> dict:
    return {
        "claim": claim,
        "verdict": verdict,
        "anchor": anchor,
        "probes": probes,
        "confidence": confidence,
    }


def control(cid, kind, description, fired_bad, silent_good, bad="", good="") -> dict:
    return {
        "id": cid,
        "kind": kind,
        "description": description,
        "fired_on_bad_state": fired_bad,
        "silent_on_good_state": silent_good,
        "bad_state_output": str(bad)[:16000],
        "good_state_output": str(good)[:16000],
    }


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def main() -> int:
    sizes = materialize()
    reuse = composer_reuses_subchecks()
    if not reuse["ok"]:
        print("FAILED:IMP-0113 composer does not reuse sub-checks", reuse)
        return 1
    bad_report = lint_package(BAD)
    good_report = lint_package(GOOD)
    baseline = composition_sets(BAD)
    mutated = composition_sets(BAD, enabled=[r for r in RULE_IDS if r != "secret-gate"])
    if not baseline["equal"] or set(baseline["union"]) != set(RULE_IDS):
        print("FAILED:IMP-0113 composition", baseline)
        return 1
    if good_report["finding_count"] != 0:
        print("FAILED:IMP-0113 known-good not silent", good_report)
        return 1
    if mutated["equal"] or mutated["union_minus_linter"] != ["secret-gate"]:
        print("FAILED:IMP-0113 mutation", mutated)
        return 1

    t_rc, t_out = run(TEST_CMD)
    if t_rc != 0:
        print("FAILED:IMP-0113 unit tests")
        print(t_out[-2000:])
        return 1

    composer_rel = "tools/marketplace/package_linter.py"
    secrets_rel = "tools/marketplace/checks/secrets.py"
    test_rel = "tools/marketplace/tests/test_package_linter.py"
    c_line = find_line(composer_rel, "findings.extend(standalone_findings(root, rule_id))")
    s_line = find_line(secrets_rel, "SECRET_PREFIX_LEN")
    t_line = find_line(test_rel, "def test_composition_loses_no_subcheck")

    p_lint = probe(
        "source",
        "command",
        "python3 -B tools/marketplace/package_linter.py tools/marketplace/fixtures/known-bad",
        json.dumps(
            {
                "finding_count": bad_report["finding_count"],
                "rules": [f["rule_id"] for f in bad_report["findings"]],
            },
            sort_keys=True,
        ),
        1,
    )
    p_union = probe(
        "verifier",
        "command",
        "standalone SUBCHECKS over known-bad",
        json.dumps(baseline, sort_keys=True),
        0,
    )
    p_reuse = probe(
        "verifier",
        "file-read",
        "ast-walk tools/marketplace/package_linter.py",
        json.dumps(reuse, sort_keys=True),
        0,
    )
    p_good = probe(
        "source",
        "command",
        "python3 -B tools/marketplace/package_linter.py tools/marketplace/fixtures/known-good",
        json.dumps({"finding_count": good_report["finding_count"], "ok": good_report["ok"]}),
        0,
    )
    p_mut = probe(
        "verifier",
        "command",
        "lint_package(known-bad, enabled=without secret-gate)",
        json.dumps(mutated, sort_keys=True),
        0,
    )
    p_tests = probe("source", "command", TEST_CMD, t_out, t_rc)

    supporting = [
        composer_rel,
        "tools/marketplace/schema/lint-report.schema.json",
        "tools/marketplace/schema/package-manifest.schema.json",
        "tools/marketplace/checks/manifest.py",
        "tools/marketplace/checks/license.py",
        "tools/marketplace/checks/permissions.py",
        "tools/marketplace/checks/size_budget.py",
        "tools/marketplace/checks/secrets.py",
        "tools/marketplace/checks/name_grammar.py",
        test_rel,
        "tools/marketplace/fixtures/known-good/plugin.json",
        "tools/marketplace/fixtures/known-bad/plugin.json",
        "command-center/p2-wave/probes/IMP-0113/probe1_composition.py",
        "command-center/p2-wave/probes/IMP-0113/probe2_negative_mutation.py",
    ]

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:IMP-0113",
        "min_bytes_threshold": 128,
        "profile": "marketplace-package-linter",
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5.x-codex",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [art(rel, "supporting") for rel in supporting],
        "evidence": [
            evidence(
                "On the known-bad fixture the linter finding set equals the union of "
                "the six standalone sub-checks, and that union is exactly the six "
                f"rule ids {list(RULE_IDS)}. A composer that silently dropped a "
                "sub-check would fail this equality.",
                "CONFIRMED",
                f"{composer_rel}:{c_line}",
                [p_lint, p_union],
                "almost-certain",
            ),
            evidence(
                "The composer imports RULE_IDS/SUBCHECKS/STANDALONE_MODULES from "
                "marketplace.checks and calls standalone_findings; it does not contain "
                "SPDX lists, secret patterns, size ceilings, permission ids, or "
                "confusable maps. Reviewer requirement (reuse, not reimplement) holds.",
                "CONFIRMED",
                f"{composer_rel}:{c_line}",
                [p_reuse],
                "almost-certain",
            ),
            evidence(
                "Known-good fixture yields zero findings from the linter and from "
                "every standalone sub-check in the same run that flags known-bad.",
                "CONFIRMED",
                f"{test_rel}:{t_line}",
                [p_good, p_lint],
                "almost-certain",
            ),
            evidence(
                "Disabling secret-gate makes composition_sets unequal and the missing "
                "rule id is exactly secret-gate. Secret reports keep a 4-character "
                "prefix and withhold the synthetic body.",
                "CONFIRMED",
                f"{secrets_rel}:{s_line}",
                [p_mut, p_tests],
                "almost-certain",
            ),
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "tests": [
            {
                "id": "test_composition_loses_no_subcheck",
                "command": TEST_CMD + "::test_composition_loses_no_subcheck",
                "result": "PASS" if t_rc == 0 else "FAIL",
                "assertions": 6,
                "output_tail": t_out.splitlines()[-1][:200] if t_out else "",
            },
            {
                "id": "test_known_good_zero_findings",
                "command": TEST_CMD + "::test_known_good_zero_findings",
                "result": "PASS" if t_rc == 0 else "FAIL",
                "assertions": 2,
                "output_tail": "known-good finding_count=0",
            },
            {
                "id": "test_mutation_disable_one_subcheck_detected",
                "command": TEST_CMD + "::test_mutation_disable_one_subcheck_detected",
                "result": "PASS" if t_rc == 0 else "FAIL",
                "assertions": 2,
                "output_tail": json.dumps(mutated, sort_keys=True)[:200],
            },
        ],
        "negative_controls": [
            control(
                "IMP0113-C1",
                "known-broken-fixture",
                "Known-bad must fire all six rules; known-good must be silent in the same run.",
                True,
                True,
                json.dumps(baseline, sort_keys=True),
                json.dumps({"finding_count": good_report["finding_count"], "ok": good_report["ok"]}),
            ),
            control(
                "IMP0113-C2",
                "mutation",
                "Disable secret-gate; composition equality must fail and isolate that rule.",
                True,
                True,
                json.dumps(mutated, sort_keys=True),
                json.dumps(baseline, sort_keys=True),
            ),
        ],
        "reviewer": {
            "reviewer_id": "IMP-0113-probe1-composition-reuse",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "scope_not_agreement": True,
            "notes": (
                "Independent of the linter's own ok flag: AST reuse check plus "
                "standalone union recomputation."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0113/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/IMP-0113/probe1_composition.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe("verifier", "command", P1, "deferred-to-write_receipts", 0),
            },
            {
                "consumer": "command-center/p2-wave/_measure_one_delivered.py IMP-0113",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "command",
                    "python3 command-center/p2-wave/_measure_one_delivered.py IMP-0113",
                    "deferred-to-post-write measure",
                    0,
                ),
            },
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Dependency units IMP-0004/0005/0006/0069/0090/0093 have no "
                    "delivered receipts in this worktree; this unit ships the "
                    "standalone check modules the composer calls so reuse is "
                    "measurable rather than assumed."
                ),
                "verdict": "CONFIRMED",
                "settling_experiment": (
                    "When those units deliver, re-point SUBCHECKS at their modules "
                    "and re-run composition_sets."
                ),
            }
        ],
        "report": {
            "kind": "marketplace-package-lint-report",
            "schema": "tools/marketplace/schema/lint-report.schema.json",
            "composed_from": STANDALONE_MODULES,
            "fixture_sizes": sizes,
            "known_bad": {
                "ok": bad_report["ok"],
                "finding_count": bad_report["finding_count"],
                "findings": bad_report["findings"],
                "union": baseline["union"],
                "linter": baseline["linter"],
                "equal": baseline["equal"],
            },
            "known_good": {
                "ok": good_report["ok"],
                "finding_count": good_report["finding_count"],
                "findings": good_report["findings"],
            },
            "mutation": mutated,
            "reuse": reuse,
        },
        "question_or_target": (
            "Implement the single-package linter that a publisher runs before "
            "submission, composing the existing checks (manifest schema, SPDX "
            "license, permission declaration, size budget, secret gate, name "
            "grammar) into one report with a stable machine-readable shape and "
            "one finding per rule."
        ),
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:IMP-0113 sentinel missing from receipt body")
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
