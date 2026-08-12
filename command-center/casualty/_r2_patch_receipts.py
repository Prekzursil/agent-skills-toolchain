r"""ROUND-2 receipt patcher: apply the audit-confirmed corrections to both receipts.

Two classes of change, and the distinction is deliberate:
  * DATA correction (ADV-0021): the spec's literal rule -- "a mitigation with no executable
    check is downgraded to unmitigated" -- was not applied to TB3/Tampering. That is a wrong
    CELL, not a wrong sentence, so the cell moves and every derived count is RECOUNTED from
    the cells rather than edited by hand.
  * SENTENCE correction: every overclaim is recorded VERBATIM as refuted alongside its
    correctly-scoped replacement. Nothing is silently deleted.

VERBATIM CAPTURES ARE NEVER EDITED. A probe's raw_output is evidence; where a capture is now
known to contain a wrong narrative line, the fix is a NEW capture from the FIXED probe added
alongside, plus a defect record -- not a rewrite of history.

Byte/digest convergence is copied from the round-1 builders so the elided self-digest recipe
published in extensions.self_digest_recipe keeps holding.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
from pathlib import Path

ROOT = Path("C:/Users/Prekzursil/source/ast-integrate")
CAS = ROOT / "command-center" / "casualty"
AUDIT_ANCHOR = (
    "command-center/casualty/_r2_audit_round1.txt (adversarial audit of build "
    "round 1, wf_e58dfd3f-7b1 journal line 65, agentId aa1e83cff63e3c2bd)"
)


def fp(method: str, command: str) -> str:
    return hashlib.md5(f"{method}|{command}".encode("utf-8"), usedforsecurity=False).hexdigest()


def emit(doc: dict, path: Path) -> str:
    """Serialize with a converged byte count and a correct elided self-digest."""
    doc["artifacts"][0]["sha256"] = "0" * 64
    for _ in range(6):
        blob = json.dumps(doc, indent=2, ensure_ascii=False)
        n = len(blob.encode("utf-8"))
        if doc["artifacts"][0]["bytes"] == n:
            break
        doc["artifacts"][0]["bytes"] = n
    blob = json.dumps(doc, indent=2, ensure_ascii=False)
    doc["artifacts"][0]["sha256"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    out = json.dumps(doc, indent=2, ensure_ascii=False)
    assert len(out.encode("utf-8")) == doc["artifacts"][0]["bytes"], (
        "byte convergence failed"
    )
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    return out


def gate(rel: str) -> str:
    r = subprocess.run(
        ["python", "platform/lib/receipt_schema_gate.py", rel, "--repo-root", "."],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    return (r.stdout + r.stderr).replace("\r\n", "\n").strip()


NORM = "<VOLATILE-ON-DISK-DIGEST>"


def normalise(text: str) -> str:
    return re.sub(r"on-disk [0-9a-f]{12}\.\.\.", f"on-disk {NORM}", text)


def capture_block(rel: str, text: str) -> str:
    return (
        f"$ python platform/lib/receipt_schema_gate.py {rel} --repo-root .\n"
        + normalise(text)
        + "\n\n[capture note] Exactly one token above is normalised: the 12-hex on-disk "
        f"digest quoted by condition 3, rendered as {NORM}. It is volatile by "
        "construction because embedding this very capture changes the file it describes. "
        "Everything else is verbatim, and the build asserts the condition vector is "
        "byte-identical before and after embedding."
    )


def converge_with_gate(doc: dict, path: Path, rel: str) -> tuple[str, str]:
    """Emit, gate, re-embed the gate capture, emit again, prove the vector did not move."""
    emit(doc, path)
    g1 = gate(rel)
    doc["downstream_consumers"][0]["probe"]["raw_output"] = capture_block(rel, g1)
    emit(doc, path)
    g2 = gate(rel)
    m1, m2 = g1.split("\n")[0], g2.split("\n")[0]
    assert m1 == m2, f"gate vector moved between phases:\n{m1}\n{m2}"
    return m2, g2


# ===========================================================================  ADV-0021
def patch_0021() -> dict:
    rel = "command-center/casualty/ADV-0021-install-path-stride-threat-model.json"
    path = ROOT / rel
    doc = json.loads(path.read_text(encoding="utf-8"))
    rep = doc["report"]
    cells = rep["stride_matrix"]

    before_counts = dict(rep["stride_status_counts"])
    target = [
        c
        for c in cells
        if c["boundary"].startswith("TB3") and c["stride"] == "Tampering"
    ]
    assert len(target) == 1, (
        f"expected exactly one TB3/Tampering cell, got {len(target)}"
    )
    cell = target[0]
    assert cell["status"] == "mitigated", f"unexpected pre-state {cell['status']!r}"
    old_status, old_disp = cell["status"], cell["disposition"]

    cell["status"] = "unmitigated"
    cell["downgraded_in_round2"] = {
        "from": old_status,
        "rule": (
            "catalog spec ADV-0021 evidence_requirement, literal text: 'Probe 2 "
            "(mechanically different): for every cell marked mitigated, execute the "
            "control's bypass attempt; a mitigation with no executable check is downgraded "
            "to unmitigated.' The control's PRESENCE was executably verified (V3 AST: "
            "safe_join called by 4 deploy functions) but its BYPASS was never executed "
            "against this boundary, so the literal rule applies."
        ),
        "refuted_wording": (
            "round 1 kept this cell at status=mitigated and the build report "
            "claimed 'Probe 2 executes the bypass for every mitigated cell ... "
            "All satisfied'. REFUTED by the adversarial audit; the code and the "
            "measurement were right and the classification was wider than the "
            "evidence."
        ),
        "audit_anchor": AUDIT_ANCHOR,
        "consequence": (
            "mitigated 2 -> 1 and unmitigated 20 -> 21. Every cell still marked "
            "mitigated now has an executed bypass attempt, so the Probe-2 clause is "
            "satisfied without qualification."
        ),
    }
    cell["disposition"] = (
        "ACCEPTED RESIDUAL (downgraded per the spec's own rule, round 2): the deploy-side "
        "safe_join is confirmed PRESENT by two independent mechanisms, but no bypass was "
        "executed against this boundary, so it is NOT claimed as mitigated. Owner impact: the "
        "deploy write path is protected only as far as inspection shows; an untested guard is "
        "an assumption, not a control. Settling experiment in residual_unknowns: extend "
        "adv0021_probe2b.py with a deploy.sync entry path containing '../' and a Windows device "
        "name and record whether safe_join raises. Previous disposition, retained verbatim so "
        "the change is auditable: " + old_disp
    )

    # --- RECOUNT everything from the cells; never hand-edit a derived number.
    counts: dict[str, int] = {}
    for c in cells:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    rep["stride_status_counts"] = counts

    needs = [c for c in cells if c["status"] in ("unmitigated", "partial")]
    undisposed = [
        c
        for c in needs
        if not str(c.get("disposition") or "").strip()
        or str(c.get("disposition")).strip().upper() == "NONE"
    ]

    # DETECTOR NOTE (round 2): the first version of this split searched the WHOLE cell object
    # for an ADV id and scored 24 named / 6 residual over unmitigated+partial. That is the
    # use-vs-mention error -- a cell whose control_anchor or bypass_result merely NAMES a
    # sibling unit is not ROUTED to it, and mixing partial cells into a count the audit made
    # over unmitigated cells is not comparable. Scoped to the disposition FIELD and reported
    # per status, it reproduces the audit's 17 exactly.
    def split(subset: list[dict]) -> tuple[list[dict], list[dict]]:
        adv = re.compile(r"ADV-\d{4}")
        nm = [c for c in subset if adv.search(str(c.get("disposition") or ""))]
        return nm, [c for c in subset if c not in nm]

    unmit_cells = [c for c in cells if c["status"] == "unmitigated"]
    part_cells = [c for c in cells if c["status"] == "partial"]
    named, residual = split(unmit_cells)
    p_named, p_residual = split(part_cells)

    closure = rep["tests_required_closure"]
    closure["cells_requiring_disposition"] = len(needs)
    closure["cells_without_disposition"] = len(undisposed)
    closure["satisfied"] = len(undisposed) == 0
    closure["routing_split_recounted_in_round2"] = {
        "detector": (
            "classified on the cell's disposition FIELD, not on the cell object -- a "
            "cell that merely NAMES a sibling unit elsewhere is not routed to it"
        ),
        "unmitigated_cells": len(unmit_cells),
        "named_follow_up_unit": len(named),
        "accepted_residual_with_owner_impact": len(residual),
        "partial_cells": len(part_cells),
        "partial_named_follow_up_unit": len(p_named),
        "partial_accepted_residual": len(p_residual),
        "total_requiring_disposition": len(needs),
        "refuted_wording": (
            "the round-1 build report said 'every unmitigated cell routed to a "
            "NAMED existing catalog unit'. REFUTED: the requirement is a "
            "DISJUNCTION (named unit OR accepted residual with owner-visible "
            "impact) and both arms are used. The receipt's own requirement "
            "string always stated the disjunction correctly; only the summary "
            "prose narrowed it."
        ),
        "audit_anchor": AUDIT_ANCHOR,
    }
    still_mitigated = [c for c in cells if c["status"] == "mitigated"]
    closure["probe2_bypass_coverage_recounted_in_round2"] = {
        "cells_still_marked_mitigated": len(still_mitigated),
        "of_which_have_an_executed_bypass_attempt": sum(
            1
            for c in still_mitigated
            if str(c.get("bypass_result") or "").strip()
            and "NOT bypassed" not in str(c.get("bypass_result"))
        ),
        "rule": "spec: a mitigation with no executable check is downgraded to unmitigated",
    }

    doc["extensions"]["round2_corrections"] = {
        "trigger": "adversarial audit of build round 1 returned PARTIAL",
        "audit_anchor": AUDIT_ANCHOR,
        "audit_finding": (
            "ALL SIX DoD ITEMS SUBSTANTIVELY HOLD UNDER MY OWN EXECUTION ... "
            "Nothing needs rebuilding. Two DoD self-assessments are stated wider "
            "than the evidence, and I found four real (minor) defects."
        ),
        "data_corrections": [
            {
                "what": "TB3/Tampering downgraded mitigated -> unmitigated per the spec's literal rule",
                "counts_before": before_counts,
                "counts_after": counts,
            }
        ],
        "sentence_corrections": [
            {
                "refuted": "every unmitigated cell routed to a NAMED existing catalog unit",
                "measured": f"{len(named)} of {len(unmit_cells)} UNMITIGATED cells route to a named "
                f"catalog unit; {len(residual)} are accepted residuals with "
                f"owner-visible impact statements (and of the {len(part_cells)} partial "
                f"cells, {len(p_named)} route to a named unit)",
                "scoped": "the unit's tests_required is a disjunction and both arms are used; "
                "cells_without_disposition remains 0, so the clause is satisfied",
            },
            {
                "refuted": "Probe 2 executes the bypass for every 'mitigated' cell ... All satisfied",
                "measured": "TB3/Tampering had no executed bypass against its own boundary",
                "scoped": "the cell is downgraded per the spec's rule; the clause is now satisfied "
                "for every cell still marked mitigated",
            },
        ],
        "unchanged_and_why": (
            "no probe was re-authored and no capture was edited. The audit "
            "independently re-executed the ADV-0021 verifier (byte-identical "
            "after EOL-normalise) and re-derived three P1 findings from the "
            "source with a different instrument."
        ),
    }

    marker, full = converge_with_gate(doc, path, rel)
    return {
        "unit": "ADV-0021",
        "rel": rel,
        "marker": marker,
        "counts_before": before_counts,
        "counts_after": counts,
        "cells": len(cells),
        "needs": len(needs),
        "named": len(named),
        "residual": len(residual),
        "undisposed": len(undisposed),
        "bytes": path.stat().st_size,
        "gate": full,
    }


# ===========================================================================  ADV-0022
def patch_0022() -> dict:
    rel = "command-center/casualty/ADV-0022-declared-permission-escape.json"
    path = ROOT / rel
    doc = json.loads(path.read_text(encoding="utf-8"))

    new_cap = (CAS / "probe-output" / "adv0022_git_verifier_out.R2.txt").read_text(
        encoding="utf-8"
    )
    ctrl = json.loads((CAS / "R2-DEFECT-CONTROLS.json").read_text(encoding="utf-8"))
    d4 = [c for c in ctrl["controls"] if c["defect"] == "D4"][0]

    existing = {d["id"] for d in doc["defects"]}
    did = next(
        f"ADV-0022-D{i}" for i in range(1, 99) if f"ADV-0022-D{i}" not in existing
    )
    doc["defects"].append(
        {
            "id": did,
            "severity": "P3",
            # enum is ['open','resolved','waived-by-owner','superseded'] -- my first attempt used
            # 'closed-in-round-2' and the gate correctly rejected the whole receipt as
            # schema-invalid. Recorded rather than quietly corrected: the gate caught me.
            "status": "resolved",
            "summary": (
                "This unit's own git verifier NARRATED a frozen pair of numbers ('a raw "
                "count matched 219 files, of which 12 were this lane's own artifacts') two "
                "lines above the lines that COMPUTE them. Measured in round 2: the stored "
                "capture computes raw=219 and excluding-lane=208, a delta of 11, not 12 - so "
                "the narrative was wrong AT CAPTURE TIME, not merely drifted, and the stray "
                "12 is the C3 block's raw count borrowed from the wrong block. A probe whose "
                "own output contradicts itself is a detector failure. FIXED: the delta is "
                "computed and printed as self_match_inflation. The load-bearing figures were "
                "always the computed ones (git_grep_exit=1 against a 289-tracked-file "
                "empty-pathspec control), so no conclusion in this receipt moves."
            ),
        }
    )

    src_cmd = "bash command-center/casualty/probes/adv0022_git_verifier.sh"
    ver_cmd = "python command-center/casualty/_r2_defect_controls.py"
    ver_raw = (
        f"[D4 control, both-states]\n"
        f"broken-state fires={d4['fires_in_broken_state']}  "
        f"fixed-state clean={d4['silent_in_fixed_state']}  "
        f"fixed tool still works={d4['fixed_tool_still_works']}\n" + d4["detail"]
    )
    doc["evidence"].append(
        {
            "claim": (
                "ROUND 2: the git-index verifier was re-run after its self-contradicting "
                "narrative line was replaced by a computed delta. Every load-bearing result "
                "reproduces on a moved HEAD: hooks/ is a populated pathspec (289 tracked "
                "files), `git grep tool_permissions -- hooks/` still exits 1 (real absence, "
                "not an empty tree), and the self-match inflation is now printed as a computed "
                "number that an independent recomputation agrees with."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/casualty/probe-output/adv0022_git_verifier_out.R2.txt",
            "probes": [
                {
                    "role": "source",
                    "method": "command",
                    "command": src_cmd,
                    "raw_output": new_cap[:65000],
                    "fingerprint": fp("command", src_cmd),
                    "exit_code": 0,
                },
                {
                    "role": "verifier",
                    "method": "byte-compare",
                    "command": ver_cmd,
                    "raw_output": ver_raw[:65000],
                    "fingerprint": fp("byte-compare", ver_cmd),
                    "exit_code": 0,
                },
            ],
        }
    )

    doc["extensions"]["round2_corrections"] = {
        "trigger": "adversarial audit of build round 1 returned PARTIAL",
        "audit_anchor": AUDIT_ANCHOR,
        "audit_confirmation": (
            "the audit INDEPENDENTLY RE-EXECUTED probes/adv0022_escape_harness.py "
            "in its own fresh %TEMP% workspace and reproduced "
            "narrow_out_of_declaration_escapes = 4 of 4 with the wide-permission "
            "control passing and detector_integrity.discriminates = true. It "
            "called this the strongest evidence in the audit."
        ),
        "defect_fixed_here": did,
        "captures_are_never_edited": (
            "the round-1 capture in evidence[] keeps its wrong narrative "
            "line verbatim because it is evidence; the correction is a "
            "NEW capture from the FIXED probe plus the defect record."
        ),
        "sentence_corrections": [
            {
                "refuted": "a raw count matched 219 files, of which 12 were this lane's own artifacts",
                "measured": "at capture time raw=219 excluding-lane=208 -> 11; today 225/208 -> 17",
                "scoped": "the delta is computed at run time and never narrated",
            },
        ],
    }

    marker, full = converge_with_gate(doc, path, rel)
    return {
        "unit": "ADV-0022",
        "rel": rel,
        "marker": marker,
        "new_defect": did,
        "evidence_items": len(doc["evidence"]),
        "defects": len(doc["defects"]),
        "bytes": path.stat().st_size,
        "gate": full,
    }


RECEIPTS = [
    "command-center/casualty/ADV-0021-install-path-stride-threat-model.json",
    "command-center/casualty/ADV-0022-declared-permission-escape.json",
]
# Pinned to the last round-1 lane commit, not HEAD: once round 2 is committed, restoring from
# HEAD would re-apply the patch to its own output (double-appending every addition and tripping
# the TB3 downgrade assertion). The assertions below fail loudly if the pin is wrong.
BASELINE = "4afce4e1"


def rebase_on_round1() -> None:
    """IDEMPOTENCE. This patcher is the only author of round-2 changes to these two files, so
    it always re-applies to the round-1 COMMITTED baseline rather than to its own output --
    otherwise a second run appends a second copy of every addition and the ADV-0021 downgrade
    assertion trips. Scoped `git checkout --` on exactly these two paths, nothing else."""
    for rel in RECEIPTS:
        r = subprocess.run(
            ["git", "checkout", BASELINE, "--", rel],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, (
            f"restore failed for {rel}@{BASELINE}: {r.stderr[:300]}"
        )
    print(
        f"rebased both receipts on their round-1 blobs at {BASELINE} (idempotent re-apply)"
    )


def main() -> int:
    rebase_on_round1()
    out = [patch_0021(), patch_0022()]
    for r in out:
        print(f"\n=== {r['unit']}  bytes={r['bytes']}")
        print(f"  gate marker: {r['marker']}")
        for k, v in r.items():
            if k not in {"unit", "rel", "marker", "bytes", "gate"}:
                print(f"  {k}: {v}")
    (CAS / "R2-RECEIPT-PATCH.json").write_text(
        json.dumps(
            {
                "generated_at_utc": __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .isoformat(),
                "results": [{k: v for k, v in r.items() if k != "gate"} for r in out],
                "gate_full": {r["unit"]: r["gate"] for r in out},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\nSUCCESS:r2-receipt-patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
