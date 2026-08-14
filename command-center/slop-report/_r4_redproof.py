"""Both-states proof for the SHELL extractor, at the level of the shipped `scan()`.

The gate reads COMMITTED bytes (`git cat-file -p HEAD:<path>`), so a synthetic document
cannot be introduced by writing a file. Instead the real `scan()` is exercised with its
reader injected -- the shipped control flow, synthetic input.

FOUR STATES, because two would not distinguish the hypotheses:

  R1 RED    a doc publishing `pwsh -File <untracked>.ps1` MUST produce a violation.
  R2 GREEN  a doc publishing `pwsh -File <tracked>.ps1` MUST NOT.
  R3 GREEN  a markdown LINK to the same untracked path MUST NOT -- mention, not use.
  R4 CONTROL the same R1 input against the PRE-CHANGE extractor set (python only) MUST
            produce NO violation. Without R4 this probe cannot tell "the widening added
            detection" from "something else was already catching it", which is exactly
            the inert-control failure this repo has measured.

Plus ATTRIBUTION of the corpus-wide command-count delta, so `347 -> 362` is measured
per-extractor instead of asserted.
"""

from __future__ import annotations

import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_published_commands as G  # noqa: E402


def run_scan_with(doc_text: str, extractors) -> list[dict]:
    """Exercise the shipped scan() over one synthetic document."""
    real_blob, real_ext = G.blob, G.EXTRACTORS
    G.blob = lambda root, path: doc_text  # noqa: ARG005
    G.EXTRACTORS = extractors
    try:
        findings, _total, _ex = G.scan(
            "unused", TRACKED, ["command-center/_r4_synthetic.md"]
        )
        return findings
    finally:
        G.blob, G.EXTRACTORS = real_blob, real_ext


root = G.repo_root()
TRACKED = {p for p in G.git(root, "ls-files").splitlines() if p}

# Sentinel generated at runtime: no committed byte can contain it, so a hit is real.
ABSENT = f"scripts/_zz_r4_absent_{uuid.uuid4().hex}.ps1"
PRESENT = "scripts/sync-skills.ps1"
assert PRESENT in TRACKED, f"fixture drift: {PRESENT} is no longer tracked"

BOTH = G.EXTRACTORS
PY_ONLY = (("python", G.CMD),)

r1 = run_scan_with(f"Deploy with `pwsh -File {ABSENT}` after review.", BOTH)
r2 = run_scan_with(f"Deploy with `pwsh -File {PRESENT}` after review.", BOTH)
r3 = run_scan_with(f"See [`../../{ABSENT}`](../../{ABSENT}) for detail.", BOTH)
r4 = run_scan_with(f"Deploy with `pwsh -File {ABSENT}` after review.", PY_ONLY)

states = {
    "R1_red_on_untracked_shell_target": [f["target"] for f in r1] == [ABSENT],
    "R2_green_on_tracked_shell_target": r2 == [],
    "R3_green_on_markdown_link_mention": r3 == [],
    "R4_pre_change_extractor_misses_it": r4 == [],
}

# Attribution: how many of the corpus's commands does each extractor account for?
corpus = sorted(p for p in TRACKED if G.in_corpus(p))
per_extractor = {}
for name, pat in G.EXTRACTORS:
    n = 0
    for path in corpus:
        for line in G.blob(root, path).splitlines():
            n += len(pat.findall(line))
    per_extractor[name] = n

out = {
    "rev": G.git(root, "rev-parse", "HEAD").strip(),
    "corpus_docs": len(corpus),
    "states": states,
    "ALL_STATES_PASS": all(states.values()),
    "commands_per_extractor": per_extractor,
    "commands_total": sum(per_extractor.values()),
    "sentinel": ABSENT,
    "r1_findings": r1,
}
with open(
    os.path.join(root, "command-center/slop-report/_r4_redproof.out.json"),
    "w",
    encoding="utf-8",
    newline="\n",
) as fh:
    json.dump(out, fh, indent=1, sort_keys=True)

for k, v in states.items():
    print(f"   {'ok  ' if v else 'FAIL'} {k}")
print("attribution:", json.dumps(per_extractor), "total", out["commands_total"])
print("SUCCESS:r4-redproof" if out["ALL_STATES_PASS"] else "FAILED:r4-redproof")
raise SystemExit(0 if out["ALL_STATES_PASS"] else 1)
