---
title: MON-ROUND2
type: note
permalink: dqverify-repo-20261013/docs/monitor/mon-round2
---

# MON lane — round 2 (re-entry after an adversarial refutation)

STATUS: MEASURED. Every claim below carries a pasted command output or names the file:line it
was read from. Where a round-1 sentence was wider than its evidence, the earlier wording is
recorded as REFUTED rather than deleted (fan-out-contract C2).

COVERAGE: complete for the four defects listed below and for the increment. NOT measured:
any GitHub Actions run (no CI has executed since these commits), and a whole-repo fresh-clone
suite (only the monitorcore package and its 39 test modules were run).

---

## 1. The increment: the cockpit reachability gate now grades the COMMIT

`tools/monitorcore/tests/test_registry_commit_truth.py` (new, 15 tests).

`test_registry_shipped.py` asks the right questions of the WRONG TREE. Every assertion in it
reads the Windows working tree (`Path.read_bytes` / `Path.is_file`); CI checks out the commit.
That gap is not hypothetical here — commit `3bdcaf56` is literally titled *"worktree was
green, the COMMIT was not"*.

The new module re-asks both reachability questions of the committed tree:

* are the two committed registry mirrors byte-identical **in the commit**?
* is every stanza's entry script a **tracked** path, i.e. would a fresh clone have the file
  that `mon <name>` is about to run?

**Honest scope.** Both questions already answer YES at HEAD, so this is a LATENT-hole closure,
not a live-defect fix. Measured 2026-08-12:

```
skills/monitor-launcher/monitors.toml           blob=3874 bytes crlf=0
.agents/skills/monitor-launcher/monitors.toml   blob=3874 bytes crlf=0
raw blobs equal: True          CONTROL mangled vs other: False
tracked-set size 10034   CONTROL known path in set: True   bogus path in set: False
12 of 12 stanza entries (6 stanzas x 2 registries)  disk=True head=True
```

It is additive rather than a replacement: the worktree assertions still catch an unstaged
one-sided edit, which a blob read cannot see. The two together cover both directions.

Not mtime-based, substantively and not only lexically: everything is content-addressed (blob
bytes, tree membership). `stall.py` was not touched.

## 2. Proof the increment can fail — 7/7 mutations killed, 1/1 no-op survived

`tools/monitorcore/_r2_mutation_control.py`. Each guard is reverted in turn into a **sibling
copy** of the module (the real file is never edited, so the shared worktree other lanes are
using is untouched even if the script is killed mid-run), pytest runs only that copy, and it
must go RED.

```
[baseline] unmutated copy exit=0 :: 15 passed in 5.49s
  KILLED       mirror_divergence always reports 'identical'            :: 4 failed, 11 passed
  KILLED       line-ending drift is misreported as content drift       :: 1 failed, 14 passed
  KILLED       untracked_entries never reports anything                :: 2 failed, 13 passed
  KILLED       an empty tree listing is accepted instead of failing closed :: 1 failed, 14 passed
  KILLED       an absent git silently falls back to a bare 'git'       :: 1 failed, 14 passed
  KILLED       an unreadable revision returns empty bytes not a raise  :: 1 failed, 14 passed
  KILLED       the two-path precondition is dropped                    :: 1 failed, 14 passed
  SURVIVED(ok) NO-OP: reword a docstring (inverted control)            :: 15 passed
restore verified: test_registry_commit_truth.py is byte-identical to its pre-run text
SUCCESS:r2-mutation-control 7/7 killed, 1/1 no-op survived
```

The inverted control matters: without it a harness that printed KILLED unconditionally would
look perfect.

Two of the module's own tests are controls against the REAL repo at HEAD, not against a temp
object database — `mirror_divergence` on two genuinely different tracked files must report
`content`, and a stanza naming an absent path must be reported. Temp-repo controls prove the
FUNCTIONS fire; these prove the SHIPPED assertions are wired to a working instrument.

## 3. Defect 1 — the R-M18 blocker was an overclaim; the real one is narrower

