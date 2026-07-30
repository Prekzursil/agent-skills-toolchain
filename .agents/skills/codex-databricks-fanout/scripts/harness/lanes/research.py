"""Program R lane: autonomous research fan-out over the harness + toolchain.

One Unit per (target x lens) cell. Unlike the coverage lane these units are READ-ONLY:
they analyse, cite, and recommend — they never commit, never push, never open a PR.
The durable output is the artifact itself, so there is no patch to export.
"""

from __future__ import annotations

import re

from harness.contract import SKELETON, Unit

# The lens is what stops 500 units from being 500 copies of "find bugs". Each carries a
# genuinely different question, so two units on the same file still return different
# information. Order is fixed: the wave cap must truncate deterministically.
LENSES: dict[str, str] = {
    "bugs": "Correctness defects: wrong logic, unhandled error paths, silent failures, "
    "races, and any place a detector reports success without measuring anything.",
    "security": "Secret handling, injection, path traversal, unsafe deserialisation, "
    "over-broad permissions, and trust placed in fetched or repo-supplied data.",
    "cross-session": "State shared between concurrent sessions or agents: global files, "
    "last-writer-wins slots, unscoped caches. Who writes it, who reads it, "
    "and whether one session's state can steer another's.",
    "test-gaps": "Behaviour with no test, tests that assert nothing, and gates that would "
    "stay silent in their own known-broken state.",
    "performance": "Startup cost, context bloat, redundant work, unbounded growth, and any "
    "file or buffer that grows without rotation.",
    "api-design": "Confusing interfaces, footgun defaults, arguments whose omission changes "
    "semantics dangerously, and naming that invites misuse.",
    "new-venues": "Capabilities this project does NOT have yet that a peer project of this "
    "maturity would: name the specific upstream tool, API, or pattern and what "
    "adopting it would concretely buy.",
    "architecture": "Cross-cutting structure: coupling, duplicated responsibility, layering "
    "violations, and consolidation that would remove whole classes of bug.",
}


HARNESS_BUNDLE = "/dbfs/tmp/R-research/src/harness.tgz"
TOOLCHAIN_REMOTE = "https://github.com/Prekzursil/agent-skills-toolchain.git"


def _slug(p: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")


def _fetch_for(target: str) -> str:
    """How the node obtains the source. The two trees differ and cannot be swapped.

    ~/.agents/harness is NOT a git repo and is NOT mirrored on the toolchain remote
    (verified 2026-07-26: `.agents/harness` absent from origin/main), so harness units
    read a DBFS bundle. Telling them to clone would research an empty path.
    """
    if target.startswith("harness/"):
        return (
            f"FETCH: `mkdir -p /tmp/src && cp {HARNESS_BUNDLE} /tmp/src/ && cd /tmp/src "
            f"&& tar xzf harness.tgz` — your target is then at /tmp/src/{target}. This "
            f"tree is canonical local source with no git remote; there is nothing to clone."
        )
    rel = target.split("/", 1)[1] if "/" in target else target
    return (
        f"FETCH: `git clone --depth 1 {TOOLCHAIN_REMOTE} /tmp/src` — your target is then "
        f"at /tmp/src/{rel}. Read it from the clone, not from any local checkout."
    )


def research_units(targets, lenses) -> list[Unit]:
    """One read-only Unit per (target, lens). Target-major so the order is stable."""
    units: list[Unit] = []
    for t in targets:
        for lens in lenses:
            uid = f"R-{_slug(t)}-{_slug(lens)}"
            question = LENSES.get(
                lens, f"Analyse the target through the '{lens}' lens."
            )
            prompt = f"""Research unit. Target: {t}. Lens: {lens}.

THIS UNIT IS READ-ONLY. Analyse and report. NEVER commit, NEVER push, NEVER open or merge a
PR, NEVER modify the target. There is no write token on this node by design (R1). Your
artifact IS the deliverable.

QUESTION ({lens}): {question}

{_fetch_for(t)}

WRITE-AS-YOU-GO: write your artifact IMMEDIATELY as a skeleton with every field set to the
exact string '{SKELETON}', then rewrite at each milestone. If it still reads that way, the
unit died before measuring and no verdict in it may be cited.

The final 'UNIT-COMPLETE: {uid}' line is NOT one of those fields and must NEVER be
skeletonised. It is the completion marker, so write it VERBATIM as shown, with the unit id,
and only once the report above it is real. Measured 2026-07-26: a unit that had produced
four VERIFIED findings still wrote 'UNIT-COMPLETE: {SKELETON}' and was discarded by the
harvest gate — complete work, thrown away on the one line that says it is complete.

DO:
1. Read {t} and enough of its callers to judge it in context. Reading a symbol's definition
   is not the same as reading its uses — check both before claiming behaviour.
2. For every finding, give a concrete failure scenario: specific input or state -> wrong
   outcome. A finding you cannot make fail is a hypothesis, and must be labelled one.
3. Prefer a finding you can demonstrate from the source over one that merely sounds right.
   If a claim rests on something you did NOT open, say so explicitly.
4. Rank findings by severity. Do not pad: three real defects beat twenty restatements of
   the code's own structure.

CONFIDENCE vocab, inline and adjacent to each claim: VERIFIED / LIKELY / INFERRED /
CONTRADICTED / UNKNOWN. Include an EVIDENCE block of 3-5 file:line anchors, exempt from any
length cap. An anchor you did not actually read is a fabrication — omit it instead.

ARTIFACT (write to your -o path at AT LEAST 1200 bytes — a terse report falls under the
harvest floor and is discarded. It MUST contain these fields and END with the sentinel):
  target: {t}
  lens: {lens}
  findings: <n>
  severity: <critical|high|medium|low|none>
  evidence: <file:line, file:line, ...>
  recommendation: <the single highest-value change, concretely stated>
  confidence: <VERIFIED|LIKELY|INFERRED|UNKNOWN>
UNIT-COMPLETE: {uid}
"""
            units.append(
                Unit(
                    id=uid,
                    lane="research",
                    prompt=prompt,
                    artifact=f"/dbfs/tmp/R-research/results/{uid}.md",
                    meta={"target": t, "lens": lens},
                )
            )
    return units


def plan_wave(targets, lenses, cap=None) -> tuple[list[Unit], int]:
    """Build the full matrix, then truncate to `cap`.

    Returns (units, dropped). The dropped count is returned rather than swallowed so the
    caller can log it — a silent cap reads as full coverage when it is not.
    """
    units = research_units(targets, lenses)
    if cap is None or cap >= len(units):
        return units, 0
    cap = max(0, int(cap))
    return units[:cap], len(units) - cap


def shard(units, size: int) -> list[list[Unit]]:
    """Split into consecutive shards of at most `size`, covering every unit exactly once.

    The R9 ceiling caps a single wave; a 500-unit programme is therefore several waves.
    """
    if size <= 0:
        raise ValueError(f"shard size must be positive, got {size}")
    return [list(units[i : i + size]) for i in range(0, len(units), size)]
