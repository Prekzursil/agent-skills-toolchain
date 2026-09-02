#!/usr/bin/env python3
"""Named probe 2: both-states, reviewer class, synthetic-secret honesty, receipt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RECEIPT_REL = "command-center/receipts/IMP-0119.json"


def repo_root() -> Path:
    cur = HERE
    for _ in range(8):
        if (cur / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return cur
        cur = cur.parent
    raise SystemExit("FAILED:IMP-0119-probe2 repo root not found")


REPO = repo_root()
sys.path.insert(0, str(REPO / "tools"))

from marketplace.corpus import FIXTURES, load_corpus, materialize  # noqa: E402
from marketplace.gates import (  # noqa: E402
    IMPLEMENTER_GATE_IDS,
    Package,
    SYNTHETIC_CANARY,
    canonical_payload,
    compute_digest,
    coverage_matrix,
    findings_contain_canary_body,
    run_all_gates,
    sign_payload,
)


def main() -> int:
    art = REPO / RECEIPT_REL
    if not art.is_file() or art.stat().st_size < 200:
        print("FAILED:IMP-0119-probe2 receipt missing")
        return 1
    text = art.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0119" and doc.get("id") != "IMP-0119":
        print("FAILED:IMP-0119-probe2 unit_id", doc.get("unit_id") or doc.get("id"))
        return 1
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0119-probe2 self-declared {st}")
        return 1
    if "SUCCESS:IMP-0119" not in text:
        print("FAILED:IMP-0119-probe2 sentinel absent")
        return 1

    materialize()
    packages = load_corpus()
    goods = [p for p in packages if p.kind == "good"]
    signed = next(p for p in packages if p.fixture_id == "signed")
    clean = coverage_matrix(goods)["signed"]
    if clean:
        print(f"FAILED:IMP-0119-probe2 good state dirty {clean}")
        return 1

    planted_files = dict(signed.files)
    planted_files["payload/canary.txt"] = (SYNTHETIC_CANARY + "\n").encode("utf-8")
    planted = Package(
        fixture_id="signed-planted",
        kind="bad",
        expected_gate="secret",
        root=signed.root,
        name=signed.name,
        version=signed.version,
        license=signed.license,
        permissions=list(signed.permissions),
        dependencies=dict(signed.dependencies),
        entries=list(signed.entries) + ["payload/canary.txt"],
        files=planted_files,
        digest_declared=signed.digest_declared,
        signature=dict(signed.signature),
        extra=dict(signed.extra),
    )
    planted.digest_declared = compute_digest(planted)
    planted.signature = sign_payload(canonical_payload(planted))
    planted_fired = coverage_matrix([planted])["signed-planted"]
    if planted_fired != ["secret"]:
        print(f"FAILED:IMP-0119-probe2 planted fired {planted_fired}")
        return 1

    reviewer = next(p for p in packages if p.fixture_id == "autoload-agent-config")
    implementer_hits = coverage_matrix([reviewer], gate_ids=IMPLEMENTER_GATE_IDS)[
        "autoload-agent-config"
    ]
    if implementer_hits:
        print(f"FAILED:IMP-0119-probe2 reviewer class already caught {implementer_hits}")
        return 1
    reviewer_fired = coverage_matrix([reviewer])["autoload-agent-config"]
    if reviewer_fired != ["autoload_agent"]:
        print(f"FAILED:IMP-0119-probe2 reviewer gate {reviewer_fired}")
        return 1

    doc_path = FIXTURES / "SYNTHETIC-SECRET.md"
    secret_doc = doc_path.read_text(encoding="utf-8")
    if SYNTHETIC_CANARY not in secret_doc:
        print("FAILED:IMP-0119-probe2 canary undocumented")
        return 1
    if "not a credential" not in secret_doc.lower():
        print("FAILED:IMP-0119-probe2 canary not declared non-credential")
        return 1
    secret_pkg = next(p for p in packages if p.fixture_id == "synthetic-secret")
    secret_findings = run_all_gates(secret_pkg, [secret_pkg])["secret"]
    if not secret_findings:
        print("FAILED:IMP-0119-probe2 secret gate silent")
        return 1
    if findings_contain_canary_body(secret_findings):
        print("FAILED:IMP-0119-probe2 finding echoed canary body")
        return 1

    payload = {
        "probe": "probe2-both-states",
        "unit_id": "IMP-0119",
        "good_state_clean": True,
        "bad_state_secret_only": True,
        "reviewer_class": "autoload-agent-config",
        "reviewer_missed_by_implementer_gates": True,
        "reviewer_caught_by_new_gate": True,
        "synthetic_secret_documented": True,
        "finding_omits_canary_body": True,
        "receipt_sentinel": True,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "clean_signed=True planted_secret_only=True "
        "reviewer_new_class=True canary_documented=True"
    )
    print("SUCCESS:IMP-0119-probe2 both-states reviewer secret-honesty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
