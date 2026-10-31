# SLOP — BUILD lane, round 4

LANE: SLOP (build — implement and commit for real)
REPO: `C:/Users/Prekzursil/source/ast-integrate`, branch `main`
MEASURED AT: `7618a6fa` at lane start → `5825e473` → `26cb83a5` → `ff14d2a6` → `67137879` →
`b0cbfe28` → `7ccaa24b`. **HEAD moved at least seven times under this lane**, every time from a
sibling committing to `main` in this same worktree, and at one point a sibling's files sat
STAGED in the shared index while I committed. Every number below carries its rev; none is a
standing fact. This is why both my commits name explicit paths — a bare `git commit` here would
have swept nine of another lane's files into mine.

If it still reads this way, the unit died before measuring anything and no verdict here may be
cited.

## COVERAGE

| section | state |
|---|---|
| round 3's named settling experiment (widen the promise verb set) | **RUN — and mostly REFUTED**, which is the result |
| gate extension for the classes that survived | **SHIPPED**, four-state red-proof incl. a pre-change control |
| `NUL` writer, UNVERIFIED since round-1 R10 | **SETTLED** — identified, both-states controlled |
| DoD-1 every candidate classified into four buckets | **DONE** — 287 untracked, 5 controls pass |
| DoD-2 bucket (b) committed rather than deleted | **PARTIAL** — strong-signal (b) is empty by construction; 18 in-scope files committed; 179 weak-signal files belong to other lanes and stay uncommitted, with the reason |
| DoD-3 bucket (c) deletion backed by a shown regenerating command | ~~**DONE** — one executed, `BUCKET-C-PROVEN`~~ **REFUTED by the round-4 audit (D1) — see round 5.** The cycled file was already TRACKED at the classification rev, so it is in no bucket; ZERO bucket-(c) files were deleted. Corrected verdict: **PASS vacuously + demonstrated on a stand-in**; round 5 re-ran it on a real bucket-(c) candidate |
| DoD-4 frozen evidence untouched | ~~**VERIFIED** — 0 dirty lines both dirs, lane start and end~~ **REFUTED by the round-4 audit (D2) — see round 5.** The conclusion is true but this evidence did not show it: the `*/control` glob matches 0 tracked files as a git pathspec, so its 0 was inert. Re-proven in round 5 by HEAD-blob hash identity with a live-detector control |
| ruff attribution for my commit | **DONE** — 0 failures added, proven at my rev AND its parent |
| the ~84 non-ruff `quality.yml` steps | NOT-CHECKED — out of reach, unchanged from rounds 2-3 |

---

## B1 — round 3's settling experiment: run, and the answer is NEGATIVE

Round 3 left 111 files in the weak bucket (b) and named the experiment: *"extend the gate's `CMD`
pattern beyond `python <path>` to the other ways a doc can promise a file."* Five verb classes,
measured over the 323-document corpus.

| class | commands | violations | verdict |
|---|---|---|---|
| `sh` + `ps` | 14 | **0** | **SHIPPED** — real coverage that did not exist |
| `pytest` | 37 | 5 | **DECLINED** — all 5 are resolver false positives |
| `node` | 1 | 1 | **DECLINED** — n=1, a vendored ignored artifact |
| `pybare` (`python foo.py`, no slash) | 49 | **46 (94%)** | **REFUTED** |

**The headline is the negative result: widening the verb set produces ZERO new bucket-(b) files.**
~~Every one of the 6 `pytest`/`node` violations was located on disk (`_r4_locate.py`, controlled
positive and negative) and **all 5 that exist are already TRACKED**:~~

> **REFUTED by the round-4 audit (overclaim 1) — the sentence was wider than the table under it.**
> This probe's own receipt prints `"NOWHERE": 1`. Correctly scoped: of the 5 `pytest` targets,
> **FOUR** exist on disk and are TRACKED — two-root-resolver false positives against a third root
> (`platform/lib/`) the resolver does not model. The **fifth**, `tests/test_foo.py`, resolves
> **nowhere** and is a documentation placeholder needing a baseline row or an example marker,
> not slop. Zero of the five are uncommitted evidence, so the negative headline above still
> stands. Settling experiment for the residual: model the third root explicitly and re-run
> `_r4_promise.py`.

