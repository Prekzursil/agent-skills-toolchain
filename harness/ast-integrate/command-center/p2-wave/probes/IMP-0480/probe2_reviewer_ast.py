#!/usr/bin/env python3
"""IMP-0480 probe 2: AST typed-handoff + three novel reviewer injections.

Both-states on the auditor: honest consume.py is clean; a mutant that passes
payload into apply_policy FIRES. Novel injections the catalog has never seen
must be identical on the boundary and must move the naive consumer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from artifact_boundary.ast_guard import (  # noqa: E402
    audit_consume_module,
    audit_source,
)
from artifact_boundary.consume import behavior_of  # noqa: E402
from artifact_boundary.corpus import novel_pairs  # noqa: E402
from artifact_boundary.naive import naive_consume  # noqa: E402
from artifact_boundary.policy import TrustedPolicy  # noqa: E402

MUTANT = """
def consume_stage(artifacts, policy):
    payload = artifacts[0].body
    return apply_policy(payload)
"""

HONEST = """
def consume_stage(artifacts, policy):
    wrapped = [wrap_artifact(item) for item in artifacts]
    facts = []
    for env in wrapped:
        facts.extend(extract_facts(unwrap_payload(env)))
    return apply_policy(policy)
"""


def main() -> int:
    consume_path = REPO / "tools" / "artifact_boundary" / "consume.py"
    disk = audit_consume_module(consume_path)
    mutant_findings = audit_source(MUTANT, label="in-memory-mutant")
    honest_mem = audit_source(HONEST, label="in-memory-honest")
    mutant_fires = any(
        f["id"] == "payload-reaches-apply_policy" for f in mutant_findings
    )
    honest_silent = honest_mem == []
    consume_src = consume_path.read_text(encoding="utf-8")
    no_fs = all(
        token not in consume_src
        for token in ("Path.open", "read_text", "/etc/", ".ssh")
    )

    policy = TrustedPolicy()
    novel_rows = []
    novel_held = True
    novel_naive = True
    for inj_id, clean, dirty in novel_pairs():
        same = behavior_of(clean, policy) == behavior_of(dirty, policy)
        naive_changed = naive_consume(clean, policy) != naive_consume(dirty, policy)
        novel_held = novel_held and same
        novel_naive = novel_naive and naive_changed
        novel_rows.append(
            {
                "id": inj_id,
                "boundary_identical": same,
                "naive_diverged": naive_changed,
            }
        )

    passed = (
        disk["clean"]
        and disk["wraps"]
        and disk["extracts"]
        and disk["applies_policy"]
        and mutant_fires
        and honest_silent
        and novel_held
        and novel_naive
        and no_fs
        and len(novel_rows) == 3
    )
    report = {
        "probe": "probe2-reviewer-ast-novel",
        "unit_id": "IMP-0480",
        "consume_path": str(consume_path.relative_to(REPO)),
        "disk_audit": disk,
        "mutant_fires": mutant_fires,
        "mutant_findings": mutant_findings,
        "honest_memory_silent": honest_silent,
        "no_filesystem_credential_api": no_fs,
        "novel_rows": novel_rows,
        "both_states": {
            "good_silent": disk["clean"] and honest_silent,
            "bad_fires": mutant_fires,
        },
        "pass": passed,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not passed:
        print("FAILED:IMP-0480-probe2 reviewer AST/novel")
        return 1
    print("SUCCESS:IMP-0480-probe2 AST typed-handoff; three novel injections held")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
