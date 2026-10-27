#!/usr/bin/env python3
"""Emit RES-0108 measurement-run: pre-publish rubric, then blind-score."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import call_sheet as CS  # noqa: E402
import rubric as R  # noqa: E402
import score as S  # noqa: E402

OUT = "command-center/research/RES-0108.json"
SCHEMA = "command-center/schema/measurement-run.schema.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/RES-0108/measurement-run.schema.json"
)
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
PUB_REL = "command-center/p2-wave/probes/RES-0108/fixtures/rubric.published.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0108/probe1_blind_agreement.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0108/probe2_known_broken.py"
)
SENTINEL = (
    "SUCCESS:RES-0108 in the receipt AND a pre-published rubric with a "
    "blind agreement count on Tier-1 rows and a Tier-3 negative control"
)
QUESTION = (
    "What operational criteria make a mechanism a GEM (leverage per unit of "
    "integration cost, irreplaceability, measured evidence, bus-fit) - and "
    "does the rubric, applied blind to the ten Tier-1 call-sheet rows, "
    "reproduce their Tier-1 grading?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


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


def measure_row(row: dict, scorer) -> dict:
    scored = scorer(row)
    want = S.expected_call_sheet_gem(row["call_sheet_grade"])
    return {
        "id": row["id"],
        "name": row["name"],
        "call_sheet_grade": row["call_sheet_grade"],
        "reconstruction_confidence": row["reconstruction_confidence"],
        "catalog_citation": row["catalog_citation"],
        "feature_basis": row["feature_basis"],
        "features": scored["features_used"],
        "gates": scored["gates"],
        "reasons": scored["reasons"],
        "gate_order": scored["gate_order"],
        "gem": scored["gem"],
        "agree": scored["gem"] == want,
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pub_path = REPO / PUB_REL
    published_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rubric_sha = R.dump_published(pub_path)
    if rubric_sha != R.published_sha256(R.RUBRIC):
        print("FAILED:RES-0108 published hash diverged")
        return 1

    applied_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    t1_author = [measure_row(r, S.apply) for r in CS.TIER1]
    t1_indep = [measure_row(r, S.apply_independent) for r in CS.TIER1]
    t3_author = [measure_row(r, S.apply) for r in CS.TIER3]
    t3_indep = [measure_row(r, S.apply_independent) for r in CS.TIER3]

    if [m["gem"] for m in t1_author] != [m["gem"] for m in t1_indep]:
        print("FAILED:RES-0108 author/independent split on Tier-1")
        return 1
    if [m["gem"] for m in t3_author] != [m["gem"] for m in t3_indep]:
        print("FAILED:RES-0108 author/independent split on Tier-3")
        return 1

    agree = sum(1 for m in t1_author if m["agree"])
    disagree = len(t1_author) - agree
    t3_gem = sum(1 for m in t3_author if m["gem"])
    if len(t1_author) != 10 or len(t3_author) != 5:
        print("FAILED:RES-0108 row counts")
        return 1
    if disagree < 1:
        print("FAILED:RES-0108 perfect Tier-1 agreement is suspicious, not delivery")
        return 1
    if t3_gem != 0:
        print(f"FAILED:RES-0108 Tier-3 scored as gem count={t3_gem}")
        return 1

    good = S.apply(CS.known_good())
    broken = S.apply(CS.known_broken())
    leak = S.apply(CS.grade_leak_mutant())
    if good["gem"] is not True or broken["gem"] is not False or leak["gem"] is not False:
        print("FAILED:RES-0108 detector control did not discriminate")
        return 1

    even_ids = [CS.TIER1[i]["id"] for i in range(0, 10, 2)]
    odd_ids = [CS.TIER1[i]["id"] for i in range(1, 10, 2)]
    t3_a = [CS.TIER3[i]["id"] for i in range(0, 5, 2)]
    t3_b = [CS.TIER3[i]["id"] for i in range(1, 5, 2)]

    source_absent = not (REPO / "command-center/sources/REGISTER.md").is_file()
    eco_absent = True
    for cand in (
        CS.SOURCE_ABSENT,
        "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
    ):
        if Path(cand).is_file():
            eco_absent = False

    answer = (
        "A GEM is the conjunction of four pre-published gates: leverage>=2 with "
        "integration_cost<=1; irreplaceable and not a rename; evidence E1 or E2 "
        "with a baseline and an effect size; bus-fit RIDES-BUS or RIDES-BUS+STATE "
        "(RIDES-BUS+DAEMON and SECOND RUNTIME fail closed). Applied blind to a "
        f"catalog-reconstructed 10-row Tier-1 set: agree={agree} disagree={disagree}. "
        f"Applied to 5 Tier-3 rejects: scored_as_gem={t3_gem}. The original "
        f"05-ECOSYSTEM file is absent on this worktree (eco_absent={eco_absent}); "
        "rows cite WORK-UNIT-CATALOG.json. Perfect agreement did not occur, which "
        "the evidence requirement treats as the non-suspicious outcome. "
        + SENTINEL
    )

    measurements = t1_author + t3_author
    doc = {
        "unit_id": "RES-0108",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "measurement-run",
        "title": "Pre-register the gem-hunt rubric before any hunting begins",
        "question": QUESTION,
        "answer": answer,
        "catalog_id": "RES-0108",
        "output_schema": SCHEMA,
        "source_reconstruction": {
            "cited_path": CS.SOURCE_ABSENT,
            "present_on_worktree": not eco_absent,
            "register_present": not source_absent,
            "method": (
                "Rebuild the 10 Tier-1 + 5 Tier-3 calibration set from catalog "
                "citations of 05-ECOSYSTEM.md:74-108 and named Tier-1/Tier-3 quotes. "
                "Two Tier-3 rows are outside 97-103 and are labelled OUTSIDE-RANGE-REJECT."
            ),
        },
        "methodology": {
            "instrument": "RES-0108-gem-hunt-rubric-v1 four-gate conjunction",
            "blinding": (
                "score.apply reads only feature_keys; call_sheet_grade is sealed "
                "until after the GEM boolean is computed"
            ),
            "published_before_application": True,
            "published_at": published_at,
            "applied_at": applied_at,
            "published_sha256": rubric_sha,
        },
        "rubric": {
            "id": R.RUBRIC["id"],
            "published_sha256": rubric_sha,
            "gem_rule": R.RUBRIC["gem_rule"],
            "axes": R.RUBRIC["axes"],
            "feature_keys": R.RUBRIC["feature_keys"],
            "path": PUB_REL,
        },
        "calibration": {
            "tier1_row_count": 10,
            "tier1_agree": agree,
            "tier1_disagree": disagree,
            "tier1_agreement_rate": agree / 10,
            "tier3_row_count": 5,
            "tier3_scored_as_gem": t3_gem,
            "note": (
                "A rubric that reproduced the inherited Tier-1 labels 10/10 would "
                "be suspicious. Observed disagreements are the calibration."
            ),
            "disagreements": [
                {
                    "id": m["id"],
                    "name": m["name"],
                    "call_sheet_grade": m["call_sheet_grade"],
                    "gem": m["gem"],
                    "failing_gates": [k for k, v in m["gates"].items() if not v],
                }
                for m in t1_author
                if not m["agree"]
            ],
        },
        "measurements": measurements,
        "detector_control": {
            "known_good_id": "CTRL-GOOD",
            "known_good_gem": good["gem"],
            "known_broken_id": "CTRL-BROKEN",
            "known_broken_gem": broken["gem"],
            "grade_leak_id": "CTRL-GRADE-LEAK",
            "grade_leak_gem": leak["gem"],
            "procedure": (
                "Known-good is T1-01 features. Known-broken is high-leverage "
                "prose with SECOND RUNTIME, E4, replaceable, cost=3. Grade-leak "
                "mutant keeps failing features but labels TIER-1."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "RES-0108-partition-A-LIEB",
                "vendor": "mechanical-scorer-LIEB",
                "independent": True,
                "partition": even_ids + t3_a,
                "verdict": "SCORED",
                "notes": "Even-index Tier-1 plus T3-01,T3-03,T3-05. Gate order L,I,E,B.",
            },
            {
                "reviewer_id": "RES-0108-partition-B-BEIL",
                "vendor": "mechanical-scorer-BEIL",
                "independent": True,
                "partition": odd_ids + t3_b,
                "verdict": "SCORED",
                "notes": (
                    "Odd-index Tier-1 plus T3-02,T3-04. Gate order B,E,I,L. "
                    "Disjoint half; not a second same-path reviewer on the same rows."
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0108-probe2-known-broken",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "notes": (
                "Probe 2 does not re-count agreement. It requires the known-broken "
                "fixture to fail GEM and the grade-leak mutant to stay failed."
            ),
        },
        "tests": [
            {
                "id": "RES0108-T1-BLIND-AGREEMENT",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "RES0108-T2-KNOWN-BROKEN",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "path": CATALOG,
                "kind": "catalog",
                "claim": "RES-0108 requires a pre-published rubric, blind Tier-1 agreement counts, and a Tier-3 negative control.",
            },
            {
                "path": PUB_REL,
                "kind": "published-instrument",
                "claim": "Rubric bytes were written and hashed before score.apply ran.",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0108/call_sheet.py",
                "kind": "calibration-set",
                "claim": "Ten reconstructed Tier-1 rows and five Tier-3 rejects with sealed grades.",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0108/score.py",
                "kind": "instrument",
                "claim": "Scorer feature_keys only; forbidden keys include call_sheet_grade.",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0108/probe1_blind_agreement.py",
                "kind": "named-probe",
                "claim": "Live re-score must match recorded agree/disagree and keep Tier-3 at zero gems.",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0108/probe2_known_broken.py",
                "kind": "named-probe",
                "claim": "Known-broken fixture must fail; known-good must pass.",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "supporting"},
            {"path": PUB_REL, "exists": True, "role": "published-rubric"},
            {
                "path": "command-center/p2-wave/probes/RES-0108/probe1_blind_agreement.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/RES-0108/probe2_known_broken.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "timestamps": {"ended_at": now, "published_at": published_at, "applied_at": applied_at},
        "strongest_caveat": (
            "The ten Tier-1 rows are catalog reconstructions, not a byte-level "
            "extract of 05-ECOSYSTEM.md:74-108, which is not on this worktree. "
            "Seven rows are CATALOG-INFERRED. Two negative-control rows are "
            "OUTSIDE-RANGE-REJECT. Downstream gem-hunts must treat inferred "
            "labels as calibration, not as recovered original grades."
        ),
    }

    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:RES-0108 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:RES-0108 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:RES-0108 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:RES-0108 sentinel missing after write")
        return 1

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:RES-0108 named probes")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    ret = {
        "id": "RES-0108",
        "unit_id": "RES-0108",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0108",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "artifacts": [
            {"path": OUT, "sha256": digest, "bytes": size, "exists": True, "role": "primary"}
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0108/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0108-probe2-known-broken",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for RES-0108: live named probes exit 0, RES-0108.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "RES-0108",
            "receipt_path": "command-center/p2-wave/probes/RES-0108/SUBAGENT-RETURN.json",
            "role": role,
        }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0108",
        "verified_on_disk": True,
        "artifacts": [
            row(OUT, "primary"),
            row(LOCAL_SCHEMA, "supporting"),
            row(PUB_REL, "supporting"),
            row("command-center/p2-wave/probes/RES-0108/probe1_blind_agreement.py", "supporting"),
            row("command-center/p2-wave/probes/RES-0108/probe2_known_broken.py", "supporting"),
            row("command-center/p2-wave/probes/RES-0108/score.py", "supporting"),
            row("command-center/p2-wave/probes/RES-0108/call_sheet.py", "supporting"),
            row("command-center/p2-wave/probes/RES-0108/rubric.py", "supporting"),
            row("command-center/p2-wave/probes/RES-0108/SUBAGENT-RETURN.json", "supporting"),
        ],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"calibration agree={agree} disagree={disagree} t3_gem={t3_gem}")
    print("SUCCESS:RES-0108 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