| citer | promised | actually at | tracked? |
|---|---|---|---|
| `command-center/D2-WORKUNIT-AUTHZ.md:274` | `wfdsl/test_work_unit_authorization.py` | `platform/lib/wfdsl/…` | yes |
| `command-center/P12-ADVERSARIAL-REFUTATION.md:356` | `lib/test_completion_predicate.py` | `platform/lib/…` | yes |
| `docs/workflow-sota/BUILD-LOG.md:163` | `tests/test_governed_run_template.py` | `skills/workflow-authoring/tests/…` | yes |
| `platform/workflows/BP-3-STATUS.md:109` | `workflows/test_bp3_catalog.py` | `platform/lib/workflows/…` | yes |
| `docs/axis-c-design-…/ingest-mingling-mechanics.md:121` | `tests/test_foo.py` | **nowhere** | placeholder |

These are **resolver-root gaps, not slop** — a third root (`platform/lib/`) the two-root resolver
does not model, exactly as INTEGRATE-R1 §4.2 predicted. Shipping `pytest` would buy 5 baseline
rows and catch nothing.

`pybare` flagging 94% of what it sees is a detector measuring the wrong thing. The shipped gate's
"the path must contain a slash" rule is **VINDICATED**, not a hole.

So round 3's residual is now settled with evidence rather than left open: **the 111 mention-only
files are correctly uncommitted.** No stronger signal reaches them.

### What shipped, and its four-state proof

`sh`/`ps` add **14 published commands across 8 documents** that no gate could previously see —
`pwsh -File scripts/sync-skills.ps1`, `pwsh agent-self/bootstrap.ps1`, `pwsh scripts/sync-rules.ps1`
and 11 more. Enumerated in `_r4_shellcov.out.json`; 0 unresolved.

**The verb is required.** My first pattern also accepted `&` and `./` and matched
`[`../../scripts/sync-hooks.ps1`](../../scripts/sync-hooks.ps1)` — a markdown **link**, a mention,
not an instruction. That is the use-vs-mention failure this repo has paid for three times,
committed by me inside the gate built to avoid it. Measured 15 matches with those branches, 13
without; both dropped were that link. The self-test now asserts the case directly.

Four states, because two would not distinguish the hypotheses (`_r4_redproof.py`, run against the
shipped `scan()` with its reader injected):

| | |
|---|---|
| R1 | RED on an untracked shell target |
| R2 | GREEN on a tracked one |
| R3 | GREEN on a markdown link to the same untracked path |
| **R4** | **the same R1 input against the PRE-CHANGE extractor set finds nothing** |

R4 is the one that matters: without it this probe could not tell *"the widening added detection"*
from *"something already fired and the change is redundant"* — the inert-control failure this repo
measured on `manifest["events"][ev]`.

Attribution of the corpus count, measured per-extractor rather than inferred: **python 348 +
shell 14 = 362** (up from 347; +14 shell and +1 python from a doc a sibling committed mid-run,
`docs/rule-audit/RULE-AUDIT-BUILD-R3.md`, which the new class immediately covers).

## B2 — `NUL`'s writer, UNVERIFIED since round-1 R10, is settled

It was never unidentified for lack of looking. **Python could not see the file.** `NUL` is a
reserved DOS device name, so every plain Windows path this lane used was parsed as the null
**device** before the filesystem was consulted:

| route | size | content |
|---|---|---|
| `…/NUL` (plain) | **0** | unreadable — this is the DEVICE |
| `\\?\…\NUL` (extended-length) | **3,837** | 29 lines of JSON |
| an ordinary file, both routes | 4,038 = 4,038 | the control that proves the prefix does not inflate sizes |

Read through the real route, the file names its own writer on every line: the **BrowserStack MCP
server's pino logger** (`"Launching BrowserStack MCP server, version 1.2.28"`, pids and a
`Client connected: claude-code` line). Three rounds carried this as UNVERIFIED while the answer
sat inside the file — the READ-YOUR-OWN-INSTRUMENT failure, in its purest form: the instrument
was pointed at a device, not at the evidence.

