---
title: MON-INTEGRATE
type: note
permalink: dqverify-repo-20261013/docs/monitor/mon-integrate
---

# MON lane — INTEGRATE stage (the last stage; the loop is over)

STATUS: **MEASURED.** Every claim below carries a pasted command output or names the file:line it
was read from. Where an earlier sentence in this lane was wider than its evidence, the earlier
wording is recorded as REFUTED rather than deleted.

COVERAGE: complete for the integration shipped here (the gate, its CI wiring, its both-states
control, and its cross-platform measurement). NOT measured, and stated as such below: any
GitHub Actions run, and a whole-repo fresh-clone suite.

---

## 1. What was integrated, and why this one

The MON increment (the cockpit's 6th pane, `health`) was BUILT and vendored in earlier rounds.
This stage answers a different question: is it **reachable**, and is anything **watching** that it
stays reachable?

Three gates already guard the monitor registry, and every one of them stops short of running
anything:

| gate | what it proves |
|---|---|
| `tools/measure-guard/vendordrift.py` | every committed copy of `monitorcore` is byte-identical |
| `tools/monitorcore/tests/test_registry_commit_truth.py` | the registry mirrors match IN THE COMMIT, and each stanza's entry is a TRACKED path |
| `tools/monitorcore/tests/test_registry_shipped.py` | the entry file exists on THIS BOX's working tree |

Byte-identical, tracked and present are three different questions from **launches**. A shim whose
import breaks, a vendored copy missing the module the shim imports, or an entry that exits 0
without ever rendering, is green in all three. That is the silent-no-op shape this estate has
already been bitten by once — `ui-audit` reverting to a build where `main()` never runs: exit 0,
no artifacts, no error, and every subsequent "audit passed" vacuous.

Detector control for the absence, because a bare grep proves nothing on its own:

Counted on the COMMITTED blobs at HEAD (`git cat-file -p HEAD:<path>`), so the "before" state is
the one CI actually checks out, not my edited working tree:

```
launchpath|unified_board, HEAD blob of all 7 workflows:
  autofix-models 0 · codex-runner 0 · dependabot-auto-merge 0 · no-runtime-junk 0
  quality 0 · routing-benchmark 0 · skill-dual-write 0
CONTROL  HEAD:quality.yml occurrences of "monitorcore"    = 22   (the matcher fires)
CONTROL  HEAD:quality.yml occurrences of "measure-guard"  = 10   (the matcher fires)
```

So: **nothing in this repository has ever executed a registered monitor.** `tools/measure-guard/
launchpath.py` does, and is wired into CI.

## 2. What the gate does

It materialises the registry and the probed skill directory from the blobs git actually STORED,
into a throwaway tree, and EXECUTES the registered entry there in a bounded probe mode, requiring
BOTH exit 0 AND a marker proving the program reached its board.

* **Blobs, not the working tree.** `git ls-files -s -z` for the OIDs, one `git cat-file --batch`
  for the bytes. `git archive` is deliberately NOT used — on Windows it applies export-time EOL
  conversion and hands back CRLF, i.e. it verifies the wrong bytes. This makes the gate the
  fresh-clone-equivalent launch proof the fleet audit found existed nowhere.
* **Both mirrors, independently.** The skills root is derived per registry
  (`skills/…` and `.agents/skills/…`), never hardcoded, so a `.agents`-only rot cannot hide.
* **Every stanza accounted for by name.** 1 of 6 is executed (`cockpit`); the other 5 carry a
  written exemption in `EXEMPT` (four interactive pollers with no bounded probe mode, plus `crcp`,
  which is quarantined estate-wide and must not be started). Both directions fail closed: a NEW
  stanza that is neither probed nor exempt FAILS, and a probe/exemption naming a stanza the
  registry no longer has FAILS. A green cannot be computed over nothing, and the policy cannot rot
  into fiction.
* **Fail closed, six ways:** empty `git ls-files`; zero registries discovered; a registry parsing
  to zero stanzas; a probed entry that is untracked; a skill dir that materialises zero files; a
  probe that times out.

Honest scope, inline: this gate proves the cockpit stanza LAUNCHES AND RENDERS. It does **not**
prove the other five monitors launch, and it does not assert anything about the CONTENT of the
health pane's numbers beyond the pane being reached.

## 3. The one executable end-to-end check, and it going RED without the integration

`tools/measure-guard/_launchpath_control.py` runs the SHIPPED `scan()` against THIS repository in
four states. It mutates an in-memory `oids`/`blobs` pair only — no tracked file is written or
staged — and the "rolled back" bytes are real committed history from `b9a77ad7^`, not a
hand-edited approximation.

```
  [PASS] LEG 1 as committed                                   -> GREEN
  [PASS] LEG 2 vendored copies rolled back to b9a77ad7^       -> RED :: .agents/skills/monitor-launcher/monitors.toml:[cockpit]
                                                                        -> .agents/skills/workflow-monitor/unified_board.py
                                                                        did NOT launch: exit 2: [--subagents-dir S…
  [PASS] LEG 3 [cockpit] stanza deleted from both mirrors     -> RED :: launch policy names [cockpit] but the registry has no
                                                                        such stanza - the policy has gone stale
  [PASS] LEG 4 no-op comment appended (inverted control)      -> GREEN
SUCCESS:launchpath-control 4/4 legs behaved as required
```

LEG 2 IS the "integration missing" state: roll the four vendored modules back to the bytes that
were committed immediately before the health pane, and `--pane health` is no longer a valid
choice, so the launch exits 2 and the gate reports it. LEG 4 is what stops this being a rubber
stamp in the other direction — a harness that reported RED for any perturbation would score
identically on a semantically empty edit.

## 4. Cross-platform: the gate runs on Linux, measured, not assumed

The gate runs in CI on `ubuntu-latest` and every local run of it is Windows. A Windows-only green
is the exact shape this program keeps getting burnt by, so
`tools/measure-guard/_launchpath_linux_probe.py` materialises the SAME committed blobs and runs
the entry under BOTH interpreters:

```
  materialised 72 committed blobs to …\Temp\launchpath-linux-a6ub77k7
  [PASS] windows 3.14.6      : exit=0 marker=True :: panes 1:codex 2:agents 3:workflows 4:databricks 5:mcp [6:health] …
  [PASS] linux (wsl Ubuntu)  : exit=0 marker=True :: panes … [6:health] … | health [unreachable] age=- [unreachab…
SUCCESS:launchpath-linux the gated launch renders on BOTH platforms
```

The Linux leg renders the pane as `[unreachable]` — there is no Windows sentinel event log there —
and **degrades instead of crashing**, which is precisely the CI behaviour required. WSL Ubuntu
reports `Python 3.12.3`; CI pins `python-version: "3.11"` and `tools/monitorcore/pyproject.toml:9`
declares `requires-python = ">=3.11"`, and the `gate-tests-coverage monitorcore` step already
imports the whole package in that same 3.11 job. The probe is NOT wired into CI (no runner has
`wsl.exe`); it is an operator-run corroboration.

## 5. Gates at the end of this stage

```
python -m pytest tools/measure-guard/tests -q      ->  96 passed in 52.03s   (70 before; +26 is this module)
python tools/measure-guard/launchpath.py           ->  SUCCESS:launchpath 2 launch(es) from committed blobs
                                                       across 2 registry mirror(s); 5 stanza(s) exempt
python tools/measure-guard/_launchpath_control.py  ->  SUCCESS:launchpath-control 4/4 legs
python tools/measure-guard/_launchpath_linux_probe.py -> SUCCESS:launchpath-linux both platforms
uvx ruff@0.15.17 check tools/measure-guard/        ->  All checks passed!
uvx ruff@0.15.17 format --check tools/measure-guard/ -> 18 files already formatted
python -c "yaml.safe_load(quality.yml)"            ->  YAML OK, steps: 104; measure-guard step found: 1;
                                                       launchpath in run: True
bash .quality/charter_check.sh                     ->  OK -- 6 gates consistent
```

### Fresh-clone verification (working-tree green is not clone green)

The gate and its tests were re-run from real clones, not from this working tree, both created
with `-c core.autocrlf=false -c core.eol=lf` — the Linux-runner-equivalent byte form:

| leg | clone tip | result |
|---|---|---|
| `python tools/measure-guard/launchpath.py` | `0ae5b2a` (this stage's commit) | `SUCCESS:launchpath` 2 launches, exit 0 |
| `python -m pytest tools/measure-guard/tests -q` | `9f91d47` (a sibling's later tip; `git merge-base --is-ancestor 0ae5b2a6 9f91d47` → true) | **96 passed** in 71.26s |

And the CI lint gate re-run against the COMMITTED LF blobs rather than the CRLF worktree
(`tools/monitorcore/_blob_ruff.py 0ae5b2a6`):

```
extracted 4 blob(s), CRLF among them: 0
[blob] format --check exit=0   4 files already formatted
[blob] check        exit=0   All checks passed!
control (mis-formatted blob) format --check exit=1 (must be non-zero)
SUCCESS:blob-ruff
```

MY OWN BROKEN DETECTOR, caught and disclosed rather than cited: a PowerShell
`[System.IO.File]::ReadAllBytes("tools/measure-guard/launchpath.py")` intended to count CR bytes
in the clone resolved the RELATIVE path against the process cwd, not the `Push-Location` dir,
threw, and then printed `CR bytes: 0` from the empty result. That zero measured nothing and is
NOT used. The CRLF claim rests only on the `_blob_ruff.py` line above, which counts the extracted
blobs directly.

`basedpyright` is NOT run against `tools/measure-guard` by CI (the types job names
`mcp-manager`, `scholarly-access`, `taskwatch`, `monitorcore`, `agentspec`, `mcpctl` and not this
package). Run manually it reports 3 errors on the new files, of which 2 are the `from conftest
import …` shape every existing measure-guard test module already uses, and 1 is
`description=__doc__.splitlines()[0]`, which all six pre-existing tools in this package also use
(control: the same tool reports 1 error on the untouched `vendordrift.py`). Left consistent with
the package rather than diverged for one file; disclosed rather than silently fixed in isolation.

## 6. Residual — honestly scoped, and what would settle each

### 6.1 R-M18 IS STILL NOT ENROLLED. The blocker is measured, and it is NOT the one round 1 named.

`command-center/receipts/R-M18.json` does not exist (`ls` → No such file). Re-measured here,
independently of the earlier rounds, by reading the schema and the catalog directly:

```
unit_id pattern (platform/schema/receipt.schema.json $defs.unit_id): ^[A-Z][A-Z0-9]*-[0-9]{4}$
register items matching unit_id:      0/103
work_units matching unit_id:      2007/2007
CONTROL rx('BLD-0023') -> True        rx('R-M18') -> False
```

REFUTED (round 1): *"the blocker is the SUCCESS branch requiring an independent reviewer."* That
clause is real and correctly quoted, but it gates a `state="SUCCESS"` receipt only; a
`state="BLOCKED"` receipt is schema-valid without a reviewer, and
`command-center/receipts/BLD-0023.json` is exactly that. CORRECTED, and this is the narrower true
blocker: **the register's own id shape cannot produce a valid receipt at all.** `R-M18` is 1 of
103 register rows in the same position, and every one of them declares
`command-center/receipts/<ID>.json` as its `output_path`.

`R-M18`'s `next_smallest_action`, verbatim: *"Enrol the cockpit into the unified contract at
normal MONITOR priority. It is already reachable — a [cockpit] stanza sits at line 58 of all three
monitors.toml copies (R-M01, closed on that evidence) — so this is a contract/registration change,
not a build."* Two corrections to that premise, both measured here: the stanza is at **line 72**
(it moved when `[csmon]` landed), and there are **2** registries plus **1** test fixture, not
three copies. The reachability premise itself HOLDS and is now executable rather than asserted —
that is what section 3 proves.

What remains is owner/orchestrator-owned and was NOT done here: (a) decide the id mapping (either
widen `$defs.unit_id`, or give register rows an explicit emittable `receipt_id` alias), then
(b) emit the receipt with `command-center/p13_emit_receipt.py`. Both live under
`command-center/` and `platform/schema/`, outside this lane's declared file scope, and
`command-center/` currently carries many uncommitted sibling edits — staging into it would sweep
another lane's work. **Do not let anyone hand-write a SUCCESS receipt.** R-M06 depends on R-M18,
so MONITOR stays gated. Settling experiment: after the id decision, `python
command-center/p13_emit_receipt.py` for that unit must exit 0 and the file must validate.

### 6.2 No CI run has executed any of this (UNVERIFIED, inline)

Local commands only. Confidence it passes on a real runner: **ALMOST CERTAIN, low end (about
90%)** — raised from the earlier rounds' bare guess by three independent legs, each of which
removes a distinct failure mode: the Linux interpreter leg (section 4) removes "the cockpit is
Windows-only"; the fresh LF-clone leg above removes "it only works in this working tree"; and
`git ls-files` / `git cat-file` are already relied on by the `vendordrift.py` step in the same
job, which removes "git is unavailable or shaped differently there". What is genuinely left is
runner-specific and small: `actions/checkout` must provide a working `.git` (it does), CI pins
Python 3.11 while the two legs measured 3.14.6 and 3.12.3, and the 240 s probe timeout must hold
on a cold runner (the local launch takes about 3 s). Settling experiment: the next Actions run on
this branch. It is NOT claimed as passed.

### 6.3 The gate executes 1 of 6 stanzas

`wfmon`, `agentmon`, `codexmon`, `csmon` and `crcp` are exempt with written reasons. Four of them
could in principle gain a `--once` probe mode; `crcp` must not. That is a follow-on, not a defect
of this gate — the exemptions are data, and the gate fails if one goes stale. Settling experiment:
add a `--once` renderer to `workflow_monitor.py`, then move `wfmon` from `EXEMPT` to `PROBES`.

### 6.4 Not built, deliberately

`TaskwatchSource` / a 7th pane, and `ClaudeScienceSource`. The latter is still blocked on a
machine-readable feed: `scripts/claude-science/cs-watchdog.ps1` emits formatted plaintext
(`grep -c Out-File` = 2 on that file, CONTROL `grep -c ndjson` = 0). A `[csmon]` launcher stanza
exists, but a launcher is not a feed.

### 6.5 Register rows still carry refuted evidence

R-M02 / R-M18 hold `[inherited]` evidence already disproved elsewhere in this lane ("13 stale
files" → 0 real drift; "all three monitors.toml copies" → 2 registries plus a fixture). Recording
those corrections belongs to whoever owns `command-center/sources/REGISTER.md`. Record the
refutation; do not delete the rows.

## 7. Scope disclosure

Commit `0ae5b2a6` — *feat(measure-guard): launchpath — execute the registered monitor, not just
check its bytes* — 5 files, +1078, staged by explicit pathspec (`git diff --cached --name-only`
showed exactly those 5 and no foreign path; the index was empty beforehand).

In declared scope (`tools/measure-guard/**`, `docs/monitor/**`):

```
tools/measure-guard/launchpath.py                 (new, the gate)
tools/measure-guard/tests/test_launchpath.py      (new, 26 both-states tests)
tools/measure-guard/_launchpath_control.py        (new, live-repo 4-leg both-states control)
tools/measure-guard/_launchpath_linux_probe.py    (new, Windows-vs-Linux corroboration)
docs/monitor/MON-INTEGRATE.md                     (this file)
```

OUT of declared scope, one file, with the reason stated rather than hidden:

```
.github/workflows/quality.yml   +1 run line and its comment block in the EXISTING
                                `gate-tests-coverage measure-guard` step.
```

A gate that no CI runs is not a gate, and "wire it into CI" is the integration this stage was
asked for. The file was confirmed clean (`git status --porcelain` empty for it) immediately before
the edit and staged with an explicit pathspec, so no sibling work was swept. `tools/monitorcore/**`
was NOT modified by this stage. `command-center/**`, `platform/**` and
`command-center/adversarial/**` were NOT touched.

## 8. No mtime-based stall claim

Nothing shipped here reads a file mtime. The gate is content-addressed end to end (blob OIDs, blob
bytes, a subprocess exit code, a stdout marker). Detector, with the control that the matcher can
fire:

A bare `grep mtime` is a BROKEN detector here — it matches `fro`+`mtime`+`stamp` inside
`datetime.fromtimestamp`, and an earlier round of this lane shipped that false positive. The
matcher below excludes that substring, and is proven able to fire:

```
lines containing "mtime" (excluding fromtimestamp):
  tools/measure-guard/launchpath.py                = 0
  tools/measure-guard/_launchpath_control.py       = 0
  tools/measure-guard/_launchpath_linux_probe.py   = 0
  tools/measure-guard/tests/test_launchpath.py     = 0
CONTROL tools/monitorcore/monitorcore/unified.py   = 6   (the matcher fires)
```

`tools/monitorcore/monitorcore/stall.py` and its two-signal classifier were not touched.