"""Program E lane: one Unit per uncovered-file gap. The unit writes tests, runs the REAL suite,
commits a LOCAL agent/ branch ONLY on green (no push — the node has no write token, R1)."""

from __future__ import annotations
import re
from harness.contract import Unit, SKELETON


def _slug(p):
    return re.sub(r"[^a-z0-9]+", "-", p.lower()).strip("-")


def coverage_units(repo, gaps):
    units = []
    for g in gaps:
        f, lines = g["file"], g["uncovered"]
        uid = f"E-{repo}-{_slug(f)}"
        branch = f"agent/{uid}"
        prompt = f"""Coverage unit for repo {repo}. Clone it, work on a fresh branch.
TARGET FILE: {f}
UNCOVERED lines/branches: {lines}

WRITE-AS-YOU-GO: write your report artifact IMMEDIATELY as a skeleton with every field marked the
exact string '{SKELETON}', plus a 'COVERAGE:' line naming which sections are unmeasured, then
rewrite at each milestone. If it still reads this way, the unit died before measuring anything and
no verdict here may be cited.

DO:
1. Identify why {lines} in {f} are uncovered.
2. Write tests exercising exactly those lines/branches.
3. Run the repo's REAL suite + coverage. Gate = suite GREEN and those lines now covered.
   If red or no improvement: FAILED, commit NOTHING.
4. On green ONLY: commit to a LOCAL branch {branch} (scoped add, never -A), and record its sha.
   Do NOT push — there is no token on the node (R1).
   NEVER main, NEVER an existing branch, NEVER open/merge a PR, NEVER force.
5. EXPORT the commit so it outlives this node, which is ephemeral and takes your branch with it:
   `mkdir -p /dbfs/tmp/E-coverage/patches && git format-patch -1 --stdout > /dbfs/tmp/E-coverage/patches/{uid}.patch`
   Verify it is non-empty; if the export fails, say so and set patch_file: none. A commit that is
   only a local sha is LOST work — the artifact records the claim, the patch carries the change.

CONFIDENCE vocab, inline and adjacent to each claim: VERIFIED / LIKELY / INFERRED / CONTRADICTED /
UNKNOWN. EVIDENCE block of 3-5 file:line anchors, exempt from any length cap.

ARTIFACT (write to your -o path at AT LEAST 1200 bytes -- do NOT stop short; a terse report falls
under the harvest floor and is discarded. It MUST contain these fields and END with the sentinel):
  file: {f}
  uncovered_before: {lines}
  tests_added: <n>
  suite_status: <green|red>
  coverage_after: <number>
  branch_ready: <{branch}@<local-sha> or none>
  patch_file: </dbfs/tmp/E-coverage/patches/{uid}.patch or none>
UNIT-COMPLETE: {uid}
"""
        units.append(
            Unit(
                id=uid,
                lane="coverage",
                prompt=prompt,
                artifact=f"/dbfs/tmp/E-coverage/results/{uid}.md",
                meta={"repo": repo, "file": f, "branch": branch},
            )
        )
    return units