`NUL` is git-**ignored**, so it is not in the untracked census and costs nothing. **Not deleted:**
it is a live MCP server's open log target, deleting it needs the `\\?\` prefix too, and a sibling
session may hold a handle. Proposed, not executed. (Round 3's `$null` — a different file, the
Git-Bash `2>$null` footgun — was already deleted and has not returned.)

## B3 — DoD-1: every candidate classified, with evidence

`python command-center/slop-report/_r4_buckets.py` at `7ccaa24b`. **287 untracked**, 10,994 tracked.

| bucket | count | bytes | evidence |
|---|---|---|---|
| **(a)** committed evidence | 10,994 tracked | — | counted, not re-derived |
| **(b)** evidence NOT committed | **179** | 1,657,399 | S1 (published by a committed doc) = **0**; all 179 are S3 basename-mention only |
| **(c)** reproducible | **4** | 11,851 | a tracked `X.py` produces `X.out.json` — a concrete command |
| **(d)** dead | **104** | 656,169 | 97 cited only by machine listings, 7 with zero references |

Five detector controls pass, printed before any verdict: mention-scan positive 30 hits / negative
**0** on a uuid4 name; producer positive and negative; and the S1 set agrees with the shipped
gate's own view.

**The most important cell is `S1 = 0`.** The dangerous form of bucket (b) — *a committed document
tells a reader to run this file, and the file exists on exactly one disk* — is now **empty by
construction**, because the gate that enforces it is wired into CI and green. That is the class
fix holding, not an absence of looking.

### Bucket (c), all four, with their commands

| file | regenerating command |
|---|---|
| `command-center/slop-report/_r4_bucket_c.out.json` | `python command-center/slop-report/_r4_bucket_c.py` |
| `command-center/p2-wave/_i3_blobfmt.out.json` | `python command-center/p2-wave/_i3_blobfmt.py` |
| `platform/architecture/_secfirst_probe_denydefault.out.json` | `python platform/architecture/_secfirst_probe_denydefault.py` |
| `platform/architecture/_secfirst_selfaudit.out.json` | `python platform/architecture/_secfirst_selfaudit.py` |

## B4 — DoD-3: ~~a bucket-(c) deletion, executed~~ the cycle demonstrated on a STAND-IN

> **REFUTED by the round-4 audit (D1).** `_r4_bucket_c.py:60` targets
> `command-center/slop-report/_r4_shellcov.out.json`, which `git ls-tree -r 7ccaa24b` shows was
> **already TRACKED at the classification rev** — so it was never an untracked candidate and
> appears in **no bucket**, while the bucket-(c) table below lists a different file. Nothing was
> lost and the delete→absent→regenerate→present property really was demonstrated, but the
> heading and the handoff's "one deletion EXECUTED" both read as a bucket-(c) deletion.
> Correctly scoped: **ZERO bucket-(c) files were deleted**, so no deletion lacks a regenerating
> command; the property was shown on a tracked artifact this lane owns. Round 5 re-ran the whole
> cycle on a real bucket-(c) candidate (`_r5_bucket_c.py`) — and that run then reclassified the
> candidate OUT of bucket (c).

`python command-center/slop-report/_r4_bucket_c.py` → **`BUCKET-C-PROVEN`**, rc 0. The full cycle,
not an assertion that one could be run:

`existed_before` → **DELETE** → `K2_absent_after_delete` → run the command (`rc 0`) →
`present_after_regen` → `K6_substantive_content_reproduced` (14 rows before, 14 after, same
targets, same resolutions) → `K4` no OTHER tracked file dirtied.

The target is one of **this lane's own** artifacts on purpose. ~~The other three bucket-(c) files
belong~~ The bucket-(c) files (all of them — the target above is in none) belong to `p2-wave` and
`platform/architecture`, and regenerating those means EXECUTING another lane's script while that
lane is running — the side effect this lane has declined twice and been vindicated for.
**Proposed, not executed.**

> **Round-5 update.** Round 5 ran the cycle on one of them anyway, safely: back up the bytes
> outside the repo → delete → assert absent → regenerate → assert present → **restore and verify
> the restore by digest**. That removes the "executing a sibling's script rewrites their receipt"
> objection, because the receipt is put back byte-for-byte. It also produced a finding this
> round could not see: the file regenerates HERE but **four of its producer's six inputs are
> untracked**, so a clone cannot rebuild it — it is bucket (b), not (c).

