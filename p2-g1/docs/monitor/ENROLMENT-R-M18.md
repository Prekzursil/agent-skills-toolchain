# R-M18 enrolment dossier -- unified monitor cockpit

STATUS: COMPLETE for round 1. Every claim below was EXECUTED in this session, on this box, at
worktree `C:/Users/Prekzursil/source/ast-integrate` (branch `main`, parent commit `52a6d6ab`).

The prior round of this lane died after writing only a skeleton. If any row below reverts to
`UNKNOWN - not yet measured`, that is the skeleton and no verdict here may be cited.

COVERAGE: S1-S7 all MEASURED. One item is deliberately NOT done and its blocker is named
(S5, the receipt write) -- see "The receipt blocker".

| # | claim | state |
|---|---|---|
| S1 | monitorcore suite passes, 100% line+branch | MEASURED -- 1169 passed, 4174 stmts / 1244 branches, 0 miss |
| S2 | the increment renders end-to-end | MEASURED -- live + degraded frames captured below |
| S3 | vendored-copy drift across every committed copy | MEASURED -- 0 drift, 2 copies, gate proven to fire |
| S4 | which register artifacts are frozen | MEASURED |
| S5 | `command-center/receipts/R-M18.json` | NOT WRITTEN -- blocker named, schema-anchored |
| S6 | claude-science enrolment seam | MEASURED -- ABSENT |
| S7 | the cockpit increment shipped, with tests | SHIPPED -- the health pane |

## S7 -- the increment: the health pane (adopting the orphaned fifth source)

### The finding

`SystemHealthSource` was written, unit-tested, 100%-covered -- and wired to **nothing**.

Detector, with a positive control so the silence means something:

```
grep -rn "health_source|SystemHealthSource|HealthPayload" monitorcore/*.py   (excluding health_source.py itself)
  -> 0 hits, exit 1
CONTROL, same matcher shape, on a source known to be wired:
grep -rln "mcp_source|McpSource" monitorcore/*.py  (excluding mcp_source.py)
  -> 4 files: pane.py, pane_views.py, unified.py, health_source.py
```

So the matcher fires when a source IS wired. The fifth source had no `PaneId` member, no entry
in `PANES`, and no construction in `unified.default_sources()`. The one adapter whose entire
purpose is to notice that the observer has died was itself unobservable.

CORRECTION TO THE GROUNDING BRIEF (recorded, not silently dropped): the grounding lane ranked a
NEW sixth source (`TaskwatchSource`) as the next increment, having counted five sources without
checking whether all five were reachable. Building a sixth while the fifth is an orphan adds to
the pile. `TaskwatchSource` remains a sound follow-on; it was not the round-1 item.

### What shipped

* `pane.py` -- `PaneId.HEALTH`; `payload_of()` (the SCALAR twin of `payload_rows`, so a
  one-sample payload gets the same never-raise guarantee); `snap_is_stale()`.
* `pane_views.py` -- `HealthPane` + `_health_lines()`, registered as the 6th entry in `PANES`.
* `unified.py` -- `SystemHealthSource` constructed in `default_sources()`, `--health-path` CLI
  flag, pane count corrected in the docstring and `--help` text.
* `health_source.py` -- class-level `id = _ID`, matching the other four sources, so a pane can
  declare `source_id = SystemHealthSource.id` at class-definition time.

THE STALE ROW IS THE POINT. The sentinel's last sample stays readable forever after the sentinel
dies, so a pane that just printed the numbers would render a healthy board for a machine nobody
is watching. When the snapshot is stale the pane leads with an explicit `[STALE] ... every figure
below is the LAST reading, not a current one` row, ahead of any figure.

NO MTIME STALL CLAIM WAS ADDED. Staleness here is the SOURCE's own dead-man comparison of the
sample's embedded timestamp against wall time -- not a file mtime, and not an inference about
whether any process is stuck. `stall.py`'s existing two-signal classifier was not touched.

Verified with a detector that was itself checked, because the first two attempts were broken:

* `grep -n "mtime"` over the modules reported a hit -- it was matching `fro`**`mtime`**`stamp`
  inside `datetime.fromtimestamp`. A substring false positive.
