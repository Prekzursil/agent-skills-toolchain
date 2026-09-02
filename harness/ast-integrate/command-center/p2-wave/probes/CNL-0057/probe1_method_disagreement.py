#!/usr/bin/env python3
"""Probe 1: voting vs synthesis-only disagree; reason is method, not seats."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import synthesis_only as S  # noqa: E402

NOTE = (
    "command-center/design/council/"
    "CNL-0057-synthesis-only-mode-when-taking-no-vote-is-the-correct-des.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0057-probe1 {msg}")
    return 1


def main() -> int:
    diag = S.load_fixture("diagnosis_split.json")
    scalar = S.load_fixture("scalar_estimate.json")
    mutated = S.load_fixture("mutated_participants.json")

    md = S.methods_disagree(diag)
    print(
        f"diagnosis disagree={md['disagree']} reason={md['reason']} "
        f"detail={md['detail']} vote_winner={md['vote'].get('winner')} "
        f"synthesis_winner={md['synthesis'].get('winner')} "
        f"live={md['synthesis'].get('live_hypotheses')}"
    )
    if not md["disagree"]:
        return fail("diagnosis vote and synthesis-only did not disagree")
    if md["reason"] != "method":
        return fail(f"expected reason=method, got {md['reason']}")
    if md["vote"].get("winner") != "cache":
        return fail("expected plurality winner cache")
    if md["synthesis"].get("winner") is not None:
        return fail("synthesis-only must not emit a winner")
    if set(md["synthesis"].get("live_hypotheses") or []) != {"cache", "deploy"}:
        return fail("synthesis must keep both live hypotheses")

    # Same ballots, two procedures: fingerprints match, so not participants.
    same_fp = S.ballot_fingerprint(diag)
    if same_fp != md["ballot_fingerprint"]:
        return fail("fingerprint drift inside methods_disagree")
    print(f"diagnosis_ballot_fp={same_fp} attribution=method")

    sd = S.methods_disagree(scalar)
    held = sd["vote"].get("held_values")
    mean = sd["vote"].get("manufactured_scalar")
    print(
        f"scalar disagree={sd['disagree']} reason={sd['reason']} "
        f"mean={mean} held={held} mean_in_held={mean in set(held or [])}"
    )
    if not sd["disagree"] or sd["reason"] != "method":
        return fail("scalar mean must disagree with every held estimate")
    if mean != 40.0:
        return fail(f"expected mean 40.0, got {mean}")

    # Participant control: mutated ballots vs original, same procedure (vote).
    reason_p = S.attribute_reason(diag, mutated)
    print(f"mutated_vs_original reason={reason_p}")
    if reason_p != "participants":
        return fail("mutated ballots must attribute to participants, not method")
    if S.ballot_fingerprint(diag) == S.ballot_fingerprint(mutated):
        return fail("mutated fixture must change the ballot fingerprint")

    # If the design note exists, check local structure. Do not fetch the
    # catalog shim's ast-integrate.invalid $ref (RefResolutionError on this host).
    note_path = REPO / NOTE
    if note_path.is_file():
        import note_schema as NS  # noqa: E402

        text = note_path.read_text(encoding="utf-8")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError as exc:
            return fail(f"note unparseable {exc}")
        if not isinstance(doc, dict):
            return fail("note is not an object")
        if not NS.rejects_garbage():
            return fail("local note schema accepted garbage")
        errs = NS.iter_errors(doc)
        if errs:
            return fail(f"note schema errors {errs[0]}")
        if "SUCCESS:CNL-0057" not in text:
            return fail("sentinel absent from note")
        shim = REPO / SCHEMA
        if not shim.is_file():
            return fail(f"catalog output_schema missing {SCHEMA}")
        print("note_present=True schema_ok=True sentinel=SUCCESS:CNL-0057")
    else:
        print("note_present=False (pre-emit)")

    print(
        "method_not_participants=True "
        "vote_hides_minority=True "
        "mean_manufactures_unheld_scalar=True"
    )
    print("SUCCESS:CNL-0057-probe1 method disagreement attributed to method")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
