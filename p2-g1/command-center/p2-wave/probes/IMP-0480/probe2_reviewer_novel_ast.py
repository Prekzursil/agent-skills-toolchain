#!/usr/bin/env python3
"""IMP-0480 probe2: novel reviewer-authored injections + the AST mutant.

Three novel injections the catalog corpus has never seen (base64-exec,
file-URI, tool-override role-spoof) must all produce identical consuming
output. The AST auditor must find the consume module clean (payload never
reaches apply_policy), and a MUTANT consumer that passes item.body into
apply_policy must be flagged (mutation detected)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
AB = REPO / "tools" / "artifact_boundary"


def load_mod(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(AB.parent))
consume = load_mod("imp0480_consume", AB / "consume.py")
corpus = load_mod("imp0480_corpus", AB / "corpus.py")
policy = load_mod("imp0480_policy", AB / "policy.py")
ast_guard = load_mod("imp0480_ast_guard", AB / "ast_guard.py")

POL = policy.TrustedPolicy()

MUTANT_SOURCE = '''
from artifact_boundary.corpus import Artifact
from artifact_boundary.policy import TrustedPolicy


def consume_stage_mutant(artifacts, policy):
    facts = []
    for item in artifacts:
        apply_policy(item.body, policy)  # payload reaches apply_policy
        facts.append([item.kind, str(item.score)])
    return {"facts": facts}
'''


def fail(msg):
    print("FAILED:IMP-0480-probe2 " + str(msg))
    return 1


def main() -> int:
    base = corpus.baseline_artifacts()
    clean_out = consume.behavior_of(base, POL)

    # (a) novel injections: identical output, every one.
    novel_rows = []
    for inj_id, clean, dirty in corpus.novel_pairs():
        a = consume.behavior_of(clean, POL)
        b = consume.behavior_of(dirty, POL)
        identical = a == b
        naive = sys.modules.get("imp0480_naive")
        if naive is None:
            naive = load_mod("imp0480_naive", AB / "naive.py")
        diverged = naive.naive_consume(clean, POL) != naive.naive_consume(dirty, POL)
        if not identical:
            return fail("novel injection %s changed consuming output" % inj_id)
        novel_rows.append({"id": inj_id, "boundary_identical": identical, "naive_diverged": diverged})

    # (b) AST audit: production consume module is clean.
    audit = ast_guard.audit_consume_module(AB / "consume.py")
    if not audit["clean"]:
        return fail("production consume module failed the AST audit: %s" % audit["findings"])
    if not audit["wraps"] or not audit["applies_policy"]:
        return fail("AST audit structural check incomplete: %s" % audit)

    # (c) AST mutant: a consumer passing body into apply_policy is flagged.
    findings = ast_guard.audit_source(MUTANT_SOURCE, label="mutant-consumer")
    if not findings:
        return fail("AST mutant not detected - auditor cannot fire")
    flagged = any(f["id"] == "payload-reaches-apply_policy" for f in findings)
    if not flagged:
        return fail("mutant flagged but with wrong finding id: %s" % findings)

    print(json.dumps({
        "probe": "probe2-reviewer-novel-ast",
        "unit_id": "IMP-0480",
        "novel_classes": [r["id"] for r in novel_rows],
        "novel_rows": novel_rows,
        "ast_audit_clean": audit["clean"],
        "ast_findings": audit["findings"],
        "ast_structural": {k: audit[k] for k in ("wraps", "extracts", "applies_policy")},
        "ast_mutant_detected": flagged,
        "ast_mutant_finding": findings[0]["id"],
        "behavioral_baseline_verdict": clean_out.get("verdict"),
        "sentinel": "SENTINEL:IMP-0480:INJECTION-BOUNDARY-HELD",
    },  indent=2))
    print("SUCCESS:IMP-0480-probe2 three novel injections identical; consume module AST-clean; body-to-apply_policy mutant detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
