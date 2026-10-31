---
title: INTEGRATION
type: note
permalink: dqverify-repo-20261013/docs/mcp-audit/integration
---

# MCPRESEARCH — INTEGRATE lane

Measured 2026-08-13, worktree `C:/Users/Prekzursil/source/ast-integrate`, plus a full Linux
clone (Ubuntu 24.04, git 2.43, python 3.12) because a Windows-only measurement cannot answer
a question about `ubuntu-latest`.

Companion to `MCP-CAPABILITY-AND-DISPOSITION.md` and the four
`ROUND{1,2,3,4}-DEFECT-CLOSURE` ledgers. Those four rounds produced the gates. **This round
makes them run**, and answers the round-1 refutation that was never closed.

> **SUCCEEDED BY `LANE-MCPRESEARCH-INTEGRATE.md`.** This document made the lane's *gates*
> reachable. A later round found the lane's *measurement* was not: round 4 measured the 7
> HTTP rows and nothing joined the number back, so the shipped table still printed `--` in
> seven cost cells. Read that report for the join, its red-proof, and the current residual
> list — several items in §6 below have since moved.

COVERAGE: everything below carries executed output. **NOT measured:** the other ~21
`quality.yml` steps (types, per-package coverage, node, opengrep, gitleaks, osv); whether the
new workflow behaves on a real GitHub runner (it has never run on one); the 7 HTTP-transport
rows' tool surfaces; the `mcpctl` precedence question. Each is in §6 with its settling
experiment.

If it still reads this way, the unit died before measuring anything and no verdict here may
be cited. — *it does not; every section below quotes a real exit code.*

---

## 1. The hole: 20-odd gates and nothing invoked them

```
$ grep -rn "mcp-audit\|probe_capability\|rank_disposition" .github/
(no matches)
```

Four rounds built a DoD ledger with seven negative controls, three invariant red-proofs
(`assert_reversible` / `assert_signal_consistency` / `assert_liveness_consistency`), an EOL
both-states probe, a set-arithmetic overlap report, and a 23-row disposition table. **None of
it ran on any push or pull request.** `disposition.json` could be hand-edited, a mounted
server could vanish from the inventory, or a producer could stop reproducing its own artifact
— and all three would land on main green. That is the same shape as the sibling lane's
"fixed producer that nothing invokes", in a different lane.

## 2. What is wired

| | |
|---|---|
| `.github/workflows/mcp-audit.yml` | NEW. `push`(main) + `pull_request` + `workflow_dispatch`, `ubuntu-latest`, python 3.11, `fetch-depth: 0`. Two steps: the gate's own self-test, then the gate. |
| `command-center/mcp-audit/ci_gate.py` | NEW. The CI entry point: 15 planned invocations over 14 gates, real exit code per child, a no-silent-shrink inventory invariant, and producer determinism. |

**Why its own workflow file and not a job in `quality.yml`.** `quality.yml` is a closed gate
set policed bidirectionally by `.quality/charter_check.sh`: a `gate-<slug>` marker there with
no matching `- slug:` in `.quality/charter.yml` turns the *existing* lint job red, and
`ci/tests/test_charter_consistency.py` pins that in both directions. `charter_check.sh` reads
only `quality.yml`, so a separate workflow carries no charter obligation — the shape
`no-runtime-junk.yml`, `skill-dual-write.yml` and `p2next-rail-count.yml` already use. It also
touches no file a sibling lane is editing. Verified after writing:

```
$ python -c "yaml.safe_load(...)"   ->  4 steps in order, runs-on ubuntu-latest, fetch-depth 0, 0 CRLF
$ bash .quality/charter_check.sh    ->  OK -- 7 gates consistent   (exit 0)
```

**Why `fetch-depth: 0`.** Four gates read pinned historical blobs — `b9dce830` (the round-1
defect reproduction), `630bb8af` (the both-states control that must FAIL), `673cd180` and
`2caafe53` (the false-CRLF sentences). On a shallow checkout every one of them fails closed.

**What the gate asserts**, in order:

1. **No silent shrink.** Every `*.py` in the directory is in `CI_PLAN` (with an expected exit
   code) or in `EXCLUDED` (with a written reason). A file in neither fails the run. This
   invariant caught its own author mid-build: adding `_i4_determinism_diff.py` turned the gate
   red until it was classified.
2. **Real exit code per child**, never through a pipe — a shell pipeline reports the *last*
   command's status, which turns a red gate green.
3. **Both states.** `_r2_dod_check.py 630bb8af` is planned with expected rc **1**. Green on
   the current tree means nothing unless the same ledger is observed going red on a blob that
   genuinely violates it.
