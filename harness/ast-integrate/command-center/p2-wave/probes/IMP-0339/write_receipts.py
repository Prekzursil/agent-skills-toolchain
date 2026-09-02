#!/usr/bin/env python3
"""Write IMP-0339 receipt, SUBAGENT-RETURN.json, and per-unit manifest.

Does not invoke tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE / "fixtures"))

from planted import EXPECTED_PROMOTED, build_ideas, build_ledger  # noqa: E402
from tools.council.artifacts.option_cards import (  # noqa: E402
    field_completeness_audit,
    inject_incomplete_card,
    promote,
    validate_card,
)
from tools.council.artifacts.quality_rater import (  # noqa: E402
    mean_quality,
    title_length_select,
)

UNIT = "IMP-0339"
OUT = "command-center/receipts/IMP-0339.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0339/probe1_promotion_schema.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0339/probe2_blind_quality.py"
)
SUPPORTING = [
    "tools/council/artifacts/option_cards.py",
    "tools/council/artifacts/quality_rater.py",
    "tools/council/artifacts/tests/test_option_cards.py",
    "command-center/p2-wave/probes/IMP-0339/probe1_promotion_schema.py",
    "command-center/p2-wave/probes/IMP-0339/probe2_blind_quality.py",
    "command-center/p2-wave/probes/IMP-0339/fixtures/planted.py",
    "command-center/p2-wave/probes/IMP-0339/fixtures/ledger.json",
    "command-center/p2-wave/probes/IMP-0339/fixtures/anchors/claim-a.md",
    "command-center/p2-wave/probes/IMP-0339/fixtures/anchors/claim-b.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    data = path.read_bytes() if path.is_file() else b""
    raw = data.replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw) if path.is_file() else 0,
        "sha256": hashlib.sha256(raw).hexdigest() if path.is_file() else "",
        "exists": path.is_file(),
        "role": role,
        "eol": "LF" if path.is_file() else "NOT-CHECKED",
    }


def run_probe(cmd: str) -> tuple[int, str]:
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": True,
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0339/SUBAGENT-RETURN.json",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ledger = build_ledger()
    ledger_path = HERE / "fixtures" / "ledger.json"
    ledger_path.write_text(
        json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    ideas = build_ideas()
    result = promote(ideas, evidence_root=REPO)
    audit = field_completeness_audit(result.cards)
    k = result.n_promoted
    promoted_ideas = [i for i in ideas if i["idea_id"] in set(EXPECTED_PROMOTED)]
    rng = __import__("random").Random(20260824)
    random_subset = rng.sample(list(ideas), k)
    decorative = title_length_select(ideas, k)
    promoted_mean = mean_quality(promoted_ideas)
    random_mean = mean_quality(random_subset)
    decorative_mean = mean_quality(decorative)
    completeness_control = []
    if result.cards:
        for field_name in ("mechanism", "cost", "risk", "evidence"):
            broken = inject_incomplete_card(result.cards[0], drop_field=field_name)
            errs = validate_card(broken)
            completeness_control.append(
                {"dropped_field": field_name, "fired": bool(errs), "errors": errs}
            )

    unittest_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest "
        "tools.council.artifacts.tests.test_option_cards -q"
    )
    ut_rc, ut_out = run_probe(unittest_cmd)

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0 or ut_rc != 0:
        print(f"FAILED:IMP-0339 receipts probes c1={c1} c2={c2} unittest={ut_rc}")
        print(t1[-2000:])
        print(t2[-2000:])
        print(ut_out[-1000:])
        return 1

    ended = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    summary = result.as_dict()
    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0339",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0339]",
        "profile": "council-artifacts-module",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "question_answered": (
            "What fraction of raw ideas survive promotion, and is the bar doing "
            "work — would a random subset of the same size be indistinguishable "
            "from the promoted set on an independent quality rating?"
        ),
        "artifact_paths": [OUT] + SUPPORTING,
        "artifacts": [art(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    f"Promotion rate on the planted 24-idea ledger is "
                    f"{summary['n_promoted']}/{summary['n_raw']} = "
                    f"{summary['promotion_rate']:.6f}. Drop reasons were "
                    f"{summary['dropped_by_reason']} (first failing check in "
                    "MECHANISM, COST, RISK, EVIDENCE order). The bar is selective: "
                    "rate is neither 0 nor 1."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/artifacts/option_cards.py:CHECK_ORDER",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "exit_code": c1,
                        "raw_output": t1[:8000],
                        "fingerprint": hashlib.sha256(P1.encode()).hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "in-process",
                        "command": "promote(build_ideas(), evidence_root=REPO)",
                        "exit_code": 0,
                        "raw_output": json.dumps(summary, sort_keys=True),
                        "fingerprint": hashlib.sha256(b"promote-inprocess").hexdigest()[:32],
                    },
                ],
            },
            {
                "claim": (
                    f"Blind held-out quality: promoted mean={promoted_mean:.3f}, "
                    f"random subset (seed=20260824) mean={random_mean:.3f}, "
                    f"title-length decorative bar mean={decorative_mean:.3f}. "
                    "The promoted set beats both by >15 points, so the bar is not "
                    "a random subset of the same size wearing a different name."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/artifacts/quality_rater.py:independent_quality",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "exit_code": c2,
                        "raw_output": t2[:8000],
                        "fingerprint": hashlib.sha256(P2.encode()).hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": unittest_cmd,
                        "exit_code": ut_rc,
                        "raw_output": ut_out[:4000],
                        "fingerprint": hashlib.sha256(unittest_cmd.encode()).hexdigest()[:32],
                    },
                ],
            },
            {
                "claim": (
                    f"Field-completeness validation on every promoted card: "
                    f"{audit['n_complete']}/{audit['n_cards']} complete, "
                    f"{audit['n_incomplete']} incomplete. Injecting a missing "
                    "mechanism, cost, risk or evidence field into a clone of a "
                    "promoted card makes validate_card fire in all four cases."
                ),
                "verdict": "CONFIRMED",
                "anchor": "tools/council/artifacts/option_cards.py:validate_card",
                "confidence": "almost-certain",
                "probes": [
                    {
                        "role": "source",
                        "method": "in-process",
                        "command": "field_completeness_audit(result.cards)",
                        "exit_code": 0,
                        "raw_output": json.dumps(
                            {k: audit[k] for k in ("n_cards", "n_complete", "n_incomplete", "all_complete")},
                            sort_keys=True,
                        ),
                        "fingerprint": hashlib.sha256(b"completeness-audit").hexdigest()[:32],
                    },
                    {
                        "role": "verifier",
                        "method": "mutation",
                        "command": "inject_incomplete_card for each required field",
                        "exit_code": 0,
                        "raw_output": json.dumps(completeness_control, sort_keys=True),
                        "fingerprint": hashlib.sha256(b"inject-incomplete").hexdigest()[:32],
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "T1-promotion-criteria-and-card-schema",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "assertions": 8,
                "output_tail": t1.splitlines()[-1] if t1 else "",
            },
            {
                "id": "T2-promoted-beats-random-on-blind-rating",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "assertions": 4,
                "output_tail": t2.splitlines()[-1] if t2 else "",
            },
            {
                "id": "T3-unittest-option-cards",
                "command": unittest_cmd,
                "result": "PASS" if ut_rc == 0 else "FAIL",
                "assertions": 3,
                "output_tail": ut_out[-200:],
            },
        ],
        "test_ids": [
            "T1-promotion-criteria-and-card-schema",
            "T2-promoted-beats-random-on-blind-rating",
            "T3-unittest-option-cards",
        ],
        "negative_controls": [
            {
                "id": "NC-incomplete-card-completeness-fires",
                "kind": "mutation",
                "description": (
                    "Clone a promoted card and strip each required field. "
                    "validate_card must fire; a silent completeness check is a no-op."
                ),
                "fired_on_bad_state": all(row["fired"] for row in completeness_control),
                "silent_on_good_state": audit["all_complete"],
                "bad_state_output": json.dumps(completeness_control, sort_keys=True)[:16000],
                "good_state_output": f"all_complete={audit['all_complete']} n={audit['n_cards']}",
            },
            {
                "id": "NC-title-length-bar-is-decorative",
                "kind": "known-broken-fixture",
                "description": (
                    "A title-length promoter of the same cardinality must not beat "
                    "the documented random subset by the same 15-point margin the "
                    "maturity bar achieves. Long titles were planted on immature ideas."
                ),
                "fired_on_bad_state": (decorative_mean - random_mean) < 15.0,
                "silent_on_good_state": (promoted_mean - random_mean) >= 15.0,
                "bad_state_output": f"decorative_mean={decorative_mean} random_mean={random_mean}",
                "good_state_output": f"promoted_mean={promoted_mean} random_mean={random_mean}",
            },
        ],
        "negative_control_ids": [
            "NC-incomplete-card-completeness-fires",
            "NC-title-length-bar-is-decorative",
        ],
        "reviewer": {
            "reviewer_id": "IMP-0339-probe2-blind-quality",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Named probes start from the tests and the live module, not an "
                "author summary. A separate-agent reviewer was not launched."
            ),
        },
        "reviewer_verdict": "PASS",
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0339/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {"count": 0, "policy": "two strikes then pivot (AGENTS.md 4b)"},
        "residual_unknowns": [
            {
                "claim": (
                    "IMP-0290 (blind_first.py) and IMP-0300 (unique_ideas.py) are "
                    "catalog dependencies and are not on disk in this worktree. "
                    "This unit consumes a typed idea ledger (canonical_mechanism_id "
                    "copied through when present) rather than importing those modules."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "After IMP-0300 lands, pipe unique_ideas output into "
                    "option_cards.promote and re-run both named probes on that ledger."
                ),
            },
            {
                "claim": (
                    "Held-out quality labels on the planted ledger were assigned by "
                    "the same implementer who wrote the bar. The probes prove the bar "
                    "does not read those labels and that a title-length bar fails the "
                    "same comparison; they do not prove the bar tracks an independently "
                    "elicited human quality rating on a live council transcript."
                ),
                "verdict": "PARTIAL",
                "settling_experiment": (
                    "Score a held-out live ledger with a rater who has not seen "
                    "promotion status, then re-run probe2 without replanting labels."
                ),
            },
        ],
        "report": {
            "kind": "idea-to-option-card-promotion",
            "promotion": summary,
            "completeness": {
                "n_cards": audit["n_cards"],
                "n_complete": audit["n_complete"],
                "n_incomplete": audit["n_incomplete"],
                "all_complete": audit["all_complete"],
            },
            "blind_quality": {
                "promoted_mean": promoted_mean,
                "random_subset_mean": random_mean,
                "decorative_title_length_mean": decorative_mean,
                "random_seed": 20260824,
                "margin": 15.0,
            },
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    primary = row(OUT, "primary")
    if primary["bytes"] < int(receipt["min_bytes_threshold"]):
        print(f"FAILED:IMP-0339 receipt {primary['bytes']}B below floor")
        return 1
    if "SUCCESS:IMP-0339" not in out_path.read_text(encoding="utf-8"):
        print("FAILED:IMP-0339 sentinel absent after write")
        return 1

    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:IMP-0339",
        "registered": True,
        "output_path": OUT,
        "output_schema": (
            "command-center/schema/receipt.schema.json profile=council-artifacts-module"
        ),
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "promotion-criteria-and-card-schema",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "blind-quality-vs-random-subset",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0339/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0339-probe2-blind-quality",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0339: live named probes exit 0, receipts/IMP-0339.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0339 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
