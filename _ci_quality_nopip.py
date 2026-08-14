"""The quality.yml steps that need NO `pip install` -- run them as extra CI substitute.

`_ci_local_substitute.py` covers the eight small workflows. quality.yml is the big one (219
run steps) and most of it needs a per-subproject `pip install -e ".[dev]"` into the runner
env, which is not reproducible here. But a large slice is plain `python -m pytest <path>` or
`python <script>` over pure-stdlib code, and those DO run locally.

Skipping them meant the largest workflow was the least verified while CI was down. This
closes that gap for the part that is honestly runnable, and says nothing about the rest.

Terminal: SUCCESS:quality-nopip / FAILED:quality-nopip <n>
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent
PY = sys.executable

STEPS: list[tuple[str, list[str]]] = [
    (
        "charter-consistency",
        [PY, "-m", "pytest", "ci/tests/test_charter_consistency.py", "-q"],
    ),
    ("cc-tests", [PY, "-m", "pytest", "tools/command-center/tests", "-q"]),
    ("cc-validate", [PY, "tools/command-center/validate.py"]),
    ("cc-render-check", [PY, "tools/command-center/render.py", "--check"]),
    ("casualty-tests", [PY, "-m", "pytest", "command-center/casualty/tests", "-q"]),
    ("casualty-guard", [PY, "command-center/casualty/casualty_guard.py"]),
    ("casualty-redproof", [PY, "command-center/casualty/integration_redproof.py"]),
    ("measure-guard-tests", [PY, "-m", "pytest", "tools/measure-guard/tests", "-q"]),
    (
        "suitefloor-cc",
        [PY, "tools/measure-guard/suitefloor.py", "--suite", "command-center"],
    ),
    (
        "suitefloor-casualty",
        [PY, "tools/measure-guard/suitefloor.py", "--suite", "casualty"],
    ),
    ("refcheck", [PY, "tools/measure-guard/refcheck.py"]),
    ("wudeps", [PY, "tools/measure-guard/wudeps.py"]),
    ("jsonparse", [PY, "tools/measure-guard/jsonparse.py"]),
    ("launchpath", [PY, "tools/measure-guard/launchpath.py"]),
    ("vendordrift", [PY, "tools/measure-guard/vendordrift.py"]),
    (
        "deploy-doc-consistency",
        [PY, "-m", "pytest", "ci/tests/test_deploy_doc_consistency.py", "-q"],
    ),
    (
        "program-b-register",
        [PY, "-m", "pytest", "ci/tests/test_program_b_register.py", "-q"],
    ),
    ("program-b-mutation", [PY, "docs/program-b/mutation_probe.py"]),
    (
        "emit-hook-manifest-tests",
        [PY, "-m", "pytest", "ci/tests/test_emit_hook_manifest.py", "-q"],
    ),
    ("rules-integrity", [PY, "-m", "pytest", "ci/tests/test_rules_integrity.py", "-q"]),
    (
        "coverage-authority",
        [PY, "-m", "pytest", "ci/tests/test_coverage_authority_consistency.py", "-q"],
    ),
    ("rules-scope", [PY, "-m", "pytest", "ci/tests/test_rules_scope.py", "-q"]),
    (
        "rules-selector-inherit",
        [PY, "-m", "pytest", "ci/tests/test_rules_selector_inheritance.py", "-q"],
    ),
    (
        "rules-common-contracts",
        [PY, "-m", "pytest", "ci/tests/test_rules_common_contracts.py", "-q"],
    ),
    (
        "rules-doc-contracts",
        [PY, "-m", "pytest", "ci/tests/test_rules_doc_contracts.py", "-q"],
    ),
    (
        "rules-doc-coherence",
        [PY, "-m", "pytest", "ci/tests/test_rules_doc_coherence.py", "-q"],
    ),
    (
        "rule-audit-ci-wiring",
        [PY, "-m", "pytest", "ci/tests/test_rule_audit_ci_wiring.py", "-q"],
    ),
    (
        "rules-hook-examples",
        [PY, "-m", "pytest", "ci/tests/test_rules_hook_examples.py", "-q"],
    ),
    (
        "review-severity",
        [PY, "-m", "pytest", "ci/tests/test_review_severity_coherence.py", "-q"],
    ),
    (
        "docs-executable-claims",
        [
            PY,
            "-m",
            "pytest",
            "ci/tests/test_docs_executable_claims.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
    ),
    (
        "docs-gate-ci-wiring",
        [
            PY,
            "-m",
            "pytest",
            "ci/tests/test_docs_gate_ci_wiring.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
    ),
    (
        "command-doc-promises",
        [
            PY,
            "-m",
            "pytest",
            "ci/tests/test_command_doc_promises.py",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
    ),
    (
        "deployed-hook-twin-parity",
        [PY, "-m", "pytest", "ci/tests/test_deployed_hook_twin_parity.py", "-q"],
    ),
    ("manifest-provenance", [PY, "hooks/_shared/test_manifest_provenance.py"]),
    ("hookrun", [PY, "hooks/_shared/test_hookrun.py"]),
    ("ledger", [PY, "hooks/event-ledger/test_ledger.py"]),
    ("prune-oats", [PY, "agent-self/config/hooks/event-ledger/test_prune_oats.py"]),
    (
        "claim-gate-selftest",
        [PY, ".agents/skills/claim-verify-gate/scripts/claim_gate.py", "--self-test"],
    ),
    (
        "claim-gate-tests",
        [PY, ".agents/skills/claim-verify-gate/scripts/test_claim_gate.py"],
    ),
    (
        "claim-gate-mutations",
        [PY, ".agents/skills/claim-verify-gate/scripts/test_claim_gate_mutations.py"],
    ),
    ("repo-map", [PY, "tools/repomap/test_repo_map.py"]),
    ("sentinel", [PY, "hooks/tool-result-sentinel/test_sentinel.py"]),
    ("memory-guard", [PY, "hooks/memory-guard/test_scan.py"]),
    (
        "git-hygiene",
        [PY, "-m", "pytest", "-q", "hooks/git-hygiene/test_git_hygiene.py"],
    ),
    # quality.yml runs these three with `working-directory:`, so they are given an explicit
    # cwd below rather than a path from the repo root -- a standalone script that resolves
    # its fixtures relative to cwd fails in a way that looks like a real regression.
    ("triage-router", [PY, "test_triage_router.py"], "tools/triage-router"),
    ("msys-pathconv", [PY, "test_msys_pathconv.py"], "hooks/cmd-rewrite"),
    ("cmd-rewrite-hooks", [PY, "test_hooks.py"], "hooks/cmd-rewrite"),
]

# Normalise: entries may carry an optional third element, the working directory.
STEPS = [(s[0], s[1], (s[2] if len(s) > 2 else None)) for s in STEPS]  # type: ignore[misc]


def main() -> int:
    bad: list[tuple[str, str]] = []
    for sid, argv, wd in STEPS:
        t0 = time.monotonic()
        cwd = REPO / wd if wd else REPO
        try:
            p = subprocess.run(
                argv, cwd=cwd, capture_output=True, text=True, timeout=420
            )
            rc, out = p.returncode, (p.stdout + p.stderr).strip().splitlines()
        except subprocess.TimeoutExpired:
            rc, out = 124, ["TIMEOUT 420s"]
        except FileNotFoundError as exc:
            rc, out = 127, [f"missing: {exc}"]
        dt = time.monotonic() - t0
        last = out[-1][:130] if out else ""
        if rc:
            (REPO / f"_ciq_fail_{sid}.log").write_text(
                "\n".join(out[-200:]), encoding="utf-8"
            )
            bad.append((sid, last))
        print(
            f"{'SUCCESS' if rc == 0 else 'FAILED':7} :{sid:<26} {dt:6.1f}s"
            f"{'  rc=' + str(rc) + '  ' + last if rc else ''}",
            flush=True,
        )

    print("\n" + "=" * 72)
    print(f"quality.yml no-pip slice: {len(STEPS) - len(bad)} pass, {len(bad)} fail")
    for sid, last in bad:
        print(f"  FAILED :{sid}  {last}   -> _ciq_fail_{sid}.log")
    print("SUCCESS:quality-nopip" if not bad else f"FAILED:quality-nopip {len(bad)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