* `grep -nE "\bmtime\b"` reported 0 hits on the modules AND **0 on the control**, because
  `mtime_fn` / `_mtime` have word characters adjacent so `\b` never matches. A detector that
  cannot fire on a known positive proves nothing about a negative.
* Working detector: `grep -n "mtime" | grep -v "fromtimestamp"`. Control fires -- 6 hits in
  `unified.py` (`_mtime`, `mtime_fn`). Against `pane.py`, `pane_views.py`, `health_source.py`:
  **0 hits.** And `git show b9a77ad7 -- unified.py | grep '^+' | grep -c mtime` = **0**, so this
  lane added none of the pre-existing ones either.

### S2 -- executed end-to-end

`python -m monitorcore.unified --once --pane health --width 100` (exit 0):

```
panes 1:codex 2:agents 3:workflows 4:databricks 5:mcp [6:health] tab=next q=quit
  health [error] age=5s health: ORANGE - phys 94% - commit 56% - 1259 procs - 14 orphan
  [ORANGE] phys 94% - commit 56% - driver phys=93.8
  procs 1259 - handles 392556 - threads 12499
  gdi_max not-measured - usr_max not-measured - top not-measured
  orphaned MCP runtimes 14
  orphan - node.exe:93456 (ppid 60940, 74.0 MB)
```

That is live signal from this box that previously rendered on no board at all.

Degraded path, `--health-path C:/nope/missing.ndjson` (exit 0):

```
  health [unreachable] age=- [unreachable] health: unreachable - sentinel event log not found
  workstation health: not measured (sentinel event log not found: is sentinel.ps1 running?)
```

An absent feed reads as *not measured*, never as a fabricated zero.

### S1 -- tests, and proof the tests can fail

`python -m pytest -q --cov=monitorcore --cov-branch` at the moment of commit `b9a77ad7` ->
**1169 passed** (was 1147), TOTAL 4174 stmts / 1244 branches, **0 miss, 100%**.
`basedpyright monitorcore` -> 0 errors, 0 warnings, 0 notes. `ruff==0.15.17 check` +
`format --check` -> clean.

FINAL STATE: **1169 passed, 100% line+branch, 0 miss**, and verified CLONE-GREEN (below).
The transient red that occurred mid-wave is recorded rather than deleted, because it produced
the sharpest finding of this lane.

A mid-wave re-run read **1168 passed, 1 FAILED**:
`test_registry_shipped.py::test_registry_mirrors_are_byte_identical`.

NOT CAUSED BY THIS LANE, and attributed rather than asserted:

```
git show --pretty="" --name-only b9a77ad7 01721de9 | grep -c "monitors.toml"   ->  0
diff skills/monitor-launcher/monitors.toml .agents/skills/monitor-launcher/monitors.toml
   -> the CS lane's new [csmon] stanza (14 lines), present in .agents, absent from skills/
```

The test LF-normalises before comparing, so this was a real divergence and not a CRLF phantom.
Flagged to the orchestrator rather than raced, because the file was actively being edited.

### The finding that mattered: a WORKTREE green is not a CLONE green

The fix was applied and reported GREEN on the strength of `pytest` passing. It was still
broken. `test_registry_mirrors_are_byte_identical` reads the WORKING TREE
(`p.read_bytes()`); CI checks out the COMMIT. Those had diverged:

```
HEAD:skills/monitor-launcher/monitors.toml          3874 B   [csmon] present
HEAD:.agents/skills/monitor-launcher/monitors.toml  3224 B   [csmon] ABSENT
```

One side had been committed and the other left modified-but-uncommitted, so a fresh clone got
exactly the half-written pair the test exists to catch -- invisible to a suite run that
measures the wrong bytes. Committed as `3bdcaf56`.

VERIFIED THE RIGHT WAY AFTERWARDS, by extracting both blobs at HEAD into a temp tree and
comparing those (with a mangled control that fires):

```
control fires: True
SUCCESS:clone-green mirrors identical in a fresh extraction
```

GENERAL LESSON for this program: for any assertion about files a gate compares, run the check
against `git show HEAD:<path>` output, never the worktree. Passing `pytest` proves the tree on
your disk is consistent; it says nothing about what CI will materialise.