REFUTED (round 1): *"A SUCCESS receipt REQUIRES an INDEPENDENT reviewer PASS … writing
`command-center/receipts/R-M18.json` here would be self-certification."* The quotation is
accurate; the conclusion is wider than the clause. The reviewer requirement sits inside an
`if state == "SUCCESS"` branch, and a `BLOCKED` receipt with `reviewer.independent: false` is
schema-valid — `command-center/receipts/BLD-0023.json` is already exactly that.

CORRECTED, re-measured, and mechanically independent (round 1 read the `state` conditional;
this reads the `unit_id` pattern):

```
$defs/unit_id pattern = ^[A-Z][A-Z0-9]*-[0-9]{4}$
re.fullmatch(pattern,'R-M18')    -> None
re.fullmatch(pattern,'BLD-0023') -> match          (CONTROL: the matcher fires)

[LEG 1] receipt as R-M18 declares itself   -> 2 errors: unit_id, sentinel
[LEG 2] identical body, id RM-0018         -> 0 errors     <-- the id shape is the WHOLE blocker
[LEG 3] BLD-0023 as-is                     -> 0 errors     <-- validator accepts a known-good
[LEG 4] BLD-0023 with state -> SUCCESS     -> 7 errors     <-- validator is not inert
FAILED:R-M18-receipt not written
```

Blast radius, with a two-sided control: **0 of 103** REGISTER rows (`items`) match the pattern;
**2007 of 2007** `work_units` do; all 6 receipts on disk do. Every one of the 103 declares
`command-center/receipts/<ID>.json` as its `output_path`, so none of them can emit a valid
receipt. R-M18 is 1 of 103, not a special case.

Full detail, the unblock steps and the inline UNVERIFIED are in
`docs/monitor/ENROLMENT-R-M18.md` under "S5 CORRECTED".

## 4. Defect 2 — `_blob_parity.py` reported 0 CONTENT mismatches; it is now 2

Re-run at this HEAD: `python tools/monitorcore/_blob_parity.py b9a77ad7` →
`files compared: 20  CRLF-in-blob: 0  line-ending-only: 15  CONTENT mismatches: 2`
(`.github/workflows/quality.yml`, `docs/monitor/ENROLMENT-R-M18.md`).

Root cause is TOOL SEMANTICS, not drift in the commit: the tool compares a FIXED commit's
blobs against the MOVING working tree, so its verdict decays the moment any later commit or
sibling edit touches one of those paths. Both current mismatches are later legitimate edits —
`quality.yml` carries another lane's uncommitted `tools/wf-timeout` H6 step, and the dossier
was extended by commit `99118c4d` after round 1's last commit.

Re-scoped sentence: round 1's "0 CONTENT mismatches" was true **at the instant it was run and
only for the paths in that commit**; it is not a durable property and must not be cited as
one. The durable check is blob-vs-worktree at HEAD, which is what the increment in section 1
institutionalises for the registry pair.

## 5. Defect 3 — `vendordrift.py` authorship

`git log --follow` puts `tools/measure-guard/vendordrift.py` AND
`tools/measure-guard/tests/test_vendordrift.py` AND `docs/monitor/ENROLMENT-R-M18.md` first on
commit `52a6d6ab` — *"wip(e2e-wave): preserve interrupted lane output — 1.2 MB of real work,
explicitly UNAUDITED"*, 08:17, an ancestor of round 1's `b9a77ad7` (09:42).

Correctly scoped: round 1 did **not** author `vendordrift.py`; it inherited it from an
explicitly-unaudited WIP commit and contributed (a) the CI wiring at `quality.yml:113-114` and
(b) a live both-states control run. Round 1's "SCOPE EXPANSION BUILT" wording implies
authorship of the tool and should read "wired and controlled a pre-existing, unaudited tool".

The tool itself is separately corroborated: the audit ran a four-leg both-states check on it in
a throwaway repo (clean → 0, content byte → 1, CRLF blob by OID → crlf-only, untracked source
of truth → fail-closed), and it passes here now:
`SUCCESS:vendordrift 2 vendored copy/copies of 'monitorcore' match tools/monitorcore/monitorcore (37 files each)`.

