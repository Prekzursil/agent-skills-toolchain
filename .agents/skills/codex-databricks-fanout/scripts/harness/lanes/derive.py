"""Derive lane: re-adjudicate an existing finding against CURRENT code, on the 48-wide rail.

Why this exists rather than more local agents: the local Claude fan-out measured ~37 min
per result at width 7 (~0.1 results/min across two workflows), which put 218 remaining
units at roughly 37 hours. The same work as Codex units on Databricks runs 48 wide, off-box,
so neither RAM pressure nor a session death touches it.

READ-ONLY by construction: a derive unit adjudicates, it never edits. Patching stays local
and behind an adversarial gate, because two agent recommendations have already been wrong
on this estate.
"""

from __future__ import annotations

from harness.contract import SKELETON, Unit
from harness.lanes.coverage import _slug  # one slug impl, not three

TOOLCHAIN = "https://github.com/Prekzursil/agent-skills-toolchain.git"
HARNESS_BUNDLE = "/dbfs/tmp/R-research/src/harness.tgz"
CORPUS = "harness-sota-2026-07-18-corpus"


def derive_units(entries) -> list[Unit]:
    """One unit per corpus item. `entries` come from the deterministic pre-pass:
    {id, targets[], stale_targets[]}."""
    units: list[Unit] = []
    for e in entries:
        uid = f"D-{_slug(e['id'])}"
        targets = list(e.get("targets") or [])
        stale = list(e.get("stale_targets") or [])
        stale_note = ""
        if stale:
            stale_note = (
                f"\nSTALE WARNING: {', '.join(stale)} HAS CHANGED on main since the corpus "
                f"was written. Re-derive this finding from scratch against today's code; do "
                f"NOT apply it on trust. A prior 1582-finding audit on this estate was 19 "
                f"commits stale by the time anyone read it, and verify-before-fix was the "
                f"single highest-value move.\n"
            )

        # Two finding sources: SOTA corpus docs live in the toolchain repo; Program R
        # findings live in per-file briefs shipped to DBFS. Same adjudication either way —
        # but send a brief-backed unit to the corpus and it clones a repo, finds no such
        # document, and reports nothing.
        brief = e.get("brief")
        if brief:
            source = (
                f"  Your findings are in the brief at {brief} — read it first.\n"
                f"  `git clone --depth 1 {TOOLCHAIN} /tmp/tc` for the targets it names."
            )
        else:
            source = (
                f"  `git clone --depth 1 {TOOLCHAIN} /tmp/tc` — the corpus document is\n"
                f"  then at /tmp/tc/{CORPUS}/{e['id']}.md and most targets are under /tmp/tc/."
            )

        prompt = f"""Re-adjudicate ONE finding from a nine-day-old audit against CURRENT code.

Corpus unit: {e["id"]}
Targets it audits: {", ".join(targets) or "(none resolved)"}
{stale_note}
FETCH:
{source}
  The live harness is NOT in that repo; if a target starts with `harness/`, get it from
  `mkdir -p /tmp/src && cp {HARNESS_BUNDLE} /tmp/src/ && cd /tmp/src && tar xzf harness.tgz`.

THIS UNIT IS READ-ONLY. Adjudicate only. NEVER edit a file, NEVER commit, NEVER push,
NEVER open a PR. There is no write token on this node by design.

WRITE-AS-YOU-GO: write your artifact IMMEDIATELY as a skeleton with every field set to the
exact string '{SKELETON}', then rewrite at each milestone.

The final 'UNIT-COMPLETE: {uid}' line is NOT one of those fields and must NEVER be
skeletonised. It is the completion marker: write it VERBATIM with the unit id, only once
the report above it is real. Measured 2026-07-26: a unit that had produced four VERIFIED
findings still wrote 'UNIT-COMPLETE: {SKELETON}' and the harvest gate discarded it —
complete work thrown away on the one line that says it is complete.

DO:
1. Read the corpus document and extract the concrete defect claim(s) it makes about our code.
2. Open the CURRENT source at each cited anchor. Anchors may have drifted; if so, locate the
   construct by name and say the anchor moved.
3. Choose ONE verdict:
     STILL_TRUE      - the defect is present in today's code. Give the concrete failure:
                       specific input or state -> wrong outcome, from code you actually read.
                       Run a cheap probe where you can and quote its real output.
     ALREADY_FIXED   - it was real but current code handles it. Show the guard.
     NOT_A_DEFECT    - the claim misreads the code, or the construct is deliberate and
                       documented. Say which.
     STALE_REDERIVED - the target changed so much the finding no longer maps; say what you
                       found instead.
     UNCLEAR         - only if you cannot tell without running something you must not run.
4. ALREADY_FIXED and NOT_A_DEFECT are VALUABLE results, not failures. A nine-day-old audit
   should produce plenty of both. Do not manufacture a defect to look productive.
5. Set actionable: true ONLY for STILL_TRUE backed by a concrete failure.

CONFIDENCE vocab inline: VERIFIED / LIKELY / INFERRED / CONTRADICTED / UNKNOWN.
An anchor you did not actually open is a fabrication — omit it instead.

ARTIFACT (write to your -o path, AT LEAST 1200 bytes — a terse report falls under the
harvest floor and is discarded. MUST contain these fields and END with the sentinel):
  unit: {e["id"]}
  verdict: <STILL_TRUE|ALREADY_FIXED|NOT_A_DEFECT|STALE_REDERIVED|UNCLEAR>
  severity: <critical|high|medium|low|none>
  evidence: <the concrete failure, or the guard that prevents it>
  targets: {", ".join(targets) or "none"}
  actionable: <true|false>
UNIT-COMPLETE: {uid}
"""
        units.append(
            Unit(
                id=uid,
                lane="derive",
                prompt=prompt,
                artifact=f"/dbfs/tmp/R-derive/results/{uid}.md",
                meta={"corpus_id": e["id"], "targets": targets, "stale": stale},
            )
        )
    return units