A green suite is not evidence until it goes red on a broken build. `_mutation_control.py`
reverts one guarantee at a time and requires the named test to fail -- **6/6 killed**, restore
verified byte-identical:

| mutation | killed by |
|---|---|
| unwire the pane from `PANES` | `test_every_registered_source_has_a_pane_that_renders_it` |
| render the stale banner unconditionally | `test_health_pane_omits_the_stale_row_on_a_fresh_sample` |
| drop the stale banner entirely | `test_health_pane_leads_with_an_explicit_stale_row...` |
| let an unsampled GUI counter render bare | `test_health_pane_never_fabricates_a_zero...` |
| make `payload_of` trust any payload | `test_health_pane_says_not_measured_when_the_payload...` |
| make `snap_is_stale` always False | `test_health_pane_leads_with_an_explicit_stale_row...` |

`test_every_registered_source_has_a_pane_that_renders_it` is the structural guard, not a one-off
assertion: any FUTURE source added without a pane now fails there rather than being invisible.

### The committed BLOBS, not just the worktree

windows-shell 8b: a Windows worktree can be CRLF while the stored blob is LF, so a local
formatter green can be measured against bytes CI never checks out. That trap was live here --
`_blob_parity.py` on commit `b9a77ad7` reports **15 of 20 files differ between blob and
worktree, in line endings ONLY, 0 CONTENT mismatches, 0 CRLF in any blob**. So the worktree
pytest / basedpyright runs transfer (content is identical), but the FORMAT result did not, and
was re-measured properly:

`_blob_ruff.py` extracts all 18 committed `.py` blobs into a temp tree, copies the repo's
`ruff.toml` in first (a bare temp dir silently falls back to line-length 88 and manufactures a
false red) and preserves each repo-relative path so the `extend-exclude` globs still apply:

```
extracted 18 blob(s), CRLF among them: 0
[blob] format --check exit=0  18 files already formatted
[blob] check        exit=0  All checks passed!
control (mis-formatted blob) format --check exit=1 (must be non-zero)
SUCCESS:blob-ruff
```

The mangled control fired, so the green is not a "ruff found no files" artifact.

## S3 -- vendored copies, and the CI hole that is now closed

`monitorcore` is VENDORED into two committed copies. The source change was propagated
byte-exactly (`_propagate_vendored.py`, read-back asserted) and both gates agree:

* `python tools/measure-guard/vendordrift.py` -> `SUCCESS:vendordrift 2 vendored copy/copies
  ... match ... (37 files each)`, exit 0.