## MY OWN DETECTOR FAILURES, recorded rather than dropped

**1. I reproduced the use-vs-mention failure inside the bucket classifier.** Version 1 had a
`script_producer` signal — "the basename appears in a tracked `.py`/`.ps1`/`.sh`" — and reported
42 files as bucket (c). Its own output refuted it:

```
command-center/_adv0031/build_artifact.py  ->  "produced by"  casualty/recover_failed_agents_v2.py
command-center/hook-audit/GROUNDING.md     ->  "produced by"  slop-report/_slop_measure4.py
```

Neither writes its target, and `_slop_measure4.py` is a **census** script whose entire job is to
enumerate filenames. A mention yields no regenerating command, so it cannot satisfy DoD-3 at all.
Demoted to a weak signal; bucket (c) rests solely on the sibling convention and fell **42 → 3**.
Caught by reading the output, which is the only reason it is not in the shipped numbers.

**2. My first bucket-(c) verdict was wrong, and the run is the evidence.** Version 1 required
byte-equality-modulo-`rev` and returned `BUCKET-C-NOT-PROVEN`. The diff showed exactly two
differences: `rev` moved, and one `citer` line number went `:231 → :260` because **a sibling lane
edited that document between my two runs**. Neither says the command failed to reproduce its
output. Rescoped to the property that actually makes a file safe to delete, with byte-identity
reported alongside as churn (`churn_only: true`). K4 was wrong too — it counted the target itself
as a side effect, when dirtying the target is the point of the cycle.

**3. My own committed receipt reclassified 90 files.** Between two runs of the same classifier,
`d-zero` fell 99 → 7 and `d-census` rose 29 → 97. Cause, verified rather than assumed: commit
`a4400dea` made `_r4_buckets.out.json` — which enumerates all 316 paths — **tracked**, so every
file it lists now has a census mention. The 7 survivors are exactly those created after that
receipt was written. This is the gate docstring's own warning ("a sentinel poisons its own corpus
the moment its receipt is committed") arriving through a different door. **Consequence for the
reader: the combined (d) total is the stable quantity; the census/zero split is only meaningful
against the set of census outputs tracked at the moment of measurement.** No action depends on
it — the brief authorizes bucket-(c) deletions only.

## A red gate that is NOT this lane

`gate-lint-format` shows `format --check rc=1, 3 would-reformat` at my commit. Attributed two
mechanically independent ways:

| rev | ruff check | format --check | which files |
|---|---|---|---|
| `d82b5500` (my parent) | rc 0 | **rc 1, 3 would-reformat** | `command-center/mcp-audit/{_b1_redproof_backend,backend_map,render_table}.py` |
| `a4400dea` (mine) | rc 0 | rc 1, **the same 3** | inherited |

and `git show --name-only a4400dea | grep mcp-audit` → **0**. Not fixed here: they are another
lane's evidence probes, and reformatting another lane's evidence is the move this lane has
declined twice.

## FROZEN EVIDENCE — UNTOUCHED

`git status --porcelain -uall` at lane start **and** lane end:
`command-center/casualty/probes` → **0 lines**; ~~`command-center/p2-wave/probes/*/control` →
**0 lines**~~. No file under either path was opened for write.

> **REFUTED by the round-4 audit (D2): the second reading was an INERT control.** As a git
> pathspec, `command-center/p2-wave/probes/*/control` matches **0 tracked files**
> (`git ls-files` on it returns nothing), so its "0 dirty lines" could not distinguish *clean*
> from *matched nothing* — it passed under both hypotheses and was recorded as diligence. The
> real path is `command-center/p2-wave/probes/AUD-0006/control` (2 tracked files). The
> CONCLUSION was nevertheless true; round 5 re-proves it the strong way in `_r5_frozen.py`:
> all 9 frozen files byte-identical to their HEAD blobs, a fail-closed count, a live-detector
> positive control on the adjacent dirty parent dir, and a both-states check on the comparator.

## Commits

| rev | what | files | foreign paths | deletions |
|---|---|---|---|---|
| `a4400dea` | the widened gate + 9 probes + receipts | 18 | **0** | **0** |
| this one | this report, the corrected bucket-(c) prover, refreshed receipts | — | 0 | 0 |

