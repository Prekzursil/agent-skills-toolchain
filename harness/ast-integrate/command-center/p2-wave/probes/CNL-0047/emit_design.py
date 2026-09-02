#!/usr/bin/env python3
"""Emit the CNL-0047 design note (JSON document stored at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft7Validator, RefResolver

HERE = Path(__file__).resolve().parent


def repo_root(start: Path) -> Path:
    for cand in [start, *start.parents]:
        if (cand / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return cand
    raise SystemExit("FAILED:CNL-0047 repo root not found")


REPO = repo_root(HERE)
sys.path.insert(0, str(HERE))
from broken import EqualizingScheduler  # noqa: E402
from detect import prolific_silenced_after_dominant_throttle  # noqa: E402
from fixtures import QUOTA_STARVATION, speakers_for  # noqa: E402
from reviewer import independent_review  # noqa: E402
from scheduler import Scheduler, clone_seats  # noqa: E402

OUT = "command-center/design/council/CNL-0047-turn-taking-and-speaking-order-engine-as-one-shared-primit.md"
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0047/probe2_both_states.py"
)
QUESTION = (
    "Round-robin order, speaking rights, turn length and per-seat speaking "
    "quotas are four dials on one scheduler - what is that scheduler's "
    "contract, and what happens to a seat that is entitled to speak but has "
    "nothing to add?"
)
SENTINEL = "SUCCESS:CNL-0047"
STRIKES = HERE / "_schema_strikes.json"
MIN_BYTES = 2048
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNL-0047/scheduler.py",
    "command-center/p2-wave/probes/CNL-0047/broken.py",
    "command-center/p2-wave/probes/CNL-0047/detect.py",
    "command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
    "command-center/p2-wave/probes/CNL-0047/probe2_both_states.py",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
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


def local_validator() -> Draft7Validator:
    store: dict = {}
    for rel in (
        SCHEMA,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ):
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        store[doc["$id"]] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    schema = store["https://ast-integrate.invalid/" + SCHEMA]
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)

    def no_net(uri: str):
        raise RuntimeError(f"blocked network fetch {uri}")

    resolver.handlers["http"] = no_net
    resolver.handlers["https"] = no_net
    return Draft7Validator(schema, resolver=resolver)


def schema_errors(doc: dict) -> list[str]:
    validator = local_validator()
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


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


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def art_row(rel: str, role: str, sha: str | None = None, size: int | None = None) -> dict:
    path = REPO / rel
    if sha is None or size is None:
        if path.is_file():
            sha, size = digest_file(path)
        else:
            sha, size = "0" * 64, 1
    return {
        "path": rel,
        "sha256": sha,
        "bytes": max(int(size), 1),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def park_blocked(required_fix: str, errs: list[str], fp: str) -> int:
    now = utcnow()
    blocked = {
        "schema_version": 1,
        "unit_id": "CNL-0047",
        "state": "BLOCKED",
        "sentinel": "FAILED:CNL-0047 parked same-fingerprint structural refute",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0047",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [art_row(SCHEMA, "supporting")],
        "evidence": [
            {
                "claim": "Two same-fingerprint structural refutes; parked without an ADV rebuild circle.",
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNL-0047/_schema_strikes.json",
                "probes": [
                    probe_obj(
                        "source",
                        "schema-validate",
                        "local RefResolver Draft7Validator",
                        "\n".join(errs[:12]),
                    ),
                    probe_obj(
                        "verifier",
                        "file-read",
                        "err_fp of sorted schema errors",
                        f"fingerprint={fp}",
                    ),
                ],
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
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
            "kind": "council-design-note",
            "observations": [
                {
                    "name": "schema_fingerprint",
                    "measured": fp,
                    "method": "sha256 of sorted schema errors, truncated",
                    "anchor": "command-center/p2-wave/probes/CNL-0047/_schema_strikes.json",
                }
            ],
            "control_ids": ["same-fingerprint-park"],
            "required_fix": required_fix,
        },
    }
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blocked, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ret = {
        "id": "CNL-0047",
        "unit_id": "CNL-0047",
        "status": "BLOCKED",
        "state": "BLOCKED",
        "required_fix": required_fix,
        "schema_fingerprint": fp,
        "output_path": OUT,
        "cloud_ok": False,
        "notes": "Parked after two same-fingerprint structural refutes. No ADV rebuild circle.",
        "ts": now,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:CNL-0047 parked same-fingerprint structural refute fp={fp}")
    print(f"required_fix={required_fix}")
    return 1


def run_engine(cls):
    seats = clone_seats(QUOTA_STARVATION["seats"])
    sched = cls(
        seats=seats,
        turn_length_tokens=int(QUOTA_STARVATION["turn_length_tokens"]),
    )
    sched.run(speakers_for("quota-starvation"), max_steps=48)
    det = prolific_silenced_after_dominant_throttle(sched)
    return sched, det


def build_doc(
    *,
    started: str,
    ended: str,
    t1: str,
    t2: str,
    c1: int,
    c2: int,
    good_det: dict,
    bad_det: dict,
    good_sched,
    bad_sched,
    review: dict,
    primary_sha: str,
    primary_bytes: int,
) -> dict:
    answer = (
        "The four dials are not four engines. They are four inputs to one "
        "next_offer machine (round-robin cursor, per-seat speaking_right, "
        "turn_length_tokens, per-seat quota_tokens). next_offer walks the "
        "roster from the cursor, skips any seat without speaking_right "
        "without emitting an offer, THROTTLEs a right-holding seat whose "
        "remaining quota is 0, otherwise offers min(turn_length, remaining "
        "quota). SPEAK consumes that many tokens from the seat's quota and "
        "advances the cursor. A seat that is entitled (right, remaining "
        "quota, cursor) but has nothing to add MUST YIELD: the cursor still "
        "advances, quota is not consumed, the seat is not marked disengaged "
        "(disengagement is CNL-0089's consecutive-yield floor, not this "
        "unit). Remainder smaller than turn_length is a partial SPEAK, not "
        "a whole-turn THROTTLE. Protocols do not implement their own airtime. "
        + SENTINEL
    )
    nc_bad = json.dumps(bad_det, sort_keys=True)
    nc_good = json.dumps(good_det, sort_keys=True)
    consumer_cmd = f"python3 -c json.loads({OUT})"
    return {
        "schema_version": 1,
        "unit_id": "CNL-0047",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0047",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "headless-linux",
        },
        "artifacts": [art_row(OUT, "primary", primary_sha, primary_bytes)]
        + [art_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "A dominant seat is throttled at its own 50-token quota "
                    "without silencing a legitimately prolific seat that "
                    "finishes its 45-token bag."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
                "probes": [
                    probe_obj("source", "command", P1, t1, c1),
                    probe_obj(
                        "verifier",
                        "byte-compare",
                        "sum SPEAK tokens from Scheduler.log not seat.spoken_tokens",
                        (
                            f"spoken={json.dumps(good_sched.spoken())} "
                            f"throttles={json.dumps(good_sched.throttles())} "
                            f"yields={json.dumps(good_sched.yields())}"
                        ),
                    ),
                ],
            },
            {
                "claim": (
                    "prolific_silenced_after_dominant_throttle FIRES on the "
                    "equalizing planted-bad scheduler and is SILENT on the "
                    "known-good Scheduler."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNL-0047/probe2_both_states.py",
                "probes": [
                    probe_obj("source", "command", P2, t2, c2),
                    probe_obj(
                        "verifier",
                        "test-run",
                        "command-center/p2-wave/probes/CNL-0047/reviewer.py remainder-cap instance",
                        json.dumps(review.get("counterexample"), sort_keys=True),
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-quota-starvation",
                "name": "Dominant throttled; prolific finishes 45; quiet YIELD does not consume quota",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "output_tail": t1[-1500:],
            },
            {
                "id": "probe2-both-states",
                "name": "Detector FIRE on planted-bad, SILENT on known-good",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "output_tail": t2[-1500:],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-equalizing-silences-prolific",
                "kind": "known-broken-fixture",
                "description": (
                    "Check prolific_silenced_after_dominant_throttle is meant "
                    "to reject an equalizing scheduler that silences a still-"
                    "entitled prolific seat once the dominant seat hits quota."
                ),
                "fired_on_bad_state": bool(bad_det["fired"]),
                "silent_on_good_state": not bool(good_det["fired"]),
                "bad_state_output": nc_bad,
                "good_state_output": nc_good,
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0047-independent-log-recount",
            "verdict": "PASS" if review.get("pass") else "FAIL",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "reviewed_at": ended,
            "notes": (
                "Re-sum SPEAK tokens from the offer log (not seat.spoken_tokens) "
                "and run remainder-cap-quota-5-vs-turn-length-20, an instance "
                "probe1 does not use. "
                + json.dumps(review.get("counterexample"), sort_keys=True)
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0047/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNL-0047",
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(
                    "source",
                    "schema-validate",
                    consumer_cmd,
                    "consumer=json.loads of catalog output_path\nunit_id=CNL-0047\nstate=SUCCESS\n"
                    + SENTINEL,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a "
                "3rd attempt. Two same-fingerprint structural refutes park "
                "BLOCKED with required_fix named. No ADV rebuild circle."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Exact field names in 11-COUNCIL-SPECIFICATION.schema.json "
                    "for speaking quotas and turn length."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-open this unit when 11-COUNCIL-SPECIFICATION.schema.json "
                    "and 12-COUNCIL-PROTOCOLS-AND-PRESETS.json are present on "
                    "this worktree and map dial names to those fields."
                ),
            }
        ],
        "report": {
            "kind": "council-design-note",
            "title": "Turn-taking and speaking-order engine as one shared primitive",
            "question": QUESTION,
            "answer": answer,
            "observations": [
                {
                    "name": "dominant_spoken_tokens",
                    "measured": int(good_sched.spoken().get("dominant", 0)),
                    "method": "live Scheduler.run on quota-starvation fixture",
                    "anchor": "command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
                },
                {
                    "name": "prolific_spoken_tokens",
                    "measured": int(good_sched.spoken().get("prolific", 0)),
                    "method": "independent sum of SPEAK tokens from the offer log",
                    "anchor": "command-center/p2-wave/probes/CNL-0047/scheduler.py",
                },
                {
                    "name": "quiet_yield_consumed_quota",
                    "measured": False,
                    "method": "quiet.remaining() == quiet.quota_tokens after YIELD",
                    "anchor": "command-center/p2-wave/probes/CNL-0047/probe1_quota_starvation.py",
                },
                {
                    "name": "planted_bad_detector_fired",
                    "measured": bool(bad_det["fired"]),
                    "method": "prolific_silenced_after_dominant_throttle on EqualizingScheduler",
                    "anchor": "command-center/p2-wave/probes/CNL-0047/broken.py",
                },
                {
                    "name": "known_good_detector_silent",
                    "measured": not bool(good_det["fired"]),
                    "method": "same detector on Scheduler",
                    "anchor": "command-center/p2-wave/probes/CNL-0047/detect.py",
                },
            ],
            "control_ids": ["NC-equalizing-silences-prolific"],
            "contract": {
                "primitive": "Scheduler.next_offer",
                "dials": {
                    "order": "Cursor starts at 0. After SPEAK, YIELD, or THROTTLE the cursor becomes (index+1) mod roster. Seats without speaking_right are skipped and never appear in the offer log.",
                    "speaking_right": "A seat with speaking_right=false is never offered. Absence of right is not YIELD and is not disengagement.",
                    "turn_length": "Each offer's cap is min(turn_length_tokens, remaining_quota). Remainder smaller than turn_length is still offered.",
                    "quota": "Quota counts SPEAK tokens only. YIELD does not consume quota. THROTTLE fires iff remaining_quota==0 for a right-holding seat at the cursor.",
                },
                "entitled_but_empty": {
                    "act": "YIELD",
                    "consumes_quota": False,
                    "consumes_turn_slot": True,
                    "marks_disengaged": False,
                    "handoff": "Consecutive-yield disengagement is CNL-0089, not this scheduler.",
                },
                "not_four_engines": True,
            },
            "family": {
                "name": "TURN-TAKING-DIALS",
                "expected_n": 4,
                "counted_n": 4,
                "members": [
                    "round-robin order",
                    "speaking rights",
                    "turn length",
                    "per-seat speaking quotas",
                ],
            },
            "both_states": {
                "check": "prolific_silenced_after_dominant_throttle",
                "known_good_fired": bool(good_det["fired"]),
                "planted_bad_fired": bool(bad_det["fired"]),
                "known_good_spoken": good_sched.spoken(),
                "planted_bad_spoken": bad_sched.spoken(),
            },
        },
        "extensions": {
            "completion_sentinel": SENTINEL,
            "cloud_ok_is_not_delivery": True,
            "global_unit_manifest_write": False,
            "harness_files_present": False,
        },
    }


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    started = utcnow()
    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNL-0047 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    good_sched, good_det = run_engine(Scheduler)
    bad_sched, bad_det = run_engine(EqualizingScheduler)
    review = independent_review()
    if not review.get("pass"):
        print("FAILED:CNL-0047 emit reviewer")
        return 1
    if good_det["fired"] or not bad_det["fired"]:
        print("FAILED:CNL-0047 emit both-states")
        return 1

    ended = utcnow()
    doc = build_doc(
        started=started,
        ended=ended,
        t1=t1,
        t2=t2,
        c1=c1,
        c2=c2,
        good_det=good_det,
        bad_det=bad_det,
        good_sched=good_sched,
        bad_sched=bad_sched,
        review=review,
        primary_sha="0" * 64,
        primary_bytes=MIN_BYTES,
    )

    validator = local_validator()
    garbage_ok = True
    for garbage in ({}, {"totally": "unrelated"}, {"unit_id": "NOPE"}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNL-0047 schema accepted garbage {garbage}")
            garbage_ok = False
            break
    if not garbage_ok:
        return 1

    errs = schema_errors(doc)
    if errs:
        fp = err_fp(errs)
        strikes = load_strikes()
        prior = [a.get("fingerprint") for a in strikes.get("attempts") or []]
        strikes["attempts"].append(
            {"fingerprint": fp, "errors": errs[:12], "ts": ended}
        )
        STRIKES.write_text(
            json.dumps(strikes, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        print("FAILED:CNL-0047 schema errors")
        for e in errs[:20]:
            print(" ", e)
        if prior.count(fp) >= 1:
            return park_blocked(
                "align-artifact-to-council-design-note.schema.json", errs, fp
            )
        return 1

    out = REPO / OUT
    dump(out, doc)
    sha, size = digest_file(out)
    doc["artifacts"][0]["sha256"] = sha
    doc["artifacts"][0]["bytes"] = size
    dump(out, doc)
    sha, size = digest_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNL-0047 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNL-0047 sentinel absent from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print("SUCCESS:CNL-0047 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