4. **Producer determinism.** `rank_disposition.py` and `overlap_report.py` are re-run into a
   temp file and compared **byte-for-byte** with the committed blob. Both write with
   `newline="\n"` explicitly, so this is exact on either platform — no line-ending
   normalisation, which would have hidden precisely the class of defect round 4 spent itself
   on.

## 3. Four gates did NOT run on Linux, and one of them was the DoD ledger

Every gate was authored on Windows. Wiring them into `ubuntu-latest` on the assumption that
Python is Python would have shipped a **permanently red job**. Measured instead, in a full
clone inside the WSL filesystem — *not* the linked worktree, whose `.git` is a file holding a
Windows path that Linux git cannot resolve, so every probe run there returns clean zeros:

```
$ python3 command-center/mcp-audit/_i1_ci_portability.py       # BEFORE
  PORTABLE 11/15
  NOT PORTABLE: ['probe_capability --control', 'redproof_control',
                 'r4_redproof', 'dod_check @ HEAD']
```

| # | root cause, measured | fix |
|---|---|---|
| P1 | `dod1()` used `pathlib.Path(src).is_absolute()`, which binds to the HOST flavour. The 23 recorded `source_file` values are Windows drive paths, so on POSIX **23 of 23** read as relative. It printed as only four because `main()` truncated with `problems[:4]` — a display artifact that nearly cost another wrong root cause. | `absolute_in_any_flavour()` (Windows **or** POSIX); the on-disk existence check is scoped to `native_to_host()` and its coverage is now PRINTED (`23 verified here, 0 not checkable`) rather than silently weakened. New negative control `relative-source-file`, because that branch had **no** control at all — which is why a bug lived in it. Controls went 6 → 7. |
| P2 | `probe_capability.run_control()`'s SHIM state regresses a Windows-only defect (CreateProcess does not apply PATHEXT). POSIX has no PATHEXT and no `.cmd`, so the state is not inconvenient there, it is **unobservable** — and a control that cannot fail is not a control. | Skipped on POSIX with the reason printed, plus an `expected_states` FLOOR (4 on nt, 3 on posix) so an accidental skip is loud instead of shrinking the control to whatever ran. |
| P3 | `redproof_control.py`'s `no-pathext-resolve` mutation had nothing to detect on POSIX, so its baseline was already red. | Same treatment, plus a mutation-count floor. |
| P4 | `_r4_redproof` PART B asked `bool(old_dod1(dropped))` — "did the old gate say *anything*?". Under P1 the old gate objected to all 23 paths, so it scored "not blind" while remaining exactly as blind to the ABSENCE it was being tested on. **A control that cannot distinguish the two hypotheses.** | Scoped to the property under test: does either gate emit a problem *naming that server as absent*? Unrelated noise is counted and printed, never folded into the verdict. |

```
$ python3 command-center/mcp-audit/_i1_ci_portability.py       # AFTER
  PORTABLE 15/15
  SUCCESS:ci-portability measured 15 gates, 15 portable
```

Windows was re-run after every fix and never regressed
(`SUCCESS:mcp-audit-ci-gate 15/15 gates behaved`).

### 3b. A fifth defect the determinism check found on its own

The first run of the wired gate in the Linux clone went red on something no portability probe
would have caught:

```
FAIL disposition.json: regenerated 27688 B != committed 28636 B
```

`_i4_determinism_diff.py` named it: `definition_scope` and `source_file`, **null on 23 of 23
rows**. `rank_disposition.py` sources those two fields from `load_specs()`, which reads the
LIVE `~/.claude.json` and `~/.mcp.json` — files that exist only on the box that produced the
sweep. **The producer could not reproduce its own artifact anywhere except this machine**, and
the two fields it lost are exactly DoD1's two inventory fields.

Fixed by falling back to the COMMITTED round-2 capability sweep, which recorded both fields per
row at probe time (23/23 present). Same evidence, not a guess. Live config still wins when
present. Both platforms now regenerate byte-identically — asserted, not asserted-about:

```
  ok  disposition.json       byte-identical to the committed blob (28636 B)
  ok  overlap-report.json    byte-identical to the committed blob (3738 B)
```

Also hardened while here: `_r4_selfcheck.py` left `fired = None` when its positive control
file was absent and fell through to `fired is False` → `False`, so deleting the fixture would
have turned a proven sweep into an unproven one that still printed "control fired". "Control
missing" and "control passed" must never be the same outcome. It now fails closed.

## 4. Red-proof: the gate goes RED when the work rots, and the pre-existing CI does not

`command-center/mcp-audit/_i3_redproof.py`, run in a **throwaway full clone** on Linux with
the integration committed into it, re-run against the FINAL formatted bytes. Receipt:
`command-center/mcp-audit/I-REDPROOF.json` (base `2f7f0f0b`).

Each injection is **committed**, because the gate reads committed blobs and a working-tree
edit would prove nothing. Each carries an effectiveness control (the tree really changed).

