# PHASE 5 — THE REAL PLUGIN

**Unit:** `build/phase5-plugin` · Spec `_USER-PROMPTS.md:10824-10842` · Build root `platform/plugin/`
**Status:** COMPLETE — an installable package exists, its whole lifecycle runs, and every number
below is a pasted command output. Residuals and `NOT-CHECKED` items are named in §8.

Reproduce everything in four commands from the repo root:

```
python platform/plugin/astplugin.py schemas --write --repo-root .
python platform/plugin/astplugin.py build --repo-root . --out platform/plugin/dist
python platform/plugin/measure_package.py --package platform/plugin/dist/ast-integrate-platform-1.0.0.zip
python platform/plugin/lifecycle_rehearsal.py
```

## COVERAGE

| section | status |
|---|---|
| 1. Corrections to the brief | MEASURED |
| 2. Package measurement + forbidden-content enumeration | MEASURED |
| 3. Lifecycle proof (install / update / rollback / repair / uninstall) | MEASURED |
| 4. Failed install leaves no partial state | MEASURED, with a both-states control |
| 5. Closed schema references | MEASURED (19 of 19 plugin-lane tokens) |
| 6. Spec checklist (13 required capabilities) | MEASURED per row |
| 7. Suite / lint | MEASURED |
| 8. Defects found while building · residual · NOT-CHECKED | MEASURED / declared |

---

## 1. Two corrections to the brief

**1.1 — "36 unresolved tokens" is 38, and 19 of them are mine.** Measured with a token scan over
`command-center/WORK-UNIT-CATALOG.json`:

```
$ python - (token scan, see test_schemas.py::test_catalog_references_to_plugin_schemas_now_resolve)
PLUGIN-LANE distinct tokens : 19  referencing work units: 22
  resolving on disk now     : 19 / 19
MARKETPLACE-LANE tokens     : 19  resolving: 0
COMBINED plugin+marketplace : 38
```

18 are `tools/plugin/schema/*.schema.json` plus `.claude-plugin/plugin.schema.json`. The other 19
(`tools/marketplace/schema/*` + `.claude-plugin/marketplace.schema.json`) are the sibling
marketplace lane's and are deliberately left alone. A wider scan of the same catalog finds 54
unresolved `*.schema.json` tokens in total; the remaining 35 belong to the council/design/receipt
surfaces and are out of this unit's scope.

**1.2 — the declared schema paths are NOT under the build root, so the deliverable is split.** The
brief says to build under `platform/plugin/`; the catalog declares the schema paths as
`tools/plugin/schema/…` and `.claude-plugin/plugin.schema.json`. Both were honoured: the
implementation lives under `platform/plugin/`, and `platform/plugin/schemas.py` is the single
in-code source of truth that *materialises* the JSON files at the exact declared paths.
`schemas.check()` compares disk against the module, so a hand-edit of a generated file is a test
failure (`test_schemas.py::test_on_disk_schemas_match_this_module`) rather than silent drift.

**1.3 — the tournament minority report M1 is surfaced, not overridden.** `TOURNAMENT-VERDICT.md`
§4 M1 records that `marketplace-first` held the better answer on the whole Phase 4-6
deployment/licensing surface, and that the live legal defect is **no root `LICENSE`/`NOTICE`
against 31 Apache-2.0 payload entries under a declared MIT**. This unit does **not** decide that:
Stage 0 is an owner licensing decision. What it does do is ship a `LICENSE` **inside the package**
matching the manifest's declared `MIT`, and add a conformance condition that the member exists.
**The root-repo licensing defect M1 names remains OPEN and is the owner's call.**

**1.4 — three `dup-guard` hook warnings were resolved as intentional separations,** verified by
reading each: `tools/agentrail/agentrail/deploy.py` installs an `agentrail.cmd` shim (no
provenance, no drift), `tools/crcp/crcp/lifecycle.py` and `tools/crcp/crcp/health.py` are CRCP
domain code, and `.agents/skills/deep-research/.../cache.py` is an HTTP research cache. None
models a package payload, an install prefix, or live-vs-repo drift. No import coupling exists in
either direction.

---

## 2. Package measurement — enumerated, not asserted

