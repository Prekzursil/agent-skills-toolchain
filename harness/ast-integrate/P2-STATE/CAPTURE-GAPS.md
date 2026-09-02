# CAPTURE-GAPS — units that fail because an input was excluded from the 02.09 capture

Rule (cloud mandate): a unit whose probe needs a file that is absent from `harness/ast-integrate`
and that nothing in the tree generates is recorded here with the unit id and the missing path —
never guessed or fabricated. Each row names the capture rule most likely responsible (see
`CAPTURE-EXCLUSIONS.md`); the owner can add a `KeepOversized`/path entry and re-run
`sync-from-live.ps1 -Only ast-integrate`. Rows are appended as gaps are confirmed by a writer who
searched the tree for a generator first (`disk-verified` by the orchestrator's own measurement).

| unit | missing path (repo-relative) | evidence | likely rule | status |
|---|---|---|---|---|
| ADV-0011 | `command-center/p2-wave/probes/CNF-0153/known-clean/package-lock.json` (+ sibling fixture dirs `known-vulnerable/`, `exploratory-lodash-4.17.21/`) | `FileNotFoundError` in probe1; no generator in probes/CNF-0153 or ADV-0011 | package-lock fixtures: > 5 MB `MaxFileBytes`, or a lock file under an excluded dir name | open |
| ADV-0016 | `.github/workflows/quality.yml` | `FAILED:ADV-0016-probe1 quality.yml absent`; the capture's `.github/` holds no `workflows/` | same as TST-0016: candidate source `/workspace/.github/workflows/quality.yml` (toolchain root; owner to confirm revision) | open |
| TST-0016 | `.github/workflows/quality.yml`, `.github/workflows/no-runtime-junk.yml` | `FAILED:TST-0016-probe1 target workflows missing from classification` (p42-TST) | the live `ast-integrate` tree is a toolchain checkout; the capture's `.github/` lacks `workflows/`. Candidate source: the toolchain root `/workspace/.github/workflows/` (owner to confirm same revision) | open |
| TST-0022 | `.agents/skills/claim-verify-gate/scripts/claim_gate.py`, `.../test_claim_gate.py` | `ModuleNotFoundError: No module named 'test_claim_gate'` (p42-TST) | `.agents/` of the live checkout not captured. Candidate source: toolchain root `/workspace/.agents/skills/claim-verify-gate/scripts/` | open |
| TST-0025 | `tools/router/shadow_catalog.json` | `emit_receipt` `pin_state` needs it; `load_catalog` only falls back (p42-TST). Also location-bound fingerprint (see OPEN-LOOPS) | > 5 MB `MaxFileBytes` or generated | open |
| IMP-0333 | `tools/council/tests/test_oxford.py` | probe2 `can't open file`; the receipt already equals the live numbers and the manifest row matches (w7) | test file never captured (no copy anywhere on the box) | open |

Candidates seen in census 04 (`probe-file-missing`, 12 units) still to be confirmed by a writer
(a generator may exist): ARC-0082 `blueprints/workflows/wf.research.archival.json`; AUD-0006
`probes/AUD-0006/control/tmp/scratch_cache/real_module.py` (`tmp` = ExtraExcludeDirs); AUD-0084
`probes/AUD-0084/fixtures/use_vs_mention_fixture.py`; BLD-0053
`probes/BLD-0053/fixtures/transitive-gap/package-lock.json`; IMP-0067
`.claude-plugin/marketplace.schema.json`; RES-0086 `probes/RES-0086/captures/LOCAL.json`; RES-0132
`probes/RES-0132/control-red/package-lock.json`; RES-0182
`probes/RES-0182/snapshots/plos-hemming-2018-idea.pdf` (PDF, likely > 5 MB); TST-0055
`command-center/blueprints/engineering/engine.py`; TST-0086 `agent-self/config/settings.json`;
WFA-0160 `probes/WFA-0042/_inspect_source_out.json` (another unit's run-time output → XDEP, not a gap).