| injection | ci_gate | caught by pre-existing CI |
|---|---|---|
| **INJ-A** a mounted server vanishes from the inventory (drop the `cloud-hub` row) | **rc=1**, 3 problems | none |
| **INJ-B** a measured number hand-edited to a stale value (`cloud-hub` tool_count 424 → 409, the value `impact.py` still carries) | **rc=1** | none |
| **INJ-C** a recommendation becomes irreversible (`DISABLE` → `REMOVE`) | **rc=1**, 2 problems | none |
| **INJ-D** a new gate file lands unwired | **rc=1** (`new file(s) in neither CI_PLAN nor EXCLUDED`) | `quality/ruff-format` — recorded as also-caught, so the necessity claim excludes this row |
| **INJ-E** the both-states anchor is re-pointed at `HEAD`, silently turning the pair into two identical green runs | **rc=1** | none |

`BASELINE ci_gate rc=0` before, `RESTORED ci_gate rc=0` after — without both, the injections
prove nothing.

**"Blind" here is a measurement, not an absence.** Two guards make it one:

* The signal is `(exit code, hash of output)`, not exit code alone. `ruff format --check` was
  already red on this tree from concurrent lanes at one point; an rc-only test would have
  scored it "unchanged" for every injection and mistaken a permanently-red gate for a blind one.
* **A liveness control per pre-existing gate.** Each is given a defect it MUST see, and the run
  fails rather than publish an unmeasured blindness claim:

```
  ok  quality/ruff-check   rc=0/out=82b3e6a6 -> rc=1/out=f7a1f9c6  moved=True   (a file that does not parse)
  ok  quality/ruff-format  rc=0/out=caad85eb -> rc=1/out=3ce84d12  moved=True   (non-canonical spacing)
  ok  quality/charter      rc=0/out=680f54ab -> rc=1/out=81e90673  moved=True   (an unclaimed gate-<slug>)
  ok  p2next-rail-count    rc=0/out=d5287eb8 -> rc=1/out=27c0ec8d  moved=True   (the rail number rotated)
SUCCESS:i-redproof 5/5 injections turn the gate RED, 4/4 blind-set liveness controls fired
```

This control earned itself immediately. Its first version used `uvx ruff@0.15.17` and read
`rc=2` in **both** states — WSL had lost DNS, so the tool never ran and every "blind" row was
unproven. The run failed closed and said so. It now uses the ambient `ruff`, verified at
exactly the pinned `0.15.17`, with the resolved path recorded in the receipt.

**Scope of the blindness claim, stated because a wider one would be false:** four pre-existing
gates were measured. The other ~21 `quality.yml` steps were not run. None of them evaluates the
semantics of a JSON measurement artifact — but that is reasoning, not measurement, and it is
labelled as such here and in the script.

## 5. The contested round-1 refutation — CONFIRMED by execution, and now scoped

The lane's adversarial round returned `audit_holds: false`, `build_is_sound: false`. Its
`must_fix`: **`call_verified` measures "the process spawns and advertises a tool surface", not
capability** — and its worked example was `searxng`, which ships `call_verified: true` with
`tool_count: 4`.

Rounds 2 and 3 fixed adjacent things (the legend/field contradiction D1; the verified-and-errored
liveness shape) but **never settled the semantic claim**. So this lane ran the experiment
instead of naming it. A real in-session call to the server in question, read-only:

```
mcp__searxng__searxng_instance_info  ->
  {"available": false,
   "message": "SearXNG /config is unavailable; no configured instances answered
               capability discovery.",
   "instancesUnreachable": [{"sourceUrl": "http://127.0.0.1:8890", ...}]}
```

**The refuter was right.** The stdio handshake is a real MCP call — it is not a spawn check —
but `initialize` + `tools/list` proves the process starts and *advertises* a surface, and
nothing more. `searxng`'s backing instance is unreachable, so not one of its four advertised
tools can do its job, while the row reads `handshake_verified: true`.

What changed, and what deliberately did not:

* **The emitted legend is narrowed**, in the module constant `S4_LEGEND` that
  `assert_signal_consistency()` reads — so the text that ships and the text the invariant checks
  remain one object. It now states the scope and carries the executed counter-example, so a
  consumer joining on the field (the `mcpctl` wiring is the next step) sees it in the artifact
  rather than in prose it will never read.
* **The module docstring's gloss `"does it actually work"` is deleted.** That sentence, not the
  field, was the over-read.
* **No disposition moved**: `DISABLE 1 / INVESTIGATE 2 / KEEP 20`, before and after. A
  disclosure fix that moves a verdict is a different change, and this one did not. `searxng`'s
  DISABLE rests on exact set arithmetic (all 4 tool names a strict subset of `search-hub`'s 68,
  0 unique), not on `call_verified` — so the refutation does not disturb it. If anything the
  new measurement strengthens it.