* CI's own `diff -r --exclude=__pycache__ tools/monitorcore/monitorcore
  skills/workflow-monitor/monitorcore` -> identical, exit 0.

BOTH-STATES CONTROL on the live gate (`_vendordrift_control.py`), because a gate never seen to
fire measures nothing: clean -> **exit 0**; one byte appended to
`.agents/skills/workflow-monitor/monitorcore/pane.py` and STAGED -> **exit 1**
(`FAILED:vendordrift 1 drifted path(s) across 1 of 2 ...`); restored -> exit 0. This also proves
the gate reads the INDEX, which is the property the sync claim rests on.

CI WIRING (scope expansion, judged correct and performed). `.github/workflows/quality.yml`
diffed exactly ONE pair, so the SECOND committed copy was in no workflow:

```
grep -c "skills/workflow-monitor/monitorcore" quality.yml = 1   (matcher fires)
grep -c "\.agents/skills/workflow-monitor"    quality.yml = 0   (genuinely absent)
```

The hardcoded `diff -r` step is replaced by `python tools/measure-guard/vendordrift.py`, which
DISCOVERS every tracked `*/monitorcore/__init__.py` so a third copy cannot arrive ungated, and
compares committed blob OIDs rather than CRLF worktree bytes. `.quality/charter_check.sh` ->
`OK -- 6 gates consistent`; the workflow still parses (102 steps).

## S6 -- claude-science: no seam, precise blocker

`grep -rn "ndjson|NDJSON" scripts/claude-science/` -> 0 hits. Positive control on the same file:
`grep -c "Out-File" scripts/claude-science/cs-watchdog.ps1` -> 2. The watchdog appends a
formatted plaintext line, not NDJSON.

BLOCKER: with no NDJSON feed a `ClaudeScienceSource` cannot be a near-copy of
`SystemHealthSource`; it would need the package's first HTTP client, under a 100%-branch gate
and the `dependencies = []` constraint that exists because monitorcore is vendored into
plain-Python skills. Not started. Unblocked the moment `cs-watchdog.ps1` emits NDJSON alongside
its plaintext log. Owner: the CS lane. (That lane did land `/claude-science` this session, but
the command surface is not a machine-readable feed.)

## S4 -- frozen artifacts

The register's cited "62,722-char contract body" is
`~/.claude/harness-restore-20260806/wave1/_l14_body_A.txt`, a code-fenced slice of
`_USER-PROMPTS.md` -- a frozen record of a past owner prompt. It and the dated
`09-RECONCILED-BACKLOG.md` MUST NOT be edited; doing so would falsify the owner's own record.
The live governance surface is `command-center/sources/REGISTER.md` +
`WORK-UNIT-CATALOG.json`.

## The receipt blocker (S5) -- why this lane must NOT write R-M18.json

R-M18 declares `output_path: command-center/receipts/R-M18.json` and
`completion_sentinel: SUCCESS:R-M18`. That file was not written, and the reason is not scope --
it is the repo's own machine-enforced schema.

`platform/schema/receipt.schema.json`, `$defs.receipt_core.allOf[0]`, the `state == "SUCCESS"`
branch, verbatim:

```json
"reviewer": {"properties": {"verdict": {"const": "PASS"},
                            "independent": {"const": true}},
             "required": ["verdict", "independent"]}
```

A SUCCESS receipt REQUIRES an INDEPENDENT reviewer verdict of PASS (plus `tests` with no
FAIL/ERROR/SKIP/NOT-RUN, `negative_controls`, `manifest_registration.registered == true`, and
at least one executed `downstream_consumer`). This lane BUILT the increment, so its own verdict
is by definition not independent. Emitting the receipt here would be self-certification -- the
exact failure the schema exists to prevent, and `command-center/p13_emit_receipt.py` refuses to
write a receipt that fails validation.

Two things therefore remain, both owned by the orchestrator, neither buildable from inside this
lane:

1. An INDEPENDENT reviewer records `verdict: PASS`, `independent: true` against this increment.
2. The receipt is emitted through `p13_emit_receipt.py` (never hand-written), carrying the
   evidence pairs in this document: source probe = the orphan-detector grep with its
   `McpSource` positive control; verifier probe = the 6/6 mutation control and the
   `vendordrift` both-states run. `downstream_consumers` is satisfiable by the executed
   `--once --pane health` frame above.

R-M06 lists R-M18 in its `dependencies`, so the MONITOR program stays gated until (1) lands.

ALSO WORTH CORRECTING IN THE REGISTER (fan-out-contract C2 -- record the refutation, do not
delete the row): R-M18's evidence says `[cockpit]` sits at line 58 of "all three monitors.toml
copies". There are 2 real registries plus 1 TEST FIXTURE
(`tools/monitorcore/tests/fixtures/monitors.toml`, whose line 58 is empty). Correctly scoped:
2 of 2 real registries carry it.

---

## S5 CORRECTED (round 2, 2026-08-12) -- the section above is REFUTED as written

The paragraph beginning *"A SUCCESS receipt REQUIRES an INDEPENDENT reviewer verdict of PASS"*
quotes the schema accurately and then draws a conclusion **wider than the clause**. It is left
in place above rather than deleted, per fan-out-contract C2, and superseded here.

**What was refuted, and by what.** An adversarial audit validated
`command-center/receipts/BLD-0023.json` (which carries `state: "BLOCKED"` and
`reviewer.independent: false`) against the schema and got **0 errors**; flipping only its
`state` to `"SUCCESS"` produced **7** errors. I re-ran that pair independently as LEG 3 / LEG 4
below and reproduce both numbers. So the reviewer clause lives inside an
`if state == "SUCCESS"` branch (`platform/schema/receipt.schema.json`, `$defs/receipt_core`,
`allOf[0]`) and does **not** prevent a receipt from existing -- only a SUCCESS one. Round 1's
"this lane must NOT write R-M18.json" was therefore the right ACTION for the wrong REASON.

**The real blocker, re-measured and mechanically independent** (round 1 read the `state`
conditional; this reads the `unit_id` pattern). Command:

```
python tools/monitorcore/_r2_rm18_receipt.py
```

```
[schema] $defs/unit_id pattern = ^[A-Z][A-Z0-9]*-[0-9]{4}$
[probe ] re.fullmatch(pattern, 'R-M18')    -> None
[ctrl  ] re.fullmatch(pattern, 'BLD-0023') -> <re.Match ... match='BLD-0023'>