```
$ python platform/plugin/measure_package.py --package platform/plugin/dist/ast-integrate-platform-1.0.0.zip
==============================================================================
PACKAGE MEASUREMENT  ast-integrate-platform 1.0.0
==============================================================================
archive bytes      : 95,093  (budget 4,194,304)
archive sha256     : af62a8836abc4f73e2a6a529dab7ea5e09b7e0828183a7caa3a08965b3067b04
member count       : 45  (budget 200)
uncompressed bytes : 288,265

--- DETECTOR CONTROL: the classifier must flag a known-present item per class ---
  OK   archive     unrelated-bundle.tar.gz      -> archive
  OK   backup      cli.py.bak                   -> backup
  OK   cache       __pycache__/mod.pyc          -> cache
  OK   credential  .env                         -> credential
  OK   log         run.log                      -> log
  OK   transcript  sessions/2026-08-10.jsonl    -> transcript
  OK   vcs         .git/config                  -> vcs

--- FORBIDDEN-CLASS ENUMERATION over the real package ---
  archive     patterns=7   hits=0
  backup      patterns=5   hits=0
  cache       patterns=12  hits=0
  credential  patterns=15  hits=0
  log         patterns=4   hits=0
  transcript  patterns=5   hits=0
  vcs         patterns=6   hits=0

--- EXPLICIT ABSENCE CHECKS (the spec's named prohibitions) ---
  PASS  no .git member
  PASS  no __pycache__ / .pyc member
  PASS  no node_modules member
  PASS  no .log member
  PASS  no .jsonl transcript member
  PASS  no .env / key / credential member
  PASS  no nested archive member
  PASS  no test module shipped
  PASS  archive under budget (4,194,304 B)
  PASS  member count under budget (200)

--- CREDENTIAL-SHAPE SCAN over every member (shapes only, never values) ---
  members scanned=45  blocking=0  advisory=0
==============================================================================
SUCCESS:measure-package no forbidden content, within budget, no credential findings
```

**The zero is meaningful because the detector control ran first**: the same classifier was fed one
known-forbidden path per class and flagged all seven. A "0 hits" from an unproven matcher would
have been worthless. The full 45-member enumeration (every path with its byte size) is printed by
the script and recorded in `platform/plugin/PACKAGE-MEASUREMENT.json`.

**Why minimality is structural, not lucky.** The payload is not "the repo minus excludes". It is an
explicitly enumerated projection assembled by `build.stage()` into a fresh staging tree — 19 runtime
modules, 18 schemas, 1 console entrypoint, 1 hook, 1 command doc, README, LICENSE — then filtered by
a **deny-by-default** allowlist (`build.ALLOW_RULES`, 7 rules each with a stated reason), then
independently **refuted** by the forbidden-class scanner, then budget-checked. A staged file that
matches no rule fails the build (`E_PAYLOAD`), and a rule that selects forbidden content also fails
the build — because that means the rule is wrong.

`platform/plugin/dist/` is gitignored: the archive is byte-reproducible from one command, so the
artifact is not source. Its measurement IS tracked.

---

## 3. Lifecycle proof — every command actually run

`python platform/plugin/lifecycle_rehearsal.py` drives the CLI **as a subprocess** against a real
temp prefix. Abridged real output (full transcript from one command):

```
1. INSTALL (dry run, then real)
$ astplugin install --package ...-1.0.0.zip --prefix <tmp>/prefix --dry-run
SUCCESS:install                                        [exit 0]   # and versions/ was NOT created
$ astplugin install --package ...-1.0.0.zip --prefix <tmp>/prefix
SUCCESS:install                                        [exit 0]
[deployed live files] 2: ['commands/astplugin.md', 'hooks/plugin_health.py']

2. UPDATE 1.0.0 -> 1.0.1 (live override must survive)
SUCCESS:update                                         [exit 0]
[preserved user overrides] ['commands/astplugin.md']
[needs decision]           []

3. ROLLBACK 1.0.1 -> 1.0.0 (no live file may disappear)
SUCCESS:rollback                                       [exit 0]
[live before/after] 2/2  removed=[]
[versions retained] ['1.0.0', '1.0.1']

4. REPAIR after deleting a deployed file
SUCCESS:repair                                         [exit 0]
[restored] ['hooks/plugin_health.py']  [kept override] ['commands/astplugin.md']

5. UNINSTALL (explicit decision required; user edits survive)
$ astplugin uninstall --prefix <tmp>/prefix
FAILED:uninstall E_USAGE Command usage error
  what happened : uninstall requires an explicit user-data decision
  cause         : The command line did not parse, or a required argument was missing.
  impact        : Nothing was read and nothing was written.
  next command  : astplugin --help
  exit code     : 2 (fail-closed)
  choose        : --retain-user-data | --purge-user-data
                                                       [exit 2]
$ astplugin uninstall --prefix <tmp>/prefix --retain-user-data
SUCCESS:uninstall                                      [exit 0]
[removed live] 1  [kept user-edited] ['commands/astplugin.md']  [removed versions] ['1.0.0','1.0.1']

7. REPRODUCIBLE BUILD (same content -> same sha256)
[build 1] af62a8836abc4f73e2a6a529dab7ea5e09b7e0828183a7caa3a08965b3067b04
[build 2] af62a8836abc4f73e2a6a529dab7ea5e09b7e0828183a7caa3a08965b3067b04

==============================================================================
SUCCESS:lifecycle-rehearsal all lifecycle assertions held
```

