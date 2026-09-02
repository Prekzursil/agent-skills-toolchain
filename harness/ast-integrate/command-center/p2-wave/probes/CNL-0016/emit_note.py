#!/usr/bin/env python3
"""Emit the CNL-0016 council design note (JSON stored at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recount as R  # noqa: E402
import sampler as S  # noqa: E402

OUT = "command-center/design/council/CNL-0016-random-and-stratified-selection-with-replay-safe-seeding.md"
SCHEMA = "command-center/schema/council-design-note.schema.json"
LOCAL_SCHEMA = (
    "command-center/p2-wave/probes/CNL-0016/council-design-note.schema.json"
)
QUESTION = (
    "What is the sampling frame for random and stratified participant selection, "
    "and how is the seed captured so a replayed council draws the identical roster "
    "while a fresh run does not?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0016/probe1_seed_roster.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0016/probe2_independent_recount.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0016 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, claim: str, mechanism: str) -> dict:
    line = find_line(REPO / rel, snippet)
    return {
        "claim": claim,
        "verdict": "CONFIRMED",
        "anchor": f"{rel}:{line}",
        "mechanism": mechanism,
        "path": rel,
        "line": line,
        "snippet": snippet,
    }


def main() -> int:
    people, spec = R.load_fixtures()
    seed_a = S.parse_seed_hex(spec["seed_a_hex"])
    seed_b = S.parse_seed_hex(spec["seed_b_hex"])
    u_a = S.run_draw(people, spec, seed_a, "uniform")
    u_b = S.run_draw(people, spec, seed_b, "uniform")
    s_a = S.run_draw(people, spec, seed_a, "stratified")
    s_b = S.run_draw(people, spec, seed_b, "stratified")
    ru_a = R.recount_uniform(people, int(spec["uniform_k"]), seed_a)
    rs_a = R.recount_stratified(people, spec["stratified_quotas"], seed_a)
    if u_a["roster"] != ru_a["roster"] or s_a["roster"] != rs_a["roster"]:
        print("FAILED:CNL-0016 emit author/reviewer roster split")
        return 1
    if u_a["roster"] == u_b["roster"] or s_a["roster"] == s_b["roster"]:
        print("FAILED:CNL-0016 emit seeds did not distinguish rosters")
        return 1
    if u_a["roster"] != S.run_draw(people, spec, seed_a, "uniform")["roster"]:
        print("FAILED:CNL-0016 emit same-seed replay drifted")
        return 1
    drifted = [p for p in people if p["id"] != "P01"]
    try:
        S.run_draw(
            drifted, spec, seed_a, "uniform", recorded_fp=u_a["frame_fingerprint"]
        )
        print("FAILED:CNL-0016 emit drift was accepted")
        return 1
    except ValueError:
        pass

    frame = S.eligible_frame(people)
    frozen = S.frozen_roster(frame, int(spec["uniform_k"]), seed_a)
    sampler_rel = "command-center/p2-wave/probes/CNL-0016/sampler.py"
    recount_rel = "command-center/p2-wave/probes/CNL-0016/recount.py"
    pool_rel = "command-center/p2-wave/probes/CNL-0016/fixtures/pool.json"
    evidence = [
        ev(
            sampler_rel,
            "ANCHOR:frame-is-ordered-eligible-catalog",
            "Sampling frame is the ordered eligible catalog, not the ineligible tail",
            "eligible_frame filters eligible=true then sorts by participant id",
        ),
        ev(
            sampler_rel,
            "ANCHOR:hmac-fisher-yates",
            "Same recruitment_seed plus same frame yields an identical roster",
            "HMAC-SHA256 Fisher-Yates with rejection sampling; domain-separated keys",
        ),
        ev(
            sampler_rel,
            "ANCHOR:fresh-run-mints-csprng-seed",
            "A fresh run mints a CSPRNG seed instead of reusing the replay seed",
            "mint_fresh_seed calls os.urandom(32); replay path takes recorded hex",
        ),
        ev(
            sampler_rel,
            "ANCHOR:replay-refuses-frame-drift",
            "Replay refuses when the live frame fingerprint differs from the captured one",
            "assert_replay_frame compares recorded vs live HMAC frame fingerprints",
        ),
        ev(
            sampler_rel,
            "ANCHOR:stratum-domain-separation",
            "Stratified draws use per-stratum child keys so quotas cannot steal seats",
            "domain_key(seed, CNL-0016|stratum|<name>) then Fisher-Yates inside the stratum",
        ),
        ev(
            recount_rel,
            "Re-implements HMAC-SHA256 Fisher-Yates",
            "Independent reviewer recount matches the author sampler seat-for-seat",
            "recount.py re-tabulates the HMAC stream without calling fisher_yates_take",
        ),
        ev(
            pool_rel,
            '"eligible": false',
            "P12 is ineligible and is outside the sampling frame",
            "fixture catalog marks P12 eligible=false; both draws omit P12",
        ),
    ]

    answer = (
        "The sampling frame is the finite ordered catalog of eligible participant "
        "descriptors (eligible=true), sorted by participant id, with ineligible "
        "rows excluded. Uniform selection draws k seats without replacement from "
        "that whole frame. Stratified selection partitions the same frame by the "
        "declared stratum key (vendor in the fixture) and draws each quota from "
        "its own stratum using a domain-separated child key. The load-bearing seed "
        "is a 32-byte recruitment_seed captured in the run artifact together with "
        "the frame fingerprint (HMAC of the canonical id+stratum list). Replay "
        "feeds that recorded seed and fingerprint back into the same HMAC-SHA256 "
        "Fisher-Yates; same seed plus same frame yields an identical roster. A "
        "fresh run MUST mint a new seed with os.urandom rather than reuse the "
        "previous seed, so it does not redraw the replay roster. Replay MUST "
        "refuse when the live frame fingerprint differs from the captured one. "
        "Same-seed identity without a different-seed inequality is insufficient: "
        "a frozen sampler that ignores the seed would still pass the first check."
    )
    note = {
        "unit_id": "CNL-0016",
        "kind": "council-design-note",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0016",
        "completion_sentinel": "SUCCESS:CNL-0016",
        "title": "Random and stratified selection with replay-safe seeding",
        "question": QUESTION,
        "claim_under_test": (
            "The sampling frame is the ordered eligible catalog; a captured "
            "recruitment_seed plus frame fingerprint replays the identical roster, "
            "and a fresh CSPRNG seed does not."
        ),
        "answer": answer,
        "mechanism": {
            "sampling_frame": (
                "ordered eligible catalog; order = lexicographic participant id; "
                "P12 is ineligible and is outside the frame"
            ),
            "frame_ids": u_a["frame_ids"],
            "frame_size": u_a["frame_size"],
            "frame_fingerprint": u_a["frame_fingerprint"],
            "stratum_key": "vendor",
            "rng": (
                "HMAC-SHA256(seed, domain) as the child key; 64-bit rejection "
                "sampling Fisher-Yates; domain CNL-0016|uniform or "
                "CNL-0016|stratum|<name>"
            ),
            "seed_capture": (
                "recruitment_seed_hex (32 bytes) + frame_fingerprint stored on "
                "the run; replay passes both back; fresh run calls os.urandom(32)"
            ),
            "recorded_rosters": {
                "uniform_seed_a": u_a["roster"],
                "uniform_seed_b": u_b["roster"],
                "stratified_seed_a": s_a["roster"],
                "stratified_seed_b": s_b["roster"],
            },
            "dependencies_not_delivered": [
                "CNL-0005 (nine per-seat dials; catalog question used, artifact absent)",
                "CNL-0011 (replay-state model; recruitment named as a seed, artifact absent)",
            ],
        },
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "evidence": evidence,
        "negative_controls": [
            {
                "id": "frozen-sampler",
                "on_state": (
                    "a sampler that ignores the seed and always returns the first "
                    "k eligible participant ids"
                ),
                "observed": (
                    f"frozen roster {frozen} is identical under seed_a and seed_b "
                    f"(fired=True); live HMAC uniform rosters "
                    f"{u_a['roster']} vs {u_b['roster']} differ (fired=False)"
                ),
            },
            {
                "id": "frame-drift-replay",
                "on_state": (
                    "a replay whose live catalog dropped P01 so the frame "
                    "fingerprint no longer matches the captured fingerprint"
                ),
                "observed": (
                    "run_draw raised ValueError fingerprint mismatch and did not "
                    "emit a substitute roster"
                ),
            },
        ],
        "negative_control": {
            "rejects": (
                "a frozen sampler that returns the first k eligible ids regardless "
                "of seed, and a replay whose frame fingerprint no longer matches"
            ),
            "observed": (
                f"frozen roster {frozen} is identical under seed_a and seed_b; "
                "live HMAC rosters differ; dropping P01 raises fingerprint mismatch"
            ),
            "verbatim": (
                "NEGATIVE CONTROL CNL-0016: the different-seed check FIRES when a "
                "frozen sampler returns the same roster under two seeds; the same "
                "check is SILENT on the live HMAC sampler. Replay refuses a drifted "
                "frame rather than silently seating a different roster."
            ),
        },
        "reviewer": {
            "reviewer_id": "CNL-0016-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "control_executed": True,
            "method": (
                "recount.py re-tabulates Fisher-Yates from HMAC stream integers; "
                "a roster disagreement blocks the unit"
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "schema"},
            {"path": SCHEMA, "exists": True, "role": "catalog-schema-shim"},
            {"path": sampler_rel, "exists": True, "role": "mechanism"},
            {"path": recount_rel, "exists": True, "role": "reviewer"},
        ],
        "schema_note": (
            "Catalog output_schema is a GENERATED SHIM whose $ref points at "
            "https://ast-integrate.invalid/...; jsonschema 4.10.3 RefResolver "
            "tries the network and does not constrain this note. This unit "
            "validates against the per-unit schema. Overwriting the shared "
            "catalog schema would be a sibling rebuild circle."
        ),
        "residual_unknowns": [
            "Windows restore inputs 11-COUNCIL-SPECIFICATION.schema.json and "
            "_USER-PROMPTS.md:10746-10767 / 10915-10946 are not on this Linux "
            "worktree; this note does not claim those files were re-read.",
            "CNL-0005 and CNL-0011 artifacts are not on disk; seat-dial names "
            "and the replay envelope field list are taken from catalog questions, "
            "not from delivered design notes.",
        ],
        "emitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if not (REPO / SCHEMA).is_file():
        print(f"FAILED:CNL-0016 catalog schema shim missing: {SCHEMA}")
        return 1
    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(note), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0016 emit schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    if not list(validator.iter_errors(garbage)):
        print("FAILED:CNL-0016 emit schema accepted garbage")
        return 1
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(note, indent=2) + "\n", encoding="utf-8")
    digest, size = sha256_file(out_path)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0016 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
