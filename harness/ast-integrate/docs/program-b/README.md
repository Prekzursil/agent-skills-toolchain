# Program B (`workflow_design`) — the 8-item register

`program-b-receipt.json` in this directory is the **machine-readable source of truth**.
`ci/tests/test_program_b_register.py` reads it on every pull request, so this register cannot
silently drift or be silently deleted. This file is the human-readable view of the same data.

## Two facts that keep getting lost

Both have now been re-litigated **three** times. They are repeated here, and pinned by the CI
test, specifically so a fourth session does not spend the effort again.

1. **The owner decided INTERLEAVE.** `15-OWNER-DECISION-RECEIPT.json:5` records
   `"q1_answer": "INTERLEAVE"`, sourced verbatim to the owner: *"it should be interleave not
   separate as program a and program b … since sequential is slow"*.
   **Only the A/B SEQUENCING is superseded. The B-lane ITEMS are not.** Conflating the two is
   precisely how this lane got dropped, three times.
2. **`workflow_design` is a SESSION NAME**, unrelated to Claude Code Workflows. The estate holds
   ~281 tracked paths matching `workflow` and three live `workflow-*` skills, and they are **all
   Program A** — the blueprint library, `workflow-foundry`, and the harness-sota corpus included.
   A keyword search for "workflow" returns Program A and buries Program B.

## The B3/B4/B5 id collision (R-B07)

The unified prompt's §13 and the reconciled backlog use the same three ids for different things.
The prompt wins, per §0 BINDING AUTHORITY ORDER. The stale column is recorded so a stale citation
is *recognisable* rather than merely wrong.

| id | canonical (prompt §13) | stale (reconciled backlog) — do not use |
|---|---|---|
| B3 | awesome-game-security | VERIFIED_DONE confirmations |
| B4 | Battle Cats | Reframe — **out of scope**, a concurrent session owns it |
| B5 | SWFOC | awesome-game-security |

## Status, graded from code on 2026-08-09

| id | item | status |
|---|---|---|
| R-B01 | B1's M1–M5 prevention proposals reach no config, hook, or decision queue | OPEN |
| R-B02 | Re-verify the 6 CLAIMED_NEEDS_REMEASURE workstreams | OPEN (5 of 6 resolved) |
| R-B03 | Skill authoring / lifecycle — B2's 11 fields and 9 properties | OPEN |
| R-B04 | B4/B5 game-domain skill families | **DONE-VERIFIED** (was DONE-CLAIMED) |
| R-B05 | Zero consumers reach any Program-B artifact | IN-FLIGHT |
| R-B06 | basic-memory holds zero notes on Program B | **DONE-VERIFIED** |
| R-B07 | B3/B4/B5 id collision | IN-FLIGHT |
| R-B08 | Live third-party credentials in `Diag 1.txt` | OPEN — **owner-only** |

### What changed, and what did not

**R-B04 moved DONE-CLAIMED → DONE-VERIFIED.** All 8 game-domain skills (5 Battle Cats, 3 SWFOC)
pass validation; `scripts/validate-all-skills.ps1` completed a 328-skill run with zero
game-domain failures. This also **refutes** the register's supporting evidence that the script is
"itself unrunnable": its *second* validator candidate resolves.

**R-B02 shrank from 6 open sub-items to 1.** Four are DONE-VERIFIED (`mcp-parity`, `mcp-gui`,
`api-perm-script`, `abbyy-ocr` — the last two were recorded as *likely outstanding* and are
refuted by on-disk evidence), one is DROPPED-BY-OWNER, and `claude-in-chrome` is **NOT-CHECKED**
because verifying it needs a browser. The row stays OPEN only because it also demands a final
disposition for all 16 dossier workstreams, and the other 10 were not re-measured here.

**R-B01's "the metric got worse" is withdrawn.** The register cites 1,233 processes against 1,070
at diagnosis. Today's reading is **972** — below both. A single snapshot cannot establish a trend
in either direction. What survives is the durable part: Defender exclusion paths = 0, `grok*`
processes = 1, and zero fan-out width caps across 206 live hook files (control: 205 of those same
files match a pattern that must hit). M1, M2 and M5 are unapplied.

**Nothing here closes R-B08.** The file exists, 2,172,114 bytes, unchanged since 2026-07-21.
It was **not opened and not scanned** — existence, size and mtime only. Its reported contents are
inherited and therefore UNVERIFIED by this lane. **Rotation is the owner's alone (AGENTS.md §9);
no agent may perform it.** What is owed is a decision plus a quarantine.

## Open owner questions

- **OQ-6** — `Diag 1.txt`: quarantine where, and does the blast-radius trace run before or after?
- **OQ-7** — confirm the prompt-wins B3/B4/B5 numbering so it is renumbered once, forever.
- **OQ-B1** — M1 (Defender exclusions) and M2 (grok-cli residency) are owner-only. Apply, decline,
  or defer?

## Deliberately out of scope

Reframe app remediation (a concurrent session owns it) · the 19 `Documents\GitHub` residue repos
(NOT_IN_SCOPE) · the per-repo fan-out plan (RETRACTED by B0 itself) · the awesome-game-security
installers (DROPPED-BY-OWNER).

## Why the receipt lives here and not in the continuation root

The contract names `program-b/PROGRAM-B-RECEIPT.json` under
`.claude/platform-redesign-2026-07-19/unified-continuation/20260723T190727Z/`. That path is not
version-controlled and has no reader — writing there would reproduce the exact
diagnosed-not-wired shape this register exists to close. The receipt is therefore emitted **into
the repo, under a CI gate**, and the contract-path artifact remains ABSENT. That absence is
recorded, not papered over.