Rollback and uninstall are the two nobody runs, so they carry **asserted invariants**, not prose:
`rollback` raises `E_TXN` if any live file disappeared or `userdata/` changed (it snapshots both and
compares); `uninstall` refuses to run without an explicit user-data decision and never deletes a
user-EDITED deployed file (1 removed, 1 kept, measured above).

---

## 4. A failed install leaves no partial state — with a both-states control

Step 6 of the rehearsal tampers with `README.md` *after* the inventory was computed, so the archive
is structurally valid and only its content hash disagrees:

```
$ astplugin install --package <tmp>/dist/corrupt.zip --prefix <tmp>/prefix-failed
FAILED:install E_CONFORM Conformance validator rejected the package
  what happened : 1 staged file(s) disagree with the package inventory
  ...
  first         : README.md: hash mismatch
                                                       [exit 51]
[prefix residue after the failed install]
{
  "installed_json": false,
  "live_files": [],
  "lock_held": false,
  "staged": [],
  "versions": []
}
[last journal record] {"event": "abort", "op": "install",
  "reason": "PluginError: E_CONFORM: 1 staged file(s) disagree with the package inventory",
  "steps_undone": 1, "undo_failures": []}

[both-states control] the SAME prefix now accepts the intact package
SUCCESS:install                                        [exit 0]
```

The control is the point: "nothing partial remains" and "the prefix is unusable" produce the same
residue listing. Installing the intact package into that same prefix afterwards distinguishes them.
The same property is asserted as a unit test
(`test_lifecycle.py::test_failed_install_leaves_no_partial_state`) and independently for an
`E_COMPAT` failure (`test_install_negotiation_rejects_an_old_client`).

---

## 5. Closed schema references

19 files created at the paths the catalog declares (22 work units referenced them; 0 existed
before):

```
.claude-plugin/plugin.schema.json
tools/plugin/schema/{compatibility, conformance-report, deploy-provenance, divergence-decision,
  drift-classification, error-taxonomy, exec-policy, failure-policy, health-report, log-record,
  migration-ledger, migration-step, payload-allowlist, payload-inventory, probe-control,
  projection-map, secret-finding, txn-journal}.schema.json
```

Each schema is tested in **three layers plus a sync check**, because any one alone is theatre:

1. it compiles against JSON Schema 2020-12 (a malformed schema validates nothing while passing);
2. the artifact the code **actually emits** validates — no hand-written fixtures, so a schema
   cannot drift from its producer;
3. a targeted mutant of that same artifact **fails** — 18 of 18 artifact schemas have a negative
   control, asserted by `test_every_artifact_schema_has_a_negative_control`, plus 7 mutants for the
   manifest schema;
4. on-disk vs in-code sync, with its own both-states control
   (`test_disk_check_detects_a_hand_edit`).

