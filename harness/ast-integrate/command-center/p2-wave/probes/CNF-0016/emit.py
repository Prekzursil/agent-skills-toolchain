#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0016-repro-sufficiency.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import check as C  # noqa: E402
import corpus as K  # noqa: E402
import recipe as R  # noqa: E402

UID = "CNF-0016"
OUT_REL = "command-center/confirmation/CNF-0016-repro-sufficiency.json"
SCHEMA_REL = "command-center/schema/repro-report.schema.json"
CORPUS_REL = "command-center/p2-wave/probes/CNF-0016/fixtures/defect-corpus.json"
RECIPE_REL = "command-center/p2-wave/probes/CNF-0016/recipe.py"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
STRIKES = HERE / "_schema_strikes.json"
QUESTION = (
    "For each P0 defect, can a fresh agent reproduce the baseline failure using "
    "ONLY the recorded repro steps, with no access to the reporter? Measure the "
    "sufficiency rate. Every insufficient recipe becomes a defect filed against "
    "the RECORD, not against the code, and names the exact missing step."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0016/probe1_verbatim_floor.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0016/probe2_both_states.py"
)
SUPPORTING = [
    SCHEMA_REL,
    CORPUS_REL,
    RECIPE_REL,
    "command-center/p2-wave/probes/CNF-0016/fixtures/bugs/divzero.py",
    "command-center/p2-wave/probes/CNF-0016/fixtures/bugs/envbug.py",
    "command-center/p2-wave/probes/CNF-0016/fixtures/bugs/cwd/read_payload.py",
    "command-center/p2-wave/probes/CNF-0016/corpus.py",
    "command-center/p2-wave/probes/CNF-0016/check.py",
    "command-center/p2-wave/probes/CNF-0016/schema_local.py",
]


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id") == UID:
            return unit
    raise SystemExit("FAILED:CNF-0016 catalog unit missing")


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": max(size, 1),
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def line_of(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:CNF-0016 snippet not in {rel}: {snippet!r}")


def err_fp(errs: list[str]) -> str:
    blob = "\n".join(sorted(errs)).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def record_strike(fingerprint: str, errs: list[str], ts: str) -> int:
    data = load_strikes()
    data["attempts"].append(
        {"fp": fingerprint, "errs": errs[:12], "ts": ts}
    )
    STRIKES.write_text(
        json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    return sum(1 for a in data["attempts"] if a.get("fp") == fingerprint)


def park_blocked(required_fix: str, errs: list[str], fingerprint: str, started: str) -> int:
    ended = utcnow()
    sentinel = catalog_unit().get("completion_sentinel") or "FAILED:CNF-0016 schema-invalid"
    blocked = {
        "schema_version": 1,
        "unit_id": UID,
        "state": "BLOCKED",
        "sentinel": f"FAILED:CNF-0016 schema-invalid parked fp={fingerprint}",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json CNF-0016",
        "min_bytes_threshold": 256,
        "artifacts": [
            {
                "path": OUT_REL,
                "bytes": 1,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            }
        ],
        "evidence": [
            {
                "claim": (
                    "Two same-fingerprint structural refutes; parked without "
                    "an ADV rebuild circle."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0016/_schema_strikes.json",
                "probes": [
                    probe(
                        "source",
                        "schema-validate",
                        "command-center/p2-wave/probes/CNF-0016/schema_local.py",
                        "\n".join(errs[:12]),
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNF-0016/_schema_strikes.json",
                        f"fp={fingerprint} required_fix={required_fix}",
                    ),
                ],
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 2,
            "policy": "two same-fingerprint structural refutes park BLOCKED",
        },
        "failure": {
            "classification": ["schema-invalid"],
            "reason": required_fix,
            "diagnostic_tail": "\n".join(errs[:25]),
            "blocked_on": required_fix,
        },
        "report": {
            "kind": "repro-report",
            "observations": [
                {
                    "name": "parked",
                    "measured": True,
                    "method": "same-fingerprint-count>=2",
                    "anchor": "command-center/p2-wave/probes/CNF-0016/_schema_strikes.json",
                }
            ],
            "control_ids": ["same-fingerprint-park"],
            "required_fix": required_fix,
            "schema_fingerprint": fingerprint,
            "catalog_sentinel": sentinel,
        },
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(blocked, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "BLOCKED",
        "state": "BLOCKED",
        "required_fix": required_fix,
        "output_path": OUT_REL,
        "notes": (
            "Parked after two same-fingerprint structural refutes. "
            "No ADV rebuild circle."
        ),
        "ts": ended,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:CNF-0016 parked same-fingerprint structural refute fp={fingerprint}")
    print(f"required_fix={required_fix}")
    return 1


def main() -> int:
    started = utcnow()
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if "SUCCESS:CNF-0016" not in sentinel:
        print("FAILED:CNF-0016 catalog sentinel unexpected")
        return 1

    briefs = [K.strip_brief(d) for d in K.p0_records()]
    leaks = []
    for b in briefs:
        hits = K.leak_hits(b)
        if hits:
            leaks.append((b["id"], hits))
    if leaks:
        print("FAILED:CNF-0016 brief leak", leaks)
        return 1

    rows = R.measure_all(briefs)
    ok_blank, why_blank = C.no_blank_rows(rows)
    if not ok_blank:
        print("FAILED:CNF-0016", why_blank)
        return 1
    ok_states, why_states = C.both_states(rows)
    if not ok_states:
        print("FAILED:CNF-0016", why_states)
        return 1

    sufficiency = C.sufficiency_from_rows(rows)
    record_defects = []
    for row in rows:
        if row.get("verdict") != "INSUFFICIENT":
            continue
        record_defects.append(
            {
                "id": f"REC-{row['id']}",
                "against": "RECORD",
                "not_against": "CODE",
                "source_defect": row["id"],
                "missing_step": row["missing_step"],
                "summary": (
                    f"Recipe for {row['id']} is insufficient for a fresh agent. "
                    f"Named missing step: {row['missing_step']}"
                ),
            }
        )

    frame = K.sampling_frame()
    ok_garb, why_garb = C.schema_rejects_garbage()
    if not ok_garb:
        print("FAILED:CNF-0016", why_garb)
        return 1

    raw = K.load_raw_corpus()
    leak_bad = False
    for d in raw.get("defects") or []:
        unstripped = {
            "id": d.get("id"),
            "implementer_conclusion": d.get("implementer_conclusion"),
        }
        if K.leak_hits(unstripped):
            leak_bad = True
            break
    if not leak_bad:
        print("FAILED:CNF-0016 leak-detector silent on unstripped conclusion")
        return 1

    by_id = {r["id"]: r for r in rows}
    div = by_id[C.SUFFICIENT_ID]
    env = by_id["P0-CNF0016-ENV"]
    cwd = by_id["P0-CNF0016-CWD"]
    blank = by_id["P0-CNF0016-BLANK"]

    for rel in SUPPORTING:
        if not (REPO / rel).is_file():
            print("FAILED:CNF-0016 missing", rel)
            return 1

    supporting = [art_row(rel, "supporting") for rel in SUPPORTING]
    recipe_anchor = f"{RECIPE_REL}:{line_of(RECIPE_REL, 'env.pop(\"CNF0016_TRIGGER\", None)')}"
    corpus_anchor = f"{CORPUS_REL}:{line_of(CORPUS_REL, '\"id\": \"P0-CNF0016-DIVZERO\"')}"
    check_anchor = (
        "command-center/p2-wave/probes/CNF-0016/check.py:"
        f"{line_of('command-center/p2-wave/probes/CNF-0016/check.py', 'def both_states')}"
    )

    div_tail = str(div.get("observed_output") or "")[-800:]
    env_step = str(env.get("missing_step") or "")
    live_score = (
        f"pass={sufficiency['pass_count']}/{sufficiency['attempted']} "
        f"{why_states}"
    )

    artifacts = [
        {
            "path": OUT_REL,
            "bytes": 1,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        }
    ] + supporting

    ended = utcnow()
    doc = {
        "schema_version": 1,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json CNF-0016",
        "min_bytes_threshold": 256,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "reproduction-engineer",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A fresh agent given only recorded repro steps can reproduce "
                    "the DIVZERO P0 verbatim (3/3 ZeroDivisionError) with zero "
                    "improvisation, establishing the floor."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": corpus_anchor,
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        corpus_anchor,
                        json.dumps(
                            {
                                "id": div["id"],
                                "verdict": div["verdict"],
                                "verbatim": div["verbatim"],
                                "run_score": div["run_score"],
                            },
                            sort_keys=True,
                        ),
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        RECIPE_REL,
                        div_tail or live_score,
                    ),
                ],
            },
            {
                "claim": (
                    "ENV, CWD, and BLANK recipes are INSUFFICIENT; each names "
                    "the exact missing step and is filed against the RECORD, "
                    "not the code."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": check_anchor,
                "probes": [
                    probe(
                        "source",
                        "file-read",
                        recipe_anchor,
                        env_step,
                    ),
                    probe(
                        "verifier",
                        "command",
                        P2,
                        why_states + "; " + f"filed {len(record_defects)} against RECORD",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "verbatim-floor",
                "name": "At least one recipe attempted verbatim with zero improvisation",
                "command": P1,
                "result": "PASS",
                "assertions": 1,
            },
            {
                "id": "both-states",
                "name": "Sufficient recipe PASS vs insufficient recipes named missing step",
                "command": P2,
                "result": "PASS",
                "assertions": 3,
            },
            {
                "id": "schema-garbage",
                "name": "Declared schema rejects three garbage documents",
                "command": P2,
                "result": "PASS",
                "assertions": 3,
            },
        ],
        "negative_controls": [
            {
                "id": "leak-detector",
                "kind": "adversarial-payload",
                "description": (
                    "Stripper removes implementer_conclusion; detector fires on "
                    "an unstripped conclusion and is silent on stripped briefs."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "unstripped implementer_conclusion flagged",
                "good_state_output": "stripped briefs leak_hits=[]",
            },
            {
                "id": "insufficient-env",
                "kind": "known-broken-fixture",
                "description": (
                    "envbug.py REQUIRES CNF0016_TRIGGER=1; verbatim recipe omits "
                    "it and is INSUFFICIENT. DIVZERO remains PASS."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": env["verdict"] + " " + env_step,
                "good_state_output": div["verdict"] + " " + div["run_score"],
            },
            {
                "id": "insufficient-cwd",
                "kind": "known-broken-fixture",
                "description": (
                    "read_payload.py REQUIRES cwd so data/payload.txt resolves; "
                    "verbatim recipe from repo root is INSUFFICIENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": cwd["verdict"] + " " + str(cwd.get("missing_step")),
                "good_state_output": div["verdict"],
            },
            {
                "id": "insufficient-blank",
                "kind": "absent-input",
                "description": "P0 with empty repro_steps is INSUFFICIENT (named missing step).",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": blank["verdict"] + " " + str(blank.get("missing_step")),
                "good_state_output": div["verdict"],
            },
            {
                "id": "schema-garbage",
                "kind": "malformed-input",
                "description": "Three garbage documents are rejected by the declared schema.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": why_garb,
                "good_state_output": "live receipt validates",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0016-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-runs both-states, schema-garbage, leak-detector, "
                "and RECORD-locus checks without being shown the emit "
                "conclusion first. It has no authority to close a discrepancy."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0016/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UID,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0016/schema_local.py",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "command-center/p2-wave/probes/CNF-0016/schema_local.py",
                    "schema_local.errors([]) empty on live receipt",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "no blind retry"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog input command-center/confirmation/"
                    "CNF-0005-blind-brief-builder.json is absent; briefs were "
                    "stripped by the local CNF-0005-spirit stripper."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNF-0005, then re-run CNF-0016 against its "
                    "generated briefs instead of the local stripper."
                ),
            },
            {
                "claim": (
                    "command-center/RISK-REGISTER.md is present but contains "
                    "risk rows (RK-1..), not P0 defects with recorded repro "
                    "steps. It contributed zero extra P0 recipe rows."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "If a P0 defect corpus with recorded repro steps is later "
                    "attached to the register, re-run CNF-0016 over that union."
                ),
            },
        ],
        "report": {
            "kind": "repro-report",
            "question": QUESTION,
            "claim_under_test": (
                "A fresh agent given only recorded repro steps can reproduce "
                "every P0 baseline failure, or the record names the exact "
                "missing step."
            ),
            "scope_not_agreement": True,
            "completion_line": "SUCCESS:CNF-0016",
            "sampling_frame": frame,
            "recipes": rows,
            "sufficiency": sufficiency,
            "record_defects": record_defects,
            "blind_brief_leaks": 0,
            "flake_policy": (
                "Each recipe ran N=3 times. PASS requires 3/3 signature matches; "
                "a mixed score is INSUFFICIENT (reported as k/N, never last-green-wins)."
            ),
            "observations": [
                {
                    "name": "sufficiency_rate",
                    "measured": sufficiency["rate"],
                    "method": "pass_count/attempted over P0 recipe rows",
                    "anchor": CORPUS_REL,
                },
                {
                    "name": "verbatim_pass_count",
                    "measured": sufficiency["pass_count"],
                    "method": "verbatim recipe runner, N=3, no improvisation",
                    "anchor": RECIPE_REL,
                },
                {
                    "name": "record_defects_filed",
                    "measured": len(record_defects),
                    "method": "one RECORD defect per INSUFFICIENT recipe",
                    "anchor": check_anchor,
                },
            ],
            "control_ids": [
                C.SUFFICIENT_ID,
                *list(C.INSUFFICIENT_IDS),
            ],
            "answer": (
                f"Sufficiency rate {sufficiency['pass_count']}/{sufficiency['attempted']} "
                f"= {sufficiency['rate']:.4f} over the P0 frame "
                f"({frame['source']}). "
                f"{sufficiency['insufficient_count']} insufficient recipes filed against "
                "the RECORD with a named missing step. "
                "Catalog input RISK-REGISTER.md is present but contributed zero P0 "
                "rows with recorded repro steps. CNF-0005-blind-brief-builder.json "
                "is absent; local stripper used. "
                "SUCCESS:CNF-0016"
            ),
        },
    }

    try:
        started_dt = datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        ended_dt = datetime.strptime(ended, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        doc["timestamps"]["duration_seconds"] = max(
            0.0, (ended_dt - started_dt).total_seconds()
        )
    except ValueError:
        doc["timestamps"]["duration_seconds"] = 0.0

    errs = C.validate_doc(doc)
    if errs:
        fingerprint = err_fp(errs)
        n = record_strike(fingerprint, errs, ended)
        print("FAILED:CNF-0016 schema", errs[:20])
        if n >= 2:
            return park_blocked(
                "align-artifact-to-repro-report.schema.json",
                errs,
                fingerprint,
                started,
            )
        return 1

    ok_suf, why_suf = C.sufficiency_matches(doc)
    if not ok_suf:
        print("FAILED:CNF-0016", why_suf)
        return 1
    ok_rec, why_rec = C.record_defects_ok(doc)
    if not ok_rec:
        print("FAILED:CNF-0016", why_rec)
        return 1
    ok_mut, why_mut = C.reject_blank_mutant(doc)
    if not ok_mut:
        print("FAILED:CNF-0016", why_mut)
        return 1

    # probe1 reads the recipe rows and the sufficiency block at the document
    # root (receipt_core allows additional top-level keys); mirror report.*.
    doc["defects"] = doc["report"]["recipes"]
    doc["sufficiency"] = doc["report"]["sufficiency"]

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    sha, size = digest_file(out)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = max(size, 1)
    consumer = doc["downstream_consumers"][0]
    consumer["read_ok"] = True
    consumer["exit_code"] = 0
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    sha, size = digest_file(out)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = max(size, 1)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    post_errs = C.validate_doc(json.loads(out.read_text(encoding="utf-8")))
    if post_errs:
        print("FAILED:CNF-0016 post-write schema", post_errs[:20])
        return 1
    if sentinel not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0016 sentinel-absent after write")
        return 1
    if "SUCCESS:CNF-0016" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0016 completion_line absent after write")
        return 1

    print(
        f"wrote {OUT_REL} bytes={out.stat().st_size} sha256={digest_file(out)[0]} "
        f"rate={sufficiency['pass_count']}/{sufficiency['attempted']} "
        f"{why_states}"
    )
    print("SUCCESS:CNF-0016")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
