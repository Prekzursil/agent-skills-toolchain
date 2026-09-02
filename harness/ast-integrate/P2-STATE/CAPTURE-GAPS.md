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
| TST-0055 | `command-center/blueprints/engineering/engine.py` | `FileNotFoundError`; no copy on the box, absent from git (p44-TST) | not captured | open |
| TST-0068 | `hooks/_dispatch/manifest.json` | capture holds a 123-byte `not_the_deployed_copy` stub; the real 14063-byte manifest exists at the toolchain root `/workspace/hooks/_dispatch/manifest.json` (p44-TST) | live tree carried a stub copy; candidate source at the toolchain root (owner to confirm) | open |
| IMP-0067 | `.claude-plugin/marketplace.schema.json` | referenced by 3 tools, nothing writes it (b3-p13-IMP) | not captured (the capture's `.claude-plugin/` holds marketplace.json, plugin.json, plugin.schema.json only) | open |
| AUD-0045 | `.agents/skills/claim-verify-gate/scripts/claim_gate.py` | same family as TST-0022 (b3-p04-AUD) | `.agents/` never captured; candidate source at the toolchain root | open |
| AUD-0047 | `.github/workflows/*.yml` (12 gates listed in `fixtures/live_gates.json`; capture holds only `plugin-repro.yml`) | (b3-p04-AUD) | same family as ADV-0016/TST-0016; candidate source `/workspace/.github/workflows/` | open |
| AUD-0080 | `probes/AUD-0080/fixtures/merge/local.json` | manifest pins its sha; `.gitignore:203` ignores any `local.json` (b3-p04-AUD) | toolchain `.gitignore` rule, not a capture rule — owner: negate the rule for this fixture | open |
| AUD-0081 | `probes/AUD-0081/fixtures/untrusted-clone/` (3 md + a `.git` file marker) | nested-repo marker never captured (b3-p04-AUD) | embedded-repo exclusion | open |
| ADV-0143 | `tools/blueprints/product/customer_council/blueprint.json` | `taxonomy.py:313`; nothing generates it; never in git history (b3-p00-ADV) | not captured | open |
| TST-0301 | `command-center/bench/METRIC-INVENTORY.json`, `command-center/bench/B07-MARGIN-TABLE.json` | code path verified green in a throwaway root with synthetic inputs; the receipt freezes the table by content-address sha (30eb8f82…, 2505 B), so the inputs cannot be re-invented (b3-s00) | never captured; owner sources the two files | open |
| AUD-0006 | `probes/AUD-0006/control/tmp/scratch_cache/real_module.py` | root `.gitignore:215` `tmp/` (b3-p03-AUD-r) | toolchain ignore rule + ExtraExcludeDirs `tmp` | open |
| AUD-0016 | `probes/AUD-0016/fixtures/estate/project/.claude/settings.local.json` | never captured (b3-p03-AUD-r) | `.claude/` local settings ignored | open |
| AUD-0018 | `probes/AUD-0018/fixtures/trees/src/rules/nested-repo/{.git,secret.md}` | nested `.git` uncommittable; probe2 controls need it (b3-p03-AUD-r) | embedded-repo exclusion | open |
| AUD-0023 | `probes/AUD-0023/fixtures/known-advisory/package-lock.json` | root `.gitignore:2`; write_receipts SUPPORTING row; artifact regen works, receipts cannot be rewritten (b3-p03-AUD-r) | toolchain ignore rule | open |
| BLD-0002, BLD-0041 | `probes/BLD-0002/fixtures/scratch/`, `probes/BLD-0041/fixtures/scratch/` (4 fixture files) | nothing generates them (b3-p06-BLD) | `scratch` = ExtraExcludeDirs — these fixtures were real inputs under an excluded name | open |
| IMP-0157 | `tools/workflow_foundry/candidate_registry.json` (manifest row sha d21f100f…, 2194 B) | never in git; unit is green on its original receipt — do NOT regenerate it (b4-p07-IMP) | not captured | open (non-blocking) |

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