## 6. Defect 4 — the worktree/commit split in the shipped tests

Closed by section 1 for the registry pair. NOT closed generally: the other worktree-reading
assertions in `test_registry_shipped.py` (`test_shipped_registries_exist`,
`test_every_shipped_entry_resolves_to_a_real_file`) still read the working tree. That is
deliberate — they answer "can this box launch it", which is a different and also-useful
question — but it means "the suite grades the commit" is true only of the two questions named
in section 1.

## 7. Gates at the end of this round

```
python -m pytest -q --cov=monitorcore --cov-branch   ->  1184 passed; TOTAL 4174 stmts,
                                                          1244 branch, 0 miss, 100%
basedpyright monitorcore                             ->  0 errors, 0 warnings, 0 notes
uvx ruff@0.15.17 check / format --check              ->  All checks passed / already formatted
python tools/measure-guard/vendordrift.py            ->  SUCCESS:vendordrift (2 copies, 37 files)
```

Baseline before this round was 1169 passed; +15 is exactly the new module.

### Fresh-clone verification (the check the fleet audit says exists nowhere)

Working-tree green is not clone green, so the claim was tested rather than assumed. Two legs,
both from a clone of this repo at the round-2 commit `cdac3f26`, both then deleted:

| leg | checkout | CRLF in the new test file | result |
|---|---|---|---|
| 1 | default `git clone` | 418 | `15 passed` (new module) |
| 2 | `-c core.autocrlf=false -c core.eol=lf` | **0** | `1184 passed` (FULL monitorcore suite) |

Leg 2 is the Linux-runner-equivalent byte form, and leg 1 is its own control: the same clone
command on this box materialises CRLF, which is exactly why a default local clone is NOT a
substitute for it. So `monitorcore` is clone-green at this commit, not merely worktree-green —
a claim round 1 explicitly declined to make.

Scope: this covers the `tools/monitorcore` package only. A whole-repo fresh-clone suite was
NOT run and is not claimed.

Vendored-copy propagation is NOT required this round, with a control: the two committed
vendored copies hold **37** files each and **0** of them are tests, while `tools/monitorcore/
tests` holds 39 test modules. A change confined to `tests/` cannot drift a vendored copy.

## 8. Residual — what this round did NOT do

1. `command-center/receipts/R-M18.json` still does not exist, and now cannot be written validly
   under that id (section 3). R-M06 depends on R-M18, so MONITOR stays gated. Two owner/
   orchestrator steps are named precisely in the dossier.
2. `TaskwatchSource` / a seventh pane: deliberately NOT built. Adding a pane touches
   `unified.py`, `nav.py`, `pane_views.py` — the three files sibling monitor lanes are most
   likely to hold — and round 1 already spent that risk budget on the health pane.
3. `ClaudeScienceSource`: still blocked on a machine-readable feed.
   `scripts/claude-science/cs-watchdog.ps1` emits a formatted plaintext line via `Out-File`
   (control: `grep -c Out-File` = 2 on that file, `grep -c ndjson` = 0). A `[csmon]` launcher
   stanza landed this session, but a launcher is not a feed.
4. **No CI run has executed any of this** (UNVERIFIED, inline). Local commands only. Settling
   experiment: the next Actions run on this branch. The one runner-specific risk is that the
   new tests shell out to `git`; `actions/checkout` provides a full working `.git`, and
   `vendordrift.py` already relies on `git ls-files` in the same workflow, so the precedent
   exists. Confidence it passes: LIKELY (55-80%).
5. `.github/workflows/quality.yml` was NOT touched this round. It currently carries another
   lane's uncommitted `tools/wf-timeout` H6 step; editing it would have swept their work.
6. The register rows R-M02 / R-M18 still carry `[inherited]` evidence that has been refuted
   (13 stale files → 0 real drift; "all three monitors.toml copies" → 2 real registries plus a
   test fixture). Recording those corrections belongs to whoever owns
   `command-center/sources/REGISTER.md`.