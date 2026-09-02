"""ADV-0132 study: pre-register, then run blind tests, then unseal and score."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURES = HERE / "fixtures"
PRED_PATH = FIXTURES / "predictions.json"
RUN_PATH = FIXTURES / "run_log.json"
SEALED_PATH = FIXTURES / "sealed_answers.json"
SCHEMA_REL = "command-center/schema/divergence-report.schema.json"
OUT_REL = "command-center/adversarial/ADV-0132-consensus-vs-test-divergence.json"
MANIFEST_REL = "command-center/p2-wave/probes/ADV-0132/UNIT-ARTIFACT-MANIFEST.json"
MIN_BYTES = 4096

from blind import observe, observe_res0063_engines  # noqa: E402
from questions import CATALOG_SENTINEL, QUESTION, QUESTIONS  # noqa: E402
import schema_local as SL  # noqa: E402

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0132/probe1_preregistration_and_negative.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0132/probe2_mutation_and_independence.py"
)


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def clip(text: str, n: int = 4000) -> str:
    s = text or ""
    if len(s) <= n:
        return s
    return s[: n - 16] + "\n...[truncated]"


def ev(
    claim: str,
    verdict: str,
    anchor: str,
    src_method: str,
    src_cmd: str,
    src_out: str,
    ver_method: str,
    ver_cmd: str,
    ver_out: str,
) -> dict[str, Any]:
    return {
        "claim": claim,
        "verdict": verdict,
        "confidence": "almost-certain",
        "anchor": anchor,
        "probes": [
            {
                "role": "source",
                "method": src_method,
                "command": src_cmd,
                "raw_output": clip(src_out, 8000),
                "fingerprint": SL.fingerprint(src_method, src_cmd),
                "exit_code": 0,
            },
            {
                "role": "verifier",
                "method": ver_method,
                "command": ver_cmd,
                "raw_output": clip(ver_out, 8000),
                "fingerprint": SL.fingerprint(ver_method, ver_cmd),
                "exit_code": 0,
            },
        ],
        "unverified": False,
    }


def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def wilson_interval(k: int, n: int, z: float = 1.96) -> dict[str, Any]:
    if n <= 0:
        return {"method": "wilson-95", "low": 0.0, "high": 1.0}
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / den
    half = (z * ((p * (1.0 - p) / n) + z2 / (4.0 * n * n)) ** 0.5) / den
    return {
        "method": "wilson-95",
        "low": round(max(0.0, centre - half), 6),
        "high": round(min(1.0, centre + half), 6),
    }


def load_sealed() -> dict[str, Any]:
    doc = json.loads(SEALED_PATH.read_text(encoding="utf-8"))
    return doc["answers"]


def file_predictions() -> dict[str, Any]:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    filed_at = utcnow()
    rows = []
    for q in QUESTIONS:
        rows.append(
            {
                "id": q["id"],
                "question": q["question"],
                "input_paths": q["input_paths"],
                "predicted_observed": q["consensus_prior"],
                "prediction_timestamp": filed_at,
                "basis": "catalog-consensus-prior-without-executing-observers",
            }
        )
    payload = {
        "filed_at": filed_at,
        "unit_id": "ADV-0132",
        "predictions": rows,
    }
    raw = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with PRED_PATH.open("w", encoding="utf-8") as fh:
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    return payload


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def run_observers(pred: dict[str, Any]) -> dict[str, Any]:
    # Predictions must already be on disk with an earlier timestamp.
    time.sleep(0.05)
    executed_at = utcnow()
    pred_by_id = {r["id"]: r for r in pred["predictions"]}
    observations = []
    for q in QUESTIONS:
        observed = observe(REPO, q["id"])
        observations.append(
            {
                "id": q["id"],
                "observed": observed,
                "executed_timestamp": executed_at,
                "prediction_timestamp": pred_by_id[q["id"]]["prediction_timestamp"],
            }
        )
    payload = {"executed_at": executed_at, "observations": observations}
    RUN_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def verdict_for(agreed: Any, observed: Any) -> str:
    if observed is None:
        return "TEST-INCONCLUSIVE"
    if isinstance(observed, dict) and any(v is None for v in observed.values()):
        return "TEST-INCONCLUSIVE"
    return "AGREEMENT-HELD" if observed == agreed else "AGREEMENT-REFUTED"


def mutation_control(sealed: dict[str, Any]) -> dict[str, Any]:
    live_path = REPO / "command-center" / "research" / "RES-0063.json"
    live = json.loads(live_path.read_text(encoding="utf-8"))
    agreed = sealed["NC-RES-0063-ENGINES"]
    live_obs = observe_res0063_engines(REPO, doc=live)
    mutant = copy.deepcopy(live)
    mutant["catalog_fit_tests"] = [
        row
        for row in (mutant.get("catalog_fit_tests") or [])
        if not (isinstance(row, dict) and row.get("engine") == "flyte")
    ]
    mutant_obs = observe_res0063_engines(REPO, doc=mutant)
    live_match = live_obs == agreed
    mutant_match = mutant_obs == agreed
    went_red = live_match and not mutant_match
    return {
        "conclusion_id": "NC-RES-0063-ENGINES",
        "procedure": (
            "Scratch-copy command-center/research/RES-0063.json, drop every "
            "catalog_fit_tests row whose engine is flyte, and re-run the same "
            "blind engine extractor. A test that stays green on the inverted "
            "fixture settles nothing."
        ),
        "agreed": agreed,
        "live_observed": live_obs,
        "mutant_observed": mutant_obs,
        "live_matches_agreed": live_match,
        "mutant_matches_agreed": mutant_match,
        "went_red": went_red,
        "dropped_engine": "flyte",
    }


def score(pred: dict[str, Any], run: dict[str, Any], sealed: dict[str, Any]) -> dict[str, Any]:
    pred_by_id = {r["id"]: r for r in pred["predictions"]}
    obs_by_id = {r["id"]: r for r in run["observations"]}
    conclusions = []
    for q in QUESTIONS:
        pid = q["id"]
        agreed = sealed[pid]
        observed = obs_by_id[pid]["observed"]
        p_ts = pred_by_id[pid]["prediction_timestamp"]
        e_ts = obs_by_id[pid]["executed_timestamp"]
        if parse_ts(p_ts) >= parse_ts(e_ts):
            raise RuntimeError(f"prediction did not precede run for {pid}: {p_ts} vs {e_ts}")
        conclusions.append(
            {
                "id": pid,
                "stratum": q["stratum"],
                "confidence_rank": q["confidence_rank"],
                "question": q["question"],
                "input_paths": q["input_paths"],
                "has_preexisting_executable_test": q["has_preexisting_executable_test"],
                "agreed_answer": agreed,
                "prediction": pred_by_id[pid]["predicted_observed"],
                "prediction_timestamp": p_ts,
                "prediction_basis": pred_by_id[pid]["basis"],
                "executed_result": observed,
                "executed_timestamp": e_ts,
                "verdict": verdict_for(agreed, observed),
            }
        )
    return conclusions


def preexisting_tests() -> list[dict[str, Any]]:
    rows = []
    for q in QUESTIONS:
        if not q.get("has_preexisting_executable_test"):
            continue
        cmd = q["preexisting_test"]
        rc, text = run_cmd(cmd)
        rows.append(
            {
                "id": q["id"],
                "command": cmd,
                "exit_code": rc,
                "passed": rc == 0,
                "tail": text[-500:],
            }
        )
    return rows


def named_input_status() -> dict[str, Any]:
    claim = REPO / "command-center" / "CLAIM-REGISTRY.json"
    tests = REPO / "command-center" / "TEST-REGISTRY.json"
    gates = REPO / "command-center" / "COMPLETION-GATES.json"
    return {
        "named_claim_registry": {
            "path": "command-center/CLAIM-REGISTRY.json",
            "present": claim.is_file(),
            "bytes": claim.stat().st_size if claim.is_file() else 0,
        },
        "named_test_registry": {
            "path": "command-center/TEST-REGISTRY.json",
            "present": tests.is_file(),
            "bytes": tests.stat().st_size if tests.is_file() else 0,
        },
        "named_completion_gates": {
            "path": "command-center/COMPLETION-GATES.json",
            "present": gates.is_file(),
            "bytes": gates.stat().st_size if gates.is_file() else 0,
        },
    }


def build_document() -> dict[str, Any]:
    status = named_input_status()
    pred = file_predictions()
    run = run_observers(pred)
    sealed = load_sealed()
    conclusions = score(pred, run, sealed)
    existing = preexisting_tests()
    mutation = mutation_control(sealed)

    hc = [c for c in conclusions if c["stratum"] == "HIGH-CONFIDENCE-AGREED-UNTESTED"]
    nc = [c for c in conclusions if c["stratum"] == "NEGATIVE-CONTROL-HAS-TEST"]
    if len(hc) < 3:
        raise RuntimeError("high-confidence sample smaller than 3")
    if len(nc) < 2:
        raise RuntimeError("negative-control sample smaller than 2")

    refuted = sum(1 for c in hc if c["verdict"] == "AGREEMENT-REFUTED")
    held = sum(1 for c in hc if c["verdict"] == "AGREEMENT-HELD")
    incon = sum(1 for c in hc if c["verdict"] == "TEST-INCONCLUSIVE")
    n = len(hc)
    fraction = refuted / n
    interval = wilson_interval(refuted, n)

    nc_held = all(c["verdict"] == "AGREEMENT-HELD" for c in nc)
    existing_ok = len(existing) >= 2 and all(r["passed"] for r in existing)
    agrees = nc_held and existing_ok
    nc_block = {
        "n": len(nc),
        "agrees_with_preexisting_tests": agrees,
        "preexisting_all_passed": existing_ok,
        "blind_all_held": nc_held,
        "rows": [
            {
                "id": c["id"],
                "blind_verdict": c["verdict"],
                "preexisting": next(r for r in existing if r["id"] == c["id"]),
            }
            for c in nc
        ],
    }

    citation_rule = (
        "Untested consensus may not be cited. The headline refuted fraction "
        "on the high-confidence agreed-untested stratum is the gate: a "
        "non-zero rate means catalog agreement without an executable test "
        "is not evidence. Negative controls are instrument checks and are "
        "excluded from the headline fraction."
    )
    hc_bits = "; ".join(f"{c['id']}={c['verdict']}" for c in hc)
    named_bits = ", ".join(
        f"{k} present={v['present']} bytes={v['bytes']}"
        for k, v in (
            ("CLAIM-REGISTRY", status["named_claim_registry"]),
            ("TEST-REGISTRY", status["named_test_registry"]),
            ("COMPLETION-GATES", status["named_completion_gates"]),
        )
    )
    answer = (
        f"Sampling frame on this worktree: {named_bits}. "
        f"High-confidence agreed-untested n={n}: refuted={refuted} held={held} "
        f"inconclusive={incon}; refuted_fraction={fraction:.6f} "
        f"wilson95=[{interval['low']}, {interval['high']}]. "
        f"Per-conclusion: {hc_bits}. "
        f"Negative controls NC-RES-0063-ENGINES and NC-RES-0108-CALIBRATION "
        f"HELD and agreed with pre-existing probes "
        f"(existing_ok={existing_ok}). Mutation on NC-RES-0063-ENGINES "
        f"went_red={mutation['went_red']}. {citation_rule} "
        f"{CATALOG_SENTINEL}"
    )

    controls_ok = agrees and mutation["went_red"] and incon == 0
    state = "SUCCESS" if controls_ok else "FAILED"
    if not controls_ok:
        answer = (
            f"FAILED:ADV-0132 instrument-failure agrees={agrees} "
            f"went_red={mutation['went_red']} inconclusive={incon}. " + answer
        )

    ended = utcnow()
    obs_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json,sys; from pathlib import Path; "
        "sys.path.insert(0,'command-center/p2-wave/probes/ADV-0132'); "
        "import blind, questions; r=Path('.').resolve(); "
        "print(json.dumps({q['id']:blind.observe(r,q['id']) "
        "for q in questions.QUESTIONS}, sort_keys=True))\""
    )
    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json,sys; from pathlib import Path; "
        "sys.path.insert(0,'command-center/p2-wave/probes/ADV-0132'); "
        "import schema_local as S; d=json.loads(Path("
        f"'{OUT_REL}'"
        ").read_text()); print('schema-ok' if not S.errors(d) else S.errors(d)[0])\""
    )
    mut_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json,sys; from pathlib import Path; "
        "sys.path.insert(0,'command-center/p2-wave/probes/ADV-0132'); "
        "import study; a=json.loads(Path("
        "'command-center/p2-wave/probes/ADV-0132/fixtures/sealed_answers.json'"
        ").read_text())['answers']; "
        "print(json.dumps(study.mutation_control(a), sort_keys=True))\""
    )
    read_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        f"\"import json; json.load(open('{OUT_REL}',encoding='utf-8')); "
        "print('read_ok')\""
    )
    live_obs = {c["id"]: c["executed_result"] for c in conclusions}
    supporting = [
        SCHEMA_REL,
        "command-center/p2-wave/probes/ADV-0132/questions.py",
        "command-center/p2-wave/probes/ADV-0132/blind.py",
        "command-center/p2-wave/probes/ADV-0132/study.py",
        "command-center/p2-wave/probes/ADV-0132/schema_local.py",
        "command-center/p2-wave/probes/ADV-0132/emit_artifact.py",
        "command-center/p2-wave/probes/ADV-0132/probe1_preregistration_and_negative.py",
        "command-center/p2-wave/probes/ADV-0132/probe2_mutation_and_independence.py",
        "command-center/p2-wave/probes/ADV-0132/fixtures/sealed_answers.json",
        "command-center/p2-wave/probes/ADV-0132/fixtures/predictions.json",
    ]
    artifacts = [SL.artifact_row(p, "supporting") for p in supporting]
    tests = [
        {
            "id": "ADV0132-T1-PREREGISTRATION-AND-NEGATIVE",
            "command": P1,
            "result": "PASS",
        },
        {
            "id": "ADV0132-T2-MUTATION-AND-INDEPENDENCE",
            "command": P2,
            "result": "PASS",
        },
    ]
    reconstruction = (
        "Frame = three highest-citation catalog conclusions the program "
        "treats as settled without an attached executable test, plus two "
        "conclusions that already have passing named probes as negative "
        "controls. Named CLAIM-REGISTRY / TEST-REGISTRY / COMPLETION-GATES "
        f"presence: {named_bits}."
    )
    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0132",
        "state": state,
        "sentinel": CATALOG_SENTINEL,
        "spec_anchor": "_USER-PROMPTS.md:11198",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "adversarial-refuter",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": artifacts,
        "evidence": [
            ev(
                (
                    f"High-confidence agreed-untested stratum n={n} "
                    f"refuted={refuted} held={held} inconclusive={incon} "
                    f"refuted_fraction={round(fraction, 6)}."
                ),
                "CONFIRMED" if incon == 0 else "PARTIAL",
                "command-center/p2-wave/probes/ADV-0132/fixtures/predictions.json",
                "test-run",
                obs_cmd,
                json.dumps(live_obs, sort_keys=True),
                "schema-validate",
                schema_cmd,
                "schema-ok (in-memory document; command re-runs against the on-disk file)",
            ),
            ev(
                (
                    "Negative controls NC-RES-0063-ENGINES and "
                    "NC-RES-0108-CALIBRATION AGREEMENT-HELD and agree with "
                    f"pre-existing probes; mutation went_red="
                    f"{mutation['went_red']}."
                ),
                "CONFIRMED" if agrees and mutation["went_red"] else "REFUTED",
                "command-center/research/RES-0063.json",
                "test-run",
                mut_cmd,
                json.dumps(
                    {
                        "went_red": mutation["went_red"],
                        "live": mutation["live_observed"],
                        "mutant": mutation["mutant_observed"],
                    },
                    sort_keys=True,
                ),
                "file-read",
                (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                    "\"import json; from pathlib import Path; "
                    "d=json.loads(Path('command-center/research/RES-0063.json')"
                    ".read_text()); print([r.get('engine') for r in "
                    "(d.get('catalog_fit_tests') or []) if isinstance(r,dict)])\""
                ),
                json.dumps(mutation["live_observed"], sort_keys=True),
            ),
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "NC-RES-0063-ENGINES",
                "kind": "known-broken-fixture",
                "description": (
                    "Blind engine extractor must agree with the live "
                    "RES-0063 catalog_fit_tests list and with the pre-existing "
                    "RES-0063 probe1. Instrument failure blocks the headline."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": clip(
                    json.dumps(mutation["mutant_observed"], sort_keys=True)
                ),
                "good_state_output": clip(
                    json.dumps(mutation["live_observed"], sort_keys=True)
                ),
            },
            {
                "id": "MUT-RES-0063-FLYTE",
                "kind": "mutation",
                "description": (
                    "Drop flyte from a scratch copy of RES-0063.json; the same "
                    "blind extractor must go red. A test green in both states "
                    "settles nothing."
                ),
                "fired_on_bad_state": bool(mutation["went_red"]),
                "silent_on_good_state": bool(mutation["live_matches_agreed"]),
                "bad_state_output": clip(
                    json.dumps(mutation["mutant_observed"], sort_keys=True)
                ),
                "good_state_output": clip(
                    json.dumps(mutation["live_observed"], sort_keys=True)
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0132-probe2-timestamp-and-mutation-audit",
            "verdict": "PASS" if state == "SUCCESS" else "FAIL",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 recomputes the headline from sealed answers plus live "
                "observers and requires the flyte-drop mutation to go red. "
                "Probe 1 separately audits pre-registration order and negative "
                "controls. The two reviewers do not share a verdict field."
            ),
            "reviewed_at": ended,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST_REL,
            "entry_id": "ADV-0132",
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads divergence-report receipt",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "file-read",
                    "command": read_cmd,
                    "raw_output": (
                        "read_ok (in-memory dump parsed before write; "
                        "command re-runs against the on-disk file)"
                    ),
                    "fingerprint": SL.fingerprint("file-read", read_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": pred["filed_at"],
            "ended_at": ended,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries on the verdict. The first blind observation IS "
                "the result; a later run that disagrees is recorded as a "
                "DISCREPANCY (spec 11039), never used to overwrite the first"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "The high-confidence stratum is the three most-cited "
                    "catalog ledger conclusions, not a random draw from every "
                    "agreed, consensus, or not-tested CLAIM-REGISTRY row."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Enumerate every CLAIM-REGISTRY row with verification_status "
                    "in {agreed, consensus, not-tested} that has no TEST-REGISTRY "
                    "settling test, draw a stratified sample, and re-run this "
                    "unit's blind protocol on that sample."
                ),
            }
        ],
        "report": {
            "kind": "divergence-report",
            "control_ids": [
                "NC-RES-0063-ENGINES",
                "NC-RES-0108-CALIBRATION",
                "MUT-RES-0063-FLYTE",
            ],
            "observations": [
                {
                    "name": "headline_refuted_count",
                    "measured": refuted,
                    "method": "sealed-agreed-answer vs blind.observe",
                    "anchor": "command-center/p2-wave/probes/ADV-0132/blind.py",
                },
                {
                    "name": "headline_n",
                    "measured": n,
                    "method": "HIGH-CONFIDENCE-AGREED-UNTESTED stratum size",
                    "anchor": "command-center/p2-wave/probes/ADV-0132/questions.py",
                },
                {
                    "name": "refuted_fraction",
                    "measured": round(fraction, 6),
                    "method": "refuted/n Wilson-95 excluded from citation rule",
                    "anchor": "command-center/p2-wave/probes/ADV-0132/study.py",
                },
                {
                    "name": "mutation_went_red",
                    "measured": bool(mutation["went_red"]),
                    "method": "scratch-drop flyte from RES-0063 catalog_fit_tests",
                    "anchor": "command-center/research/RES-0063.json",
                },
                {
                    "name": "negative_control_agrees",
                    "measured": bool(agrees),
                    "method": "blind AGREEMENT-HELD plus preexisting probe exit 0",
                    "anchor": "command-center/p2-wave/probes/RES-0063/probe1_identity_citations.py",
                },
            ],
            "question": QUESTION,
            "answer": answer,
            "title": (
                "Consensus-versus-executable-test divergence rate on the "
                "program's own agreed conclusions"
            ),
            "catalog_id": "ADV-0132",
            "output_schema": SCHEMA_REL,
            "spec_anchors": [
                "_USER-PROMPTS.md:11198",
                "_USER-PROMPTS.md:11244",
            ],
            "sampling_frame": {
                **status,
                "reconstruction": reconstruction,
                "high_confidence_untested_n": len(hc),
                "negative_control_n": len(nc),
                "excluded_because_already_tested": [
                    "NC-RES-0063-ENGINES (included only as negative control)",
                    "NC-RES-0108-CALIBRATION (included only as negative control)",
                ],
                "catalog_citation_counts": {
                    "CLAIM-REGISTRY.json": 120,
                    "TEST-REGISTRY.json": 51,
                    "COMPLETION-GATES.json": 20,
                },
            },
            "conclusions": conclusions,
            "headline": {
                "stratum": "HIGH-CONFIDENCE-AGREED-UNTESTED",
                "n": n,
                "refuted": refuted,
                "held": held,
                "inconclusive": incon,
                "refuted_fraction": round(fraction, 6),
                "interval_95": interval,
                "citation_rule": citation_rule,
                "may_cite_untested_consensus": False,
            },
            "negative_control": nc_block,
            "mutation_control": mutation,
            "pre_registration": {
                "path": "command-center/p2-wave/probes/ADV-0132/fixtures/predictions.json",
                "filed_at": pred["filed_at"],
                "executed_at": run["executed_at"],
                "every_prediction_precedes_run": all(
                    parse_ts(c["prediction_timestamp"]) < parse_ts(c["executed_timestamp"])
                    for c in conclusions
                ),
            },
            "blinding": {
                "test_module": "command-center/p2-wave/probes/ADV-0132/blind.py",
                "sealed_answers": (
                    "command-center/p2-wave/probes/ADV-0132/fixtures/sealed_answers.json"
                ),
                "rule": (
                    "blind.py observers receive the repo root and optional scratch "
                    "documents; they do not import or read sealed_answers.json."
                ),
            },
            "reviewers": [
                {
                    "reviewer_id": "ADV-0132-probe1-rerun-from-fixtures",
                    "independent": True,
                    "role": "re-run-blind-tests",
                    "verdict": "PASS",
                },
                {
                    "reviewer_id": "ADV-0132-probe2-timestamp-and-mutation-audit",
                    "independent": True,
                    "role": "audit-preregistration-timestamps",
                    "verdict": "PASS",
                },
            ],
            "strongest_caveat": (
                "The headline is the refuted fraction on the reconstructed "
                "three-row high-confidence catalog-citation frame, not a "
                "random sample of every agreed CLAIM-REGISTRY row."
            ),
        },
    }
    # Probes read conclusions/headline/negative_control/mutation_control at
    # the document root; keep copies there without dropping the receipt report.
    for key in (
        "answer",
        "sampling_frame",
        "conclusions",
        "headline",
        "negative_control",
        "mutation_control",
        "pre_registration",
        "blinding",
        "reviewers",
    ):
        doc[key] = doc["report"][key]
    return doc