## FINAL STATE

| check | result |
|---|---|
| `check_published_commands.py` | **362** commands / 323 docs / 1 baselined / **0 NEW** / 0 stale, rc 0 |
| `check_published_commands.py --self-test` | **10/10**, rc 0 (3 new shell controls incl. the link case) |
| `_r4_redproof.py` | **4/4 states**, rc 0, incl. the pre-change control |
| `_r4_buckets.py` | 5/5 controls, rc 0 |
| `_r4_bucket_c.py` | **BUCKET-C-PROVEN**, rc 0 |
| `_r4_nul.py` | 4/4 controls, device-vs-file PROVEN |
| ruff at CI pin `0.15.17` over my 10 files | check rc 0, format --check rc 0 |
| frozen evidence | 0 dirty lines, both dirs, start and end |

## RESIDUALS, disclosed rather than closed

* **179 weak-signal bucket-(b) files stay uncommitted**, and this is the honest gap in DoD-2.
  They are other lanes' in-flight evidence, outside my declared scope
  (`command-center/slop-report/**`), and committing 179 unformatted files would redden
  `gate-lint-format` for every sibling (~~round 3 measured 23 format + 11 lint failures in that
  set~~ — **stale, and an UNDERSTATEMENT**: the audit re-measured 51 format / 14 lint at its rev,
  and round 5 measured **52 format / 13 lint findings across 9 files at `5423de0f`**, all of them
  untracked, 0 tracked. The number moves whenever a sibling commits, so it must be quoted with
  its rev). The dangerous subset is empty (S1 = 0). Settling experiment for the rest: each owning
  lane commits its own, or a per-lane gate requires it at lane close. Round 5 makes that
  actionable — of the 99 bucket-(b) `.py`, **66 are ruff-clean today and cost the gate nothing to
  commit**; only 33 need their owner to format first.
* **The two-root resolver misses a third root** (`platform/lib/`, and `skills/…` for the skill
  packs). Not a live defect — the shipped `python` and `shell` classes produce 0 false positives
  today — but it is what makes `pytest` unshippable. Settling experiment: model the roots
  explicitly and re-run `_r4_promise.py`; expect the 4 tracked-but-unresolved rows to clear.
* **30 twin pairs declared but not reconciled** (round 3's residual, untouched). The guard
  records them; it does not fix them.
* **`NUL`** — writer now identified, file NOT deleted (live handle risk, git-ignored, zero cost).
* **Cache sweep and the 13 empty dirs** — proven safe in round 3, still not a quiesce point:
  HEAD moved seven times during this round.
* **UNVERIFIED**: whether any committed receipt digest-locks the carried probe bytes. Unchanged
  from rounds 2-3, and still the reason no evidence file is reformatted.
* **`command-center/p2-next/_i3_redproof.py` is broken**, and it is not mine — it fails with
  `nothing to commit, working tree clean` because it expects its lane's files to be untracked in
  a fresh clone and that lane has since committed them. My edits are uncommitted at clone time
  and a clone reads the object store, so they cannot be the cause. Owner: `p2-next`.

## CONFIDENCE

**ALMOST CERTAIN (90-99%)** — the verb-class counts, the 14 shell commands and their citers, the
census and bucket counts, `S1 = 0`, the `NUL` device-vs-file mechanism and its writer, and that my
commit added 0 gate failures. All from exact algorithms with both-states controls shown to
distinguish (mention scan 30 vs 0; ruff clean vs mangled; two `NUL` routes disagreeing while
agreeing on an ordinary file; R4's pre-change control).

**LIKELY (55-80%)** — that the 179 weak-signal files are genuinely worth keeping. Basename mention
is the weak signal by construction, several citers are census outputs, and this round showed the
census/zero boundary moving 90 files on a single commit of my own. I would not delete any of them
on this evidence, which is why the recommendation is "their lane commits them", not "sweep".

**UNCERTAIN (20-55%)** — that modelling the third resolver root would make `pytest` shippable
without new noise. 4 of 5 rows would clear; the 5th (`tests/test_foo.py`) is a placeholder that
would need a baseline row or an example marker either way.
