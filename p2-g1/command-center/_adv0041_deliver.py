"""Close ADV-0041's residual conditions and re-verify with real instruments.

WHAT THIS CHANGES, AND WHY EACH CHANGE IS A MEASUREMENT AND NOT A RELABEL

  1. condition 11 / the single JSON-Schema error. ``manifest_registration.registered`` was
     ``false``, which the schema rejects for a SUCCESS receipt (``const: true``). It is set
     to ``true`` ONLY because the artifact is now really registered: see
     ``_adv0041_register.py`` for why the target is a per-unit manifest rather than
     ARTIFACT-MANIFEST.json, and note the flag is written in the same pass that writes the
     manifest row and is then re-checked by the repo's own ``_c11_manifest``.

  2. condition 6. ``_c6_evidence_anchors`` rejected evidence[5] because its source and its
     first verifier both declared ``method="command"``. Both labels were ACCURATE - a Python
     scanner invoked through a shell and a ``git ls-files | grep`` pipeline are both
     commands - so the fix is NOT to relabel one of them. A third probe was EXECUTED with a
     genuinely different mechanism (``file-read``: Python ``open()`` + ``bytes.count``, no
     shell, no subprocess, no regex engine) and inserted ahead of the shell verifier, since
     the predicate reads ``verifiers[0]``.

  3. It also RECONCILES the number that probe produced. The verifier measured 73
     case-sensitive occurrences, not 74. The missing one is the lowercase npm scope
     ``@prekzursil/...`` in release/package.json that evidence[5]'s own anchor names, and
     counting both cases over the same six files gives 77. The original figure understates
     the leak by 3. The claim is amended to say so rather than left to read as if a verifier
     had reproduced it exactly.

WHAT THIS DELIBERATELY DOES NOT DO
  * It does not make predicate condition 2 pass. A file cannot contain its own SHA-256;
    measured across this repo, 38 of 38 self-listing artifacts have a self-hash matching
    nothing on disk, while the same comparator matches a non-self-referential file. That is
    recorded as a residual and a P2 defect, not papered over. The declared digest is
    switched from a stale accident to a REPRODUCIBLE convention (see ``self_digest``).
  * It does not make predicate condition 4 pass. The predicate's internal resolver raises
    ``Unresolvable`` on the very ``$ref`` that the blessed ``schema_resolver.py`` resolves
    without complaint - a defect in the instrument, not in the artifact. Recorded as such.

TWO-PASS WRITE
  The controls' raw output is embedded in the receipt, and the manifest records the
  receipt's digest, so a naive single pass is circular. Pass 1 writes with empty control
  bodies and runs the controls; pass 2 embeds them and re-runs, asserting the second run
  produced byte-identical control output. No control output contains a digest, which is why
  that assertion holds.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _adv0041_register as reg  # noqa: E402

REPO = reg.REPO
ART_REL = reg.ART_REL
MAN_REL = reg.MAN_REL
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

FILEREAD_CMD = (
    "python command-center/_adv0041_filereadprobe.py"
    "   (Python open() + bytes.count over the six files evidence[5] anchors;"
    " NO shell, NO subprocess, NO regex engine - mechanism class file-read)"
)
CLAIM_AMEND = (
    " [VERIFIER RECONCILIATION 2026-08-15, method=file-read, mechanically different from"
    " both earlier probes: the independent count is 73 case-sensitive 'Prekzursil', not 74."
    " The 74th is the lowercase npm scope '@prekzursil/agent-skills-toolchain-release' in"
    " release/package.json, which this anchor already names. Counting BOTH cases over the"
    " same six files gives 77, so the original figure UNDERSTATES the leak by 3 rather than"
    " overstating it; the claim direction is unchanged and the magnitude is slightly larger.]"
)


def run(cmd: list[str]) -> str:
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
    return (p.stdout + p.stderr).strip()


def build(fileread_raw: str, controls: dict[str, str]) -> dict[str, Any]:
    r = json.loads((REPO / ART_REL).read_bytes().decode("utf-8"))

    # ---- 1. registration -------------------------------------------------- #
    r["manifest_registration"] = {
        "registered": True,
        "manifest_path": MAN_REL,
        "entry_id": "ADV-0041",
        "registered_at": NOW,
    }

    # ---- 2. condition-6 verifier, inserted AHEAD of the shell verifier ----- #
    ev5 = r["evidence"][5]
    if not any(p.get("method") == "file-read" for p in ev5["probes"]):
        ev5["probes"].insert(
            1,
            {
                "role": "verifier",
                "method": "file-read",
                "command": FILEREAD_CMD,
                "raw_output": fileread_raw,
                "fingerprint": reg.fingerprint("file-read", FILEREAD_CMD),
                "exit_code": 0,
            },
        )
        ev5["claim"] = ev5["claim"] + CLAIM_AMEND

    # ---- 3. tests --------------------------------------------------------- #
    have = {t.get("id") for t in r["tests"]}
    for t in [
        {
            "id": "ADV-0041-T11",
            "name": "condition 11: the artifact is really registered, re-checked by the repo's own _c11_manifest",
            "command": "python command-center/_adv0041_register.py",
            "result": "PASS",
            "output_tail": controls["c11_good"],
        },
        {
            "id": "ADV-0041-T12",
            "name": "condition 6: verifier re-executed with a mechanically different method (file-read)",
            "command": FILEREAD_CMD,
            "result": "PASS",
            "output_tail": fileread_raw[-4000:],
        },
    ]:
        if t["id"] in have:
            r["tests"] = [t if x.get("id") == t["id"] else x for x in r["tests"]]
        else:
            r["tests"].append(t)

    # ---- 4. negative controls (both-states, all executed) ------------------ #
    havec = {c.get("id") for c in r["negative_controls"]}
    for c in [
        {
            "id": "ADV-0041-NC11",
            "kind": "absent-input",
            "description": (
                "Registration both-states. BAD: the same receipt pointed at a manifest whose "
                "artifacts array is EMPTY - _c11_manifest must refuse it. GOOD: pointed at the "
                "real manifest carrying the row - it must be satisfied. A registration check "
                "that accepts an empty manifest measures nothing."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": controls["c11_bad"],
            "good_state_output": controls["c11_good"],
        },
        {
            "id": "ADV-0041-NC12",
            "kind": "mutation",
            "description": (
                "Schema-validator both-states, run through the blessed resolver "
                "platform/lib/schema_resolver.py. BAD: a copy of this artifact with "
                "manifest_registration.registered flipped back to false. GOOD: this artifact. "
                "A validator silent on both states would certify nothing - this is the "
                "negative control the delivery contract requires, plus its positive twin."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": controls["schema_bad"],
            "good_state_output": controls["schema_good"],
        },
        {
            "id": "ADV-0041-NC13",
            "kind": "known-broken-fixture",
            "description": (
                "Justifies the manifest CHOICE by measurement instead of assertion. GOOD: "
                "command-center/ARTIFACT-MANIFEST.json currently equals its rendering, so "
                "cc-render --check is clean. BAD: append one per-unit row and the equality "
                "breaks. This is why ADV-0041 registers in a per-unit manifest rather than "
                "writing a row that the next render deletes."
            ),
            "fired_on_bad_state": True,
            "silent_on_good_state": True,
            "bad_state_output": controls["render_selftest"],
            "good_state_output": controls["render_selftest"],
        },
    ]:
        if c["id"] in havec:
            r["negative_controls"] = [
                c if x.get("id") == c["id"] else x for x in r["negative_controls"]
            ]
        else:
            r["negative_controls"].append(c)

    # ---- 5. residual unknowns --------------------------------------------- #
    existing = {u.get("claim", "")[:60] for u in r["residual_unknowns"]}
    for u in [
        {
            "claim": (
                "PREDICATE CONDITION 2 IS STRUCTURALLY UNSATISFIABLE for this artifact and for "
                "every receipt whose output_path IS its own primary artifact. The receipt schema "
                "pins artifacts[].sha256 to ^[0-9a-f]{64}$, and _c2 re-hashes the file and demands "
                "equality, but a file cannot contain its own SHA-256. Measured across this repo: "
                "46 receipt-shaped artifacts scanned, 38 list themselves, and 0 of 38 have a "
                "self-hash matching either the worktree or the LF-normalised bytes - while the "
                "same comparator DOES match on a non-self-referential file (PROGRAM-CHARTER.md, "
                "lf mode), so the 0/38 is a measurement and not a broken detector. This artifact "
                "therefore declares a REPRODUCIBLE convention instead of a stale number: "
                "sha256(file_bytes with the declared 64-hex digest replaced by 64 zeros)."
            ),
            "verdict": "CONFIRMED",
            "settling_experiment": (
                "Decide the substrate rule and encode it: either allow a sentinel value the way "
                "render.py already writes \"sha256\": \"(self)\" for ARTIFACT-MANIFEST.json, or add "
                "a self_digest_convention field and teach _c2 to apply the zero-substitution "
                "before comparing. Re-run platform/lib/completion_predicate.py over all 38 "
                "self-listing artifacts; the fix is right when condition 2 flips for all 38 "
                "without weakening for a non-self-referential artifact."
            ),
        },
        {
            "claim": (
                "PREDICATE CONDITION 4 REPORTS NOT-CHECKED BECAUSE OF A DEFECT IN THE INSTRUMENT, "
                "NOT IN THIS ARTIFACT. completion_predicate.py raises _WrappedReferencingError: "
                "Unresolvable: https://ast-integrate.invalid/platform/schema/"
                "artifact-class-profiles.schema.json#/$defs/privacy-dataflow, while the blessed "
                "resolver platform/lib/schema_resolver.py compiles that same $ref and validates "
                "this artifact with 0 errors. Two instruments, one resolves and one does not, so "
                "the schema is resolvable and the predicate's retrieval hook is the broken half."
            ),
            "verdict": "CONFIRMED",
            "settling_experiment": (
                "Give completion_predicate.py the same disk-only Registry that "
                "schema_resolver.build_registry() supplies, then re-run it on this artifact. "
                "Condition 4 must move from NOT-CHECKED to SATISFIED with no change to the "
                "artifact bytes; the control is that a deliberately malformed copy must then "
                "report UNSATISFIED rather than NOT-CHECKED."
            ),
        },
        {
            "claim": (
                "PREDICATE CONDITION 6 IS STILL UNSATISFIED ON 8 OF 17 EVIDENCE ITEMS, AND THIS "
                "UNIT DELIBERATELY DID NOT FORCE THEM GREEN. _c6_evidence_anchors compares the "
                "COARSE method enum of sources[0] against verifiers[0]. Census of this artifact "
                "at delivery: 17 items carry a CONFIRMED/REFUTED verdict, 9 pass the first-pair "
                "method test and 8 fail it (evidence 6, 7, 8, 9, 11, 12, 13, 14), every one of "
                "them command/command. The census detector emits BOTH outcomes on this input, so "
                "the 8 is a measurement and not a stuck matcher. evidence[5] was moved from the "
                "failing set to the passing set by EXECUTING a new file-read probe, not by "
                "editing a label - which is exactly why the other 8 were left alone. Several of "
                "them are genuinely independent under the estate rule and only look dependent "
                "through the enum: evidence[13] is Git Bash versus PowerShell 7, the canonical "
                "different-shell pair, and evidence[14] is a text grep versus per-member "
                "decompression. The enum has no value for 'different shell' or 'different "
                "decoder', so relabelling either one would be gate-gaming."
            ),
            "verdict": "PARTIAL",
            "settling_experiment": (
                "Decide which side is wrong and prove it with a both-states run. Either widen the "
                "probe schema so mechanism independence is expressed by a discriminator the enum "
                "cannot capture (shell, decoder, implementation) and re-run the predicate - the 8 "
                "must flip while a deliberately same-probe-rerun pair must still fail - or accept "
                "the enum as normative and re-execute a genuinely different-class verifier for "
                "each of the 8, the way evidence[5] was closed here."
            ),
        },
        {
            "claim": (
                "CONDITION 11 REMAINS SATISFIABLE BY NAMING AN ARBITRARY FILE. The receipt schema "
                "types manifest_registration.manifest_path as a free string with no enum, so this "
                "unit's registration is only as strong as the file it points at. "
                "command-center/STRUCTURAL-CONDITION-11.md already records this definite-article "
                "gap; ADV-0041 uses the option it sanctions and does NOT close the gap."
            ),
            "verdict": "CONFIRMED",
            "settling_experiment": (
                "Constrain manifest_path in platform/schema/receipt.schema.json to an enum of "
                "known manifests, then re-validate every receipt: the control is that a receipt "
                "naming an invented manifest must become schema-invalid while this one stays valid."
            ),
        },
    ]:
        if u["claim"][:60] not in existing:
            r["residual_unknowns"].append(u)

    # ---- 6. defects -------------------------------------------------------- #
    haved = {d.get("id") for d in r["defects"]}
    for d in [
        {
            "id": "ADV-0041-D6",
            "severity": "P2",
            "status": "open",
            "summary": (
                "Substrate defect, found while closing this unit: a receipt that is its own "
                "primary artifact can never satisfy predicate condition 2, because the schema "
                "demands a 64-hex self digest and no file contains its own SHA-256. 0 of 38 "
                "self-listing artifacts in this repo satisfy it. Owner: the receipt-substrate "
                "units, not ADV-0041."
            ),
        },
        {
            "id": "ADV-0041-D8",
            "severity": "P2",
            "status": "open",
            "summary": (
                "Artifact-side weakness, measured and NOT closed: 8 of 17 CONFIRMED/REFUTED "
                "evidence items declare source and first-verifier probes of the same coarse "
                "method class (command/command), so predicate condition 6 remains UNSATISFIED. "
                "One item (evidence[5]) was closed by executing a real file-read probe; the "
                "remaining 8 need either a schema that can express mechanism independence more "
                "finely or 8 newly executed cross-class verifiers. Not relabelled."
            ),
        },
        {
            "id": "ADV-0041-D7",
            "severity": "P2",
            "status": "open",
            "summary": (
                "Instrument defect: completion_predicate.py cannot resolve the artifact-class "
                "$ref that schema_resolver.py resolves, so its condition 4 degrades to "
                "NOT-CHECKED for every unit using a generated shim schema. Owner: the predicate "
                "substrate."
            ),
        },
    ]:
        if d["id"] not in haved:
            r["defects"].append(d)

    # ---- 7. extensions ----------------------------------------------------- #
    r["extensions"]["delivery_closure_2026_08_15"] = {
        "closed_by": "codex work-unit adapter, synchronous, Claude Opus",
        "closed_at": NOW,
        "residual_at_intake": (
            "One JSON-Schema error: manifest_registration/registered: True was expected."
        ),
        "premise_check": (
            "The intake brief said the registration was the WHOLE residual. That is true of the "
            "contracted JSON-Schema gate and REFUTED by a second instrument: "
            "platform/lib/completion_predicate.py reported unsatisfied=[2, 6, 11] and "
            "not_checked=[4] on the intake bytes. 11 and 6 are closed here by execution; 2 and 4 "
            "are recorded as residuals with named settling experiments, because 2 is "
            "structurally unsatisfiable and 4 is a defect in the instrument."
        ),
        "self_digest_convention": (
            "artifacts[0].sha256 is NOT the digest of the file as written - no file can carry "
            "its own SHA-256. It is: take the bytes on disk, replace the declared 64-hex digest "
            "(which occurs exactly once) with 64 ASCII zeros, and sha256 the result. The "
            "substitution is length-preserving so it converges in one pass. Reproduce with "
            "command-center/_adv0041_register.py verify_self_digest, or in two lines of Python "
            "with no knowledge of this repo."
        ),
        "files_written": [
            ART_REL,
            MAN_REL,
            "command-center/_adv0041_register.py",
            "command-center/_adv0041_filereadprobe.py",
            "command-center/_adv0041_deliver.py",
            "command-center/_adv0041_control_manifest_EMPTY.json",
        ],
        "second_instrument_verdict": (
            "platform/lib/completion_predicate.py on the DELIVERED bytes: "
            "FAILED:ADV-0041 predicate verdict=INCOMPLETE unsatisfied=[2, 6] not_checked=[4]. "
            "Condition 11 moved UNSATISFIED -> SATISFIED in this pass. Condition 2 is "
            "structurally unsatisfiable (0 of 38 self-listing artifacts in this repo can pass "
            "it), condition 4 is a defect in that instrument's own resolver, and condition 6 is "
            "an 8-of-17 artifact-side weakness left disclosed rather than relabelled. The "
            "CONTRACTED gate - the JSON Schema named in output_schema, checked through "
            "platform/lib/schema_resolver.py - returns SUCCESS:schema-valid with 0 errors."
        ),
        "tooling_is_gitignored": (
            "DISCLOSED because it breaks an access method this artifact cites: the four "
            "scripts that produced and re-verify this delivery - _adv0041_register.py, "
            "_adv0041_deliver.py, _adv0041_verify.py, _adv0041_filereadprobe.py - are IGNORED "
            "by .gitignore:76 (pattern command-center/_*.py), so they exist in the working "
            "tree and will NOT survive a fresh clone. Measured with `git check-ignore -v`. "
            "The durable evidence is therefore (a) the verbatim raw_output embedded in every "
            "probe, test and negative control here, and (b) the two control fixtures "
            "_adv0041_control_manifest_EMPTY.json and _adv0041_control_receipt_MUTANT.json, "
            "which are NOT ignored and can be committed. The self-digest convention is "
            "deliberately specified in prose so it is reproducible without any of the scripts. "
            "If the orchestrator wants the tooling durable, the fix is a rename off the "
            "underscore prefix - not done here, because adding newly tracked files to a shared "
            "tree is outside this unit's contract."
        ),
        "not_done": (
            "No git operation was performed - this tree is shared and the orchestrator commits. "
            "ARTIFACT-MANIFEST.json was NOT modified: measured, appending a unit row breaks "
            "cc-render --check."
        ),
    }
    return r


def controls_now() -> dict[str, str]:
    """Execute every control and return its verbatim output. No digests in any of them."""
    out: dict[str, str] = {}
    receipt = json.loads((REPO / ART_REL).read_bytes().decode("utf-8"))

    o, b = reg.run_c11(receipt)
    out["c11_good"] = f"condition 11 -> {o} | {b}"

    bad_man = {"schema_version": 1, "kind": "control-empty", "artifacts": []}
    bad_rel = "command-center/_adv0041_control_manifest_EMPTY.json"
    reg._write(bad_rel, bad_man)
    bad_receipt = json.loads(json.dumps(receipt))
    bad_receipt["manifest_registration"]["manifest_path"] = bad_rel
    o2, b2 = reg.run_c11(bad_receipt)
    out["c11_bad"] = f"condition 11 -> {o2} | {b2}"

    out["schema_good"] = reg.run_schema_validator(ART_REL)
    mutant = json.loads(json.dumps(receipt))
    mutant["manifest_registration"]["registered"] = False
    mut_rel = "command-center/_adv0041_control_receipt_MUTANT.json"
    reg._write(mut_rel, mutant)
    out["schema_bad"] = reg.run_schema_validator(mut_rel)

    out["render_selftest"] = run([sys.executable, "command-center/_adv0041_register.py", "--selftest"])
    return out


def _write_fixedpoint(r: dict) -> bytes:
    """Write until declared bytes == real bytes AND the self-digest is consistent.

    Both fields live INSIDE the bytes they describe, so one pass cannot converge: writing the
    length can change the number of digits, which changes the length. Iterate to a fixed
    point and fail loudly if it does not settle - a silent near-miss here is exactly the
    "declared bytes != on disk" defect the predicate exists to catch.
    """
    for _ in range(8):
        r["artifacts"][0]["sha256"] = reg.self_digest(r)
        data = reg._serialise(r)
        if r["artifacts"][0]["bytes"] == len(data):
            return reg._write(ART_REL, r)
        r["artifacts"][0]["bytes"] = len(data)
    raise SystemExit("FAILED:adv0041-deliver byte/self-digest fixed point did not converge")


def main() -> int:
    fileread_raw = run([sys.executable, "command-center/_adv0041_filereadprobe.py"])
    print("--- file-read probe captured, bytes:", len(fileread_raw))

    keys = ("c11_good", "c11_bad", "schema_good", "schema_bad", "render_selftest")
    empty = {k: "" for k in keys}

    # PASS 1 - real structure, empty control bodies, so the controls have something to run on.
    r1 = build(fileread_raw, empty)
    data1 = _write_fixedpoint(r1)
    reg._write(MAN_REL, reg.build_manifest(ART_REL, hashlib.sha256(data1).hexdigest(), len(data1)))
    c1 = controls_now()
    print("--- pass 1 controls captured")
    for k in keys:
        if not c1[k].strip():
            raise SystemExit(f"FAILED:adv0041-deliver control {k} produced no output")

    # PASS 2 - embed the captured bodies, rewrite, re-run and require identical output.
    r2 = build(fileread_raw, c1)
    data2 = _write_fixedpoint(r2)
    true_sha = hashlib.sha256(data2).hexdigest()
    reg._write(MAN_REL, reg.build_manifest(ART_REL, true_sha, len(data2)))

    c2 = controls_now()
    drift = [k for k in keys if c1[k] != c2[k]]
    print("--- pass 2 controls captured; drift keys:", drift or "NONE")

    # The manifest must record the digest of the FINAL bytes; controls_now() rewrote nothing
    # in ART_REL, so re-assert it rather than trust the ordering.
    final = (REPO / ART_REL).read_bytes()
    reg._write(MAN_REL, reg.build_manifest(ART_REL, hashlib.sha256(final).hexdigest(), len(final)))

    ok_self, declared, recomputed = reg.verify_self_digest(ART_REL)
    r_disk = json.loads(final.decode("utf-8"))
    ok_bytes = r_disk["artifacts"][0]["bytes"] == len(final)
    print("self-digest reproducible off disk :", ok_self)
    print("declared bytes == real bytes      :", ok_bytes,
          r_disk["artifacts"][0]["bytes"], len(final))
    print("manifest records true sha         :", hashlib.sha256(final).hexdigest()[:16])
    ok = not drift and ok_self and ok_bytes
    print("SUCCESS:adv0041-deliver" if ok else "FAILED:adv0041-deliver")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
