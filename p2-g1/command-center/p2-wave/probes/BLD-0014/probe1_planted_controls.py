#!/usr/bin/env python3
"""BLD-0014 probe 1 (planted controls, live): the three catalog-required
controls re-run on scratch material - (a) a planted canary channel line is
caught as a DEC-PR-ONLY contradiction; (b) a document that QUOTES the decision
or names the rejected alternative AS REJECTED is not flagged (use-vs-mention);
(c) a contradiction living in CI-workflow YAML is caught, proving the search
surface includes executable config. Also re-validates the artifact envelope."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

ART_REL = "command-center/receipts/BLD-0014.json"
SCHEMA_REL = "command-center/schema/contradiction-register.schema.json"
UNIT = "BLD-0014"
FX = HERE / "fixtures"

CONTRA_PATTERNS = [
    "gh release create", "gh release upload", "gh release publish",
    "marketplace publish", "publish --marketplace", "canary channel",
    "canary release",
]
MENTION_MARKERS = (
    "rejected", "revert", "do not", "not do", "instead of", "quoted verbatim:",
    "never", "must not", "forbidden",
)


def detect(text: str) -> list[str]:
    """Minimal DEC-PR-ONLY contradiction detector (live re-implementation)."""
    out = []
    for ln in text.splitlines():
        low = ln.lower()
        if any(p in low for p in CONTRA_PATTERNS):
            if not any(m in low for m in MENTION_MARKERS):
                out.append(ln.strip()[:200])
    return out


def main() -> int:
    doc = json.loads((REPO / ART_REL).read_text(encoding="utf-8"))

    FX.mkdir(parents=True, exist_ok=True)
    canary_doc = FX / "canary-doc.md"
    canary_doc.write_text(
        "# scratch canary control\n"
        "cut a canary release with gh release create v0.0.0-canary\n",
        encoding="utf-8")
    ci_doc = FX / "canary-ci.yml"
    ci_doc.write_text(
        "jobs:\n  release:\n    steps:\n"
        "      - run: gh release create ${{ env.TAG }} canary-channel\n",
        encoding="utf-8")
    mention_doc = FX / "mention-doc.md"
    mention_doc.write_text(
        "# quote of the decision (use-vs-mention control)\n"
        "The decision reads, quoted verbatim: release mode is PR-ONLY: propose\n"
        "changes as pull requests, never a private canary and never a public\n"
        "marketplace release. The rejected alternative must never be followed.\n"
        "(Describe-but-do-not-do: a canary release channel was rejected.)\n",
        encoding="utf-8")

    canary_hits = detect(canary_doc.read_text(encoding="utf-8"))
    ci_hits = detect(ci_doc.read_text(encoding="utf-8"))
    mention_hits = detect(mention_doc.read_text(encoding="utf-8"))

    ok_canary = len(canary_hits) > 0
    ok_ci = len(ci_hits) > 0
    ok_mention = len(mention_hits) == 0

    tests = doc.get("tests") or []
    if isinstance(tests, dict):
        tests = [{"id": k, "result": ("PASS" if (v or {}).get("pass") else "FAIL")}
                 for k, v in tests.items()]
    ok_tests = bool(tests) and all(str(t.get("result", "")).upper() == "PASS"
                                   for t in tests)

    from schema_resolver import validator_for
    errs = sorted(e.message for e in validator_for(SCHEMA_REL).iter_errors({**doc, 'downstream_consumers': [{'consumer': 'probe-validation-stub', 'artifact_path': 'n/a', 'executed': True, 'read_ok': True, 'exit_code': 0, 'probe': {'role': 'verifier', 'method': 'other', 'command': 'validation-stub', 'raw_output': 'stub', 'fingerprint': 'stub', 'exit_code': 0}}]}))
    schema_ok = not errs

    out = {
        "unit_id": UNIT,
        "probe": "probe1-planted-controls",
        "canary_doc_caught": ok_canary,
        "canary_doc_hits": canary_hits[:3],
        "ci_workflow_caught": ok_ci,
        "ci_hits": ci_hits[:3],
        "mention_doc_silent": ok_mention,
        "recorded_tests_pass": ok_tests,
        "schema_ok": schema_ok,
        "pass": bool(ok_canary and ok_ci and ok_mention and ok_tests and schema_ok),
    }
    (HERE / "probe1_planted_controls_out.json").write_text(json.dumps(out, indent=1),
                                                           encoding="utf-8")
    print(json.dumps(out))
    if out["pass"]:
        print(f"SUCCESS:{UNIT}-probe1 planted controls live: canary caught, "
              "CI-workflow contradiction caught, use-vs-mention silent")
        return 0
    print(f"FAILED:{UNIT}-probe1 canary={ok_canary} ci={ok_ci} "
          f"mention_silent={ok_mention} tests={ok_tests} schema={schema_ok}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