Several schemas are deliberately built so that a *broken implementation cannot emit a valid
document*: `drift-classification` pins `bidirectional: true` and requires all six classes in
`counts` (a one-directional classifier cannot produce `diverged`); `divergence-decision` pins
`chosen: null` (the tool cannot forge the owner's resolution); `secret-finding` pattern-pins
`excerpt_shape` to a length+entropy descriptor (a finding physically cannot carry the value);
`conformance-report` requires a `N/N conditions satisfied` verdict string, so "nothing blocking" is
not expressible; `health-report` sets `probe_count` minimum 1, so a green report from an empty probe
registry is invalid — and that is exercised by
`test_health.py::test_empty_registry_cannot_produce_a_green_report`.

---

## 6. Spec checklist — the 13 required capabilities

| # | spec requirement | where | evidence |
|---|---|---|---|
| 1 | minimal distributable package | `build.py`, `payload.py`, `packager.py` | §2: 95,093 B / 45 members; deny-by-default allowlist; enumerated absence proof |
| 2 | strict manifest compatibility | `manifest.py`, `.claude-plugin/plugin.schema.json` | 13 parametrised rejection cases; unknown fields REJECTED except reserved `x-`; case-distinct key guard via `object_pairs_hook` (a post-parse dict cannot see it); `min_client`/`max_client` negotiation tested both directions |
| 3 | explicit interpreters for scripts | `proc.py`, `manifest.py` | every `command`/`hook`/`script` entrypoint MUST declare an interpreter (`E_MANIFEST` otherwise); floors probed (`python3 >= 3.10`); Windows `bash` is named explicitly because a bare `bash` there is WSL |
| 4 | Windows/macOS/Linux launch adapters | `proc.launch_argv` | conformance C12: 3 platforms x 2 entrypoints, 0 failures; `pwsh` gets `-NoProfile -ExecutionPolicy Bypass -File`; per-OS argv recorded in the projection map |
| 5 | install / update / repair / rollback / uninstall | `lifecycle.py` | §3, all five run; 30 lifecycle tests |
| 6 | live deployment synchronisation | `deploy.py` | per-file provenance + two-directional drift classifier; all 6 classes have a dedicated test, including `diverged` |
| 7 | cache refresh and invalidation | `cache.py` | content-addressed on the LF-normalised hash; self-verifying; corrupt entry quarantined and the op continues (the ONE declared fail-open row) |
| 8 | health check | `health.py` | 8 probes; `astplugin health-check` exits 50 on failure; `doctor` maps each failure to its exact command |
| 9 | conformance validator | `conformance.py` | 16 conditions, `16/16 conditions satisfied`; every condition asserted POSITIVELY; an unevaluable condition is `NOT-CHECKED` and counts against the total |
| 10 | migration from old layouts | `migrate.py` | 3 legacy fingerprints; steps dry-runnable, idempotent, invertible; a failing step rolls the whole migration back; two matching layouts = `E_MIGRATE` |
| 11 | compatibility diagnostics | `migrate.diagnose` | client + OS + shell + interpreters; flags the Windows-`bash`-is-WSL hazard by name |
| 12 | safe failure behaviour | `journal.py`, `policy.py` | journalled transactions with per-step inverses; crash recovery; prefix lock; §4 residue proof; 15-row fail-open/fail-closed table asserted to agree with the error taxonomy (`policy_taxonomy_agreement() == []`) |
| 13 | clear user-facing error messages | `errors.py` | 16 stable codes, one exit code each; every message prints cause / impact / **exact next command**; a test asserts every `next_command` names a real CLI verb |

Also delivered because the work units require them: `PLUGIN-INVENTORY.json` with per-file hashes and
a release-to-release diff (IMP-0005), argv-array-only execution and file-based argument marshalling
(IMP-0018/0019), scoped MSYS path-conversion suppression (IMP-0020), long-path and reserved-device
safety (IMP-0021), case-collision detection (IMP-0022), three-way merge that refuses overlapping
hunks (IMP-0031), dry-run on every mutating command (IMP-0032), the both-states control harness
(IMP-0044), structured logging with deny-by-default redaction and bounded rotation (IMP-0056), the
exec policy and credential boundary (IMP-0061/0064).

---

## 7. Suite and lint

```
$ python -m pytest platform/plugin -q
252 passed in 31.80s

$ ruff check platform/plugin tools/plugin        # ruff 0.15.17, the version CI pins
All checks passed!
$ ruff format --check platform/plugin
29 files already formatted

$ python -m pytest platform -q
6 failed, 3670 passed, 14 skipped in 239.31s
```

**The 6 failures are not mine and not a regression.** All six are in `platform/marketplace/mkt/`
(5) and `platform/coordination/` (1) — untracked sibling-lane trees whose mtimes are minutes old,
being written concurrently. Two independent signals that they are uncoupled from this unit:
`grep -rn "from plugin\|import plugin\|astplugin" platform/marketplace platform/coordination`
returns **nothing**, and `python -m pytest platform/plugin -q` is 252/252 green on its own. The
pinned 2,767 baseline in the brief is stale (siblings D1/D3 already corrected it to 2,812, and the
tree has grown since).

---

## 8. Defects found while building, residual, and NOT-CHECKED

**Five real defects were found by the tests and fixed.** All five were in code I had just written
and believed correct; each is now covered by a test that goes red without the fix.

1. **The packer was not deterministic** — `PayloadEntry.size` recorded `stat().st_size` (raw bytes)
   while the archive shipped LF-normalised content, so a CRLF working tree produced a different
   inventory and therefore a different archive sha. `fsops.normalised_size` now records the bytes
   that ship. Caught by `test_crlf_source_does_not_change_the_archive`.
2. **An invalid-JSON manifest escaped as a raw `JSONDecodeError`** because the case-collision guard
   parses before the classified path. It now raises `E_MANIFEST` — an unclassified crash has no exit
   code, no cause, and no next command.
3. **Install was flaky on Windows.** `os.replace` of the freshly written staging directory raised
   `PermissionError: [WinError 5]` on 1 of 30 test runs while succeeding on the other 29 — a
   transient handle, not a logic error. `fsops.move_dir` now retries with backoff and falls back to
   copy-then-delete, and the inverse is registered *before* the move so the non-atomic fallback is
   still safe. Both states are tested.
4. **`--dry-run` install created the prefix layout** (`preflight` called `prefix.ensure()`
   unconditionally). A dry run that materialises directories is a partial install with a reassuring
   name. `preflight(mutate=False)` now measures free space against the nearest existing ancestor and
   creates nothing.
5. **A dead exemption in the secret gate.** `DOCUMENTED_PATTERN_FILES` downgraded findings in the
   scanner's own rule file, but it named `lib/payload.py` while the shipped path is
   `lib/astplugin/payload.py` — an untested widening of a security gate that never fired. Removed
   entirely; the gate now has zero exemptions, and a test asserts the symbol cannot come back. The
   14 remaining advisory findings were inspected individually and were all schema URLs/paths
   (`tools/plugin/schema/drift-classification`); a narrow all-lowercase-kebab/slash identifier
   suppression removed them, with a both-states control proving a mixed-case base64 token still
   fires. (Building that control also caught my own test data: naming the variable `BLOB` tripped
   `_looks_like_hash_literal`, so the first draft failed for the wrong reason.)

**Residual — honest limits, each with the experiment that settles it.**

* **The live deployment surface is 2 files.** `deploy.targets` projects `commands/` and `hooks/`
  only, so the drift classifier and the sync/repair proofs run over 2 live paths. The mechanism is
  target-count-independent, but a 2-path proof is not a 500-path proof. Settled by adding a
  `deploy.targets` row for a real `.agents/skills` subtree and re-running the rehearsal.
* **`--live` never points at a real `~/.claude` in any run here.** It defaults to
  `<prefix>/live` precisely so nothing touches the live harness by accident. **NOT-CHECKED:**
  behaviour against a populated real `~/.claude`. Settled by `astplugin sync --live ~/.claude
  --dry-run` and reading the drift counts before any write.
* **Client-version negotiation is tested against synthetic versions.** `min_client = 1.0.0` is the
  honest floor for "reads `plugin.json`". **NOT-CHECKED:** whether any specific Claude Code build
  accepts this manifest's additive fields; I did not install it into a real client. Settled by
  pointing a real client at the unpacked package and reading its plugin list.
* **`node`, `pwsh` and `bash` adapters are resolved but not executed.** Only `python3` is actually
  run (it is the sole declared interpreter). The other three are probed and their argv arrays are
  asserted, not invoked. Settled by adding a trivial entrypoint per interpreter and running each.
* **macOS and Linux are asserted, not executed.** Every adapter and platform branch is exercised
  via the `os_name` parameter on this Windows box; no macOS or Linux run happened. Settled by a CI
  matrix job running `lifecycle_rehearsal.py` on all three runners.
* **No independent cross-vendor review.** **NOT-CHECKED.** Settled by dispatching a fresh-context
  refuter over `payload.py`, `deploy.py` and `lifecycle.py`.
* **The root-repo licensing defect (M1) is untouched and OPEN** — see §1.3. Owner decision.

**One notice to surface, no action taken.** The repository's report-only sensitive-artifact sweep
fired four times while writing `platform/plugin/payload.py`, `cli.py` and `test_schemas.py`
(`sha256:17d36cd9678f`, `sha256:478e83753149`, `sha256:432eac76afa1`). Cause: those files contain
credential-*shape* regexes and synthetic test tokens (e.g. `ghp_bbbb…`), not values. No credential
was read, written, printed, rotated or revoked by this unit — AGENTS.md §9 reserves credential
lifecycle to the owner. The ids are surfaced here as the notice requires.
