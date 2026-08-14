# CIGREEN round 2 — six retractions, and the work order the first one hid

Round 1 of the CIGREEN lane shipped real fixes that survived an independent audit (all three
DoD items re-passed on re-execution). What did not survive was some of its **prose**. An
adversarial verifier CONFIRMED one false factual claim and four numeric overclaims; a fifth
was found here. Every correction below was re-measured **independently** for this document,
not copied from the verifier — where my number and the verifier's differ, both are shown.

The earlier wording is quoted verbatim and marked REFUTED rather than deleted. A claim that
is silently rewritten teaches nobody which instrument was wrong.

---

## R1 — "`command-center/ci/` DOES NOT EXIST" — REFUTED, and it cost something

> Round 1: *"the declared file scope was `.github/workflows/**` and `command-center/ci/**`.
> `command-center/ci/` DOES NOT EXIST."*

Measured:

    git ls-files command-center/ci
      -> command-center/ci/orchestrator-flake-note.md
    git cat-file -e 27da3215:command-center/ci/orchestrator-flake-note.md   -> rc=0  (round 1's spawn HEAD)
    git cat-file -e 28d42732:command-center/ci/orchestrator-flake-note.md   -> rc=0  (round 1's own PR commit)
    git ls-tree -r --name-only ae8205a4 -- command-center/ci                -> (empty)
    created: e4b72cfe, 2026-08-12 23:25:09 +0300

The directory was present at both revisions round 1 actually worked on. It is absent from
exactly one revision — `ae8205a4`, the stale brief baseline that round 1 had **itself already
proven was 92 commits behind**. The claim was inherited from the grounding pass and forwarded
without a re-probe, which is the specific failure the fan-out contract names: a briefed fact
needs a mechanically different re-probe, and re-running nothing is not one.

**This is not a cosmetic correction.** `orchestrator-flake-note.md` ends with a section headed
*"Suggested remedy (CIGREEN lane's call, not executed here)"* — a four-item work order addressed
to this lane by name, complete with a detector-control protocol. Round 1 asserted the directory
was empty and therefore never opened it. The assignment sat unread for a full round.

Correctly scoped: *"`command-center/ci/` exists and is tracked, but held only
`orchestrator-flake-note.md` (2,968 bytes) — no CI code — so the mcp-audit fix could not land
there and went to `command-center/mcp-audit/**` instead."* That decision was right; only the
sentence justifying it was false.

The remedy is executed in the same commit as this note, which is why this file sits in that
directory rather than anywhere else.

---

## R2 — "skill-dual-write had run 12x, all success" — REFUTED on both halves

    gh run list --workflow skill-dual-write.yml --limit 400
      -> 287 runs returned (not the cap, so this is the complete history)
         success 259 | failure 21 | cancelled 7
         2026-07-21T12:50:16Z .. 2026-08-13T14:50:03Z

Not 12, and not all success. The verifier measured 200/192/8 against a `--limit 200` list cap;
raising the cap to 400 returns 287 and is the uncapped figure.

The conclusion the number was serving is unaffected and stands: the brief's
*"gate-cs-wiring and gate-skill-deploy-hop have NEVER executed"* is false — both ran green in
run 31667122476, steps 8 and 7.

---

## R3 — "byte count unchanged 12,330 / both roots sha256 216b26de6f38" — REFUTED as blob values

These are the **CRLF working-tree** form of the file, reported as if they were the file's bytes.
Measured on the stored blobs:

| revision | path | bytes | sha256 (12) | CRLF |
|---|---|---|---|---|
| `28d42732^` | `skills/.../batch_runner.py` | 12,080 | `b8ac7a518b70` | 0 |
| `28d42732^` | `.agents/skills/.../batch_runner.py` | 12,080 | `b8ac7a518b70` | 0 |
| `28d42732` | `skills/.../batch_runner.py` | 12,080 | `ee3d69237eed` | 0 |
| `28d42732` | `.agents/skills/.../batch_runner.py` | 12,080 | `ee3d69237eed` | 0 |

LF→CRLF conversion of the post-fix blob yields exactly 12,330 bytes and `216b26de6f38`, which
is where the reported numbers came from.

Both underlying conclusions are CONFIRMED by this independent measurement: the byte count IS
unchanged (12,080 on both sides), and both skill roots ARE byte-identical — at `28d42732` they
share one git blob OID, `de37c839ee46e6e67fc6a40f229af7f4f86de851`.

Worth stating plainly because round 1's own commit message insisted on measuring the stored
blob rather than the working tree: the numbers it published came from the surface it warned
against.

---

## R4 — "9 of 11 python-version pins are 3.11" — REFUTED

    12 pins across .github/workflows/*.yml at HEAD:  10 at 3.11, 2 at 3.12
      3.11: codex-runner:96 · mcp-audit:67 · no-runtime-junk:30 · p2next-rail-count:57 ·
            quality:81 · quality:134 · quality:290 · routing-benchmark:48 ·
            rule-audit:94 · skill-dual-write:55
      3.12: quality:1492 · quality:1561

Ten of twelve, not nine of eleven. The conclusion is unaffected and has since been reinforced:
the split-interpreter surface is a live defect generator. It produced the f-string red round 1
fixed (PEP 701 backslashes are 3.12+), and within hours produced another —
`Path.read_text(newline=)` is 3.13+, which red-blocked `gate-tests-coverage` until `b0e3bf98`.

---

## R5 — "3 f-string-backslash sites across 2 files" — SELF-CONTRADICTORY, now counted

Round 1 said "3 sites across 2 files" in its narrative and "3 f-string sites hoisted" for
`_r4_cr_settle.py` alone in its file list. Those cannot both be true. Measured at `0f1ccb52^`:

| file | backslash expressions | on lines | print statements |
|---|---|---|---|
| `_r4_cr_settle.py` | 3 | 105, 118, 119 | 2 (118+119 are one implicit-concat call) |
| `_r4_selfcheck.py` | 1 | 54 | 1 |

Correct: **4 backslash expressions across 3 print statements in 2 files**. At `0f1ccb52` both
files measure 0. "Site" was doing two jobs in one report, which is how the two numbers
disagreed. No functional impact.

---

## R6 — "15/15 steps, 0 skipped" on run 31712123884 — imprecise

Job `gate-skill-dual-write` reports **18** steps, all success, 0 skipped. Fifteen of them are
the numbered gate steps; the remainder are Post/Complete. Defensible under the reading "the 15
numbered gate steps", recorded for precision.

---

## R7 — a residual round 1 raised, now RE-SCOPED by this round

Round 1's residual #1 listed three files that fail to parse on 3.11 and implied a fix queue.
One was real and a sibling closed it (`command-center/slop-report/_i4_wire_ci.py`, at
`46903c7e`). The other two must **not** be fixed:

    command-center/ssot/salvaged-from-scratch/aud_crlf.py:30
    command-center/ssot/salvaged-from-scratch/v10_spot.py:32

`ruff.toml` already excludes `command-center/ssot/salvaged-from-scratch/**`, and states why: it
is a `cp -p` snapshot of files that existed nowhere in the object store, *"copied precisely so
the bytes and mtimes are the originals, which is the whole value of the snapshot."* Repairing
their syntax would destroy the property that makes them evidence. Nothing imports them; no gate
executes them. Correct disposition is WONTFIX-by-design, not a latent-defect queue entry.

---

## The remedy this note's directory asked for

`orchestrator-flake-note.md` recorded that `gate-sast (opengrep)` failed on
`curl: (56) Connection died` during the **install** half — zero files scanned, yet rendered at
job level as `failure  gate-sast (opengrep)`, indistinguishable from a real finding. Its item 1
and item 2 are implemented in the same commit as this note:

1. **Install and scan are now two steps**, so the failing step NAME says which half broke.
2. **`curl --retry 5 --retry-all-errors --retry-delay 3`** — `--retry-all-errors` is the flag
   that covers a connection reset mid-transfer, which is what curl's own internal retry failed
   on. Plus `test -s` so an empty download fails in INSTALL.

Item 3 (digest-pin + `actions/cache`) is deliberately **not** done: it is a larger change with
its own failure modes and deserves its own verification. Item 4 is honored — no
`continue-on-error`, no `|| true`. A gate that cannot run must not report success. Both step
names keep the `gate-sast` marker, so `.quality/charter_check.sh` still maps them to the one
declared slug (verified: `charter_check: OK -- 7 gates consistent`).

### Both-states control, as that note demanded

The note is explicit that *"a fix that is only ever observed in the healthy state has not been
shown to separate them."* Two forced-failure runs were dispatched against the same tree:

| state forced | expected failing step | run id | result |
|---|---|---|---|
| install broken (URL → nonexistent tag) | `gate-sast opengrep install` | UNKNOWN - not yet measured | UNKNOWN - not yet measured |
| scan finding (seeded rule hit) | `gate-sast opengrep scan` | UNKNOWN - not yet measured | UNKNOWN - not yet measured |
| healthy (this branch) | none | UNKNOWN - not yet measured | UNKNOWN - not yet measured |

If this table still reads UNKNOWN, the controls were never run and the split has NOT been shown
to discriminate — treat the change as unverified and do not cite it.

---

## One more instrument failure, disclosed because it nearly became a finding

Chasing the `gate-tests-coverage` red at `b0e3bf98`, the local reproduction **passed**. Two
hypotheses were probed and both refuted: the doc text was byte-identical to its blob after
LF-normalisation (not a working-tree drift), and `scripts/hooks/cost-tracker.js` does not exist
on this disk either (not a dirty-tree `Path.exists()` artifact). Both refutations were correct,
and both were beside the point — the actual cause was that HEAD had moved **9 commits** between
the CI run and the probe, and sibling `5d573583` had already rewritten the offending line. The
probe was reading a different revision than the one CI measured.

Reporting "cannot reproduce" from that pass would have been a false finding. What caught it was
that the two refutations left nothing standing, which is the tell that the instrument, not the
hypothesis, is wrong. Verdict on the red itself: root cause was a bare `scripts/hooks/cost-tracker.js`
at `commands/sessions.md:289` tripping `test_no_command_doc_prose_claims_a_missing_repo_path`;
closed by a sibling, not by this lane.