[LEG 1] receipt as R-M18 declares itself       -> 2 error(s)
         unit_id:  'R-M18' does not match '^[A-Z][A-Z0-9]*-[0-9]{4}$'
         sentinel: 'SUCCESS:R-M18' does not match the sentinel pattern
[LEG 2 control] identical body, id RM-0018     -> 0 error(s)
[LEG 3 control] BLD-0023 as-is                 -> 0 error(s)
[LEG 4 control] BLD-0023, state -> SUCCESS     -> 7 error(s)
FAILED:R-M18-receipt not written
```

LEG 2 is the load-bearing control: the **same body** under a conformant id validates cleanly,
so every other field of the receipt is already correct and the id shape is the entire
structural blocker. LEG 3/LEG 4 prove the validator is not inert.

`command-center/schema/receipt.schema.json` -- the path the catalog's `defaults.output_schema`
names -- is a generated shim whose only content is
`"$ref": ".../platform/schema/receipt.schema.json#/$defs/receipt_core"`, so the strict pattern
is the one that applies to `command-center/receipts/*.json`.

**Blast radius: R-M18 is 1 of 103, not a special case.** Measured over
`command-center/WORK-UNIT-CATALOG.json` with a two-sided control:

| population | ids | match `^[A-Z][A-Z0-9]*-[0-9]{4}$` |
|---|---|---|
| `items` (the REGISTER rows: R-A, R-B, R-H, R-M, D-0, S-0, T-0, T-1, T-2) | 103 | **0** |
| `work_units` | 2,007 | **2,007** |
| receipts already on disk (`command-center/receipts/*.json`) | 6 | 6 |

All 103 register rows declare `command-center/receipts/<ID>.json` as `output_path`, and not one
of those ids can be a `unit_id`. A one-sided reading ("0 of 103 match") would have been a
detector failure; the `work_units` column is the positive control that the matcher fires.

**What now unblocks R-M18, precisely.** Two steps, both outside this lane's file scope
(`tools/monitorcore/**`, `tools/measure-guard/**`, `docs/monitor/**`):

1. **Resolve the id shape.** Either (a) give the row a conformant id (`RM-0018`) in
   `command-center/sources/REGISTER.md` **and** `WORK-UNIT-CATALOG.json`, keeping `R-M18` as an
   alias so the 19 cross-references and R-M06's `dependencies` still resolve -- small, and it
   fixes one row; or (b) widen `$defs/unit_id` to admit the family -- one edit, but it changes
   the schema 674 catalogued units share, so it needs its own review. **(a) is the smaller
   blast radius.** Do not "fix" it by hand-writing a receipt that skips validation.
2. **Then** an independent reviewer records `verdict: PASS`, `independent: true`, and the
   receipt is emitted through a validating emitter. `_r2_rm18_receipt.py` already builds the
   full body (artifacts, three evidence items with source/verifier probe pairs, failure
   classification, residual unknown) and writes **only** if validation returns zero errors --
   it exits 1 and writes nothing today.

**UNVERIFIED, inline:** whether the R-M family was ever *intended* to emit receipts, or whether
REGISTER rows are a different artifact class that inherited `defaults.output_schema` by
accident. Settling experiment: check whether any of the 103 has ever had a receipt on disk --
as of 2026-08-12 none has, while 6 `work_units`-shaped receipts do. That asymmetry is
consistent with either reading, which is why it stays UNVERIFIED.