* **NOT done, and it is the honest residual:** the field is not renamed, and the other 15
  handshake-verified rows have not been re-probed with a real tool call. The scope is now
  disclosed at the point of use; it is not eliminated. §6 names the experiment.

## 6. Residual — what is not done

1. **15 of 16 handshake-verified rows have no capability-in-use evidence.** Only `searxng` was
   probed. **UNVERIFIED** how many others advertise a surface over a dead backend.
   *Settling experiment:* one cheapest-read-only tool call per server, recorded into a committed
   JSON that `rank_disposition.py` READS.
   > **The parenthetical here was STALE WHEN WRITTEN, corrected rather than deleted.** It read
   > *"the shape `S4_EXECUTED` should have had from the start — it is currently a hand-typed
   > dict of literals in the producer … which is still true"*. It was not still true.
   > `git grep -n S4_EXECUTED -- command-center/mcp-audit/` returns no definition in
   > `rank_disposition.py`; the only hits are docstrings in `s4_evidence.py` and
   > `_g3_backend_liveness.py` **describing the defect they closed**. The records moved into
   > `s4-evidence.json` in round 2 and `rank_disposition.py:770` loads them via
   > `s4_evidence.load()`, which fails closed when the file is absent. Naming a fixed defect as
   > live is the mirror of the error this lane keeps finding — a sentence wider than its
   > evidence — and it sends the next round to re-fix something already done.
2. **The workflow has never run on a real GitHub runner.** Everything here is a local Ubuntu
   24.04 clone with python **3.12**; CI pins **3.11**. *Settling experiment:* the first
   `workflow_dispatch` after merge. Risk assessed **low** (no 3.12-only syntax; `uvx` is not
   used by the gate) but it is unmeasured, and WSL had no DNS during the red-proof so nothing
   here exercised a network-dependent step.
3. **The R1 target is still not done:** wiring this producer into `tools/mcpctl`'s four null
   fields and `tools/monitorcore`'s pane. Out of this lane's declared file scope
   (`docs/mcp-audit/**`, `command-center/mcp-audit/**`). §3b removes the blocker that made it
   impossible — the producer is now reproducible off the owner's box.
4. **The `searxng` DISABLE is recommended, not executed.** A config mutation, out of scope, and
   it must go through `mcpapply` dry-run → backup → apply. Note a root disable does not prevent
   the spawn and saves no RAM; it needs `DISABLE_PREFERENCE`.
5. **`_r4_selfcheck` inspects only the blobs of the tip commit.** On a PR with several commits
   the earlier ones are unchecked. *Settling experiment:* widen it to
   `git diff --name-only <base>...<head>`; not done here to avoid changing a gate whose current
   semantics four rounds of receipts are written against.
6. **Two Windows-only control states never run in CI** (the PATHEXT SHIM state and its
   mutation). They run locally on every Windows invocation and are floor-asserted there. A Linux
   runner cannot regress a Windows-only code path, but an edit to `RESOLVE_SHIMS` would go
   unnoticed by CI.
7. **Carried over, still open:** the `mcpctl` "mounted but not enabled" precedence question;
   the bytes-vs-tokens reconciliation with `impact.py` (whose `cloud-hub -- 409 tools` is stale
   against a twice-measured 424 — INJ-B is that rot, weaponised); `agent-mail`'s `health_check`
   reporting port 8811 while 8812 serves; whether the three playwright rails differ
   BEHAVIOURALLY (their 24 tool NAMES are byte-identical, which is why they are INVESTIGATE and
   not DISABLE).
8. **Explicitly NOT claimed: that CI is green.** Four pre-existing gates were executed here; the
   other ~21 were not.

## 7. Confidence

* **Almost certain (90-99%)** — the four Linux portability defects and their fixes (measured
  11/15 → 15/15 in a real Linux clone, with Windows re-verified at 15/15 after every change);
  the producer-determinism defect and its fix (a named 948-byte diff on two named fields ×23
  rows, then byte-identity on both platforms); that all five injections turn the new gate red
  and four of five are invisible to the four pre-existing gates measured (executed, with an
  effectiveness control per injection and a liveness control per pre-existing gate, all fired);
  that `searxng` advertises four tools over an unreachable backend (a real tool call returned
  `available: false`, naming the unreachable endpoint).
* **Likely (55-80%)** — that the workflow passes first time on a real runner. The gate is green
  on Linux and the only untested delta is python 3.11-vs-3.12 and the GitHub checkout shape.
* **Uncertain (20-55%)** — that no sixth portability or determinism defect remains. Every round
  of this lane has found three to five; this one found five. That is not obviously converging,
  and a self-review is not the settling experiment — another independent verify pass is.
* **UNVERIFIED, with its experiment named inline** — every item in §6.