# Branch retirement: the 17 non-July unmerged branches — DRAFT (measurement checkpoint)

Filed 2026-09-02. Work-in-progress checkpoint: measurement complete, tags and narrative pending.
Measured against `origin/main` at `72120810` (2026-09-02 04:20:48 +0300) with the six signals of
`reconcile-flags/branch-retirement-2026-09-02.md` §2.

## CLASSIFICATION TABLES

### partially contained — 5

| branch | tip | tip date | ahead | class | cherry | cp-RO | patch-id | squash | merge-recon | tree | PR | archive tag |
|---|---|---|---:|---|---|---:|---|---|---|---|---|---|
| `docs/cursor-cli-bridges` | `fbc70f22` | 2026-08-27 | 15 | **partial** | −0/+14 | 14 | 0/14 | no | 68/70 | 68/70 | #290&nbsp;Closed | `archive/2026-09/docs/cursor-cli-bridges` |
| `fix/deny-credential-gaps` | `d3def686` | 2026-08-26 | 2 | **partial** | −1/+1 | 1 | 1/2 | no | 1/9 | 0/9 | #260&nbsp;Merged | `archive/2026-09/fix/deny-credential-gaps` |
| `import/agents-fullstate-2026-08-28` | `c3cde97b` | 2026-08-28 | 1 | **partial** | −0/+1 | 1 | 0/1 | no | none | 2655/2665 | — | `archive/2026-09/import/agents-fullstate-2026-08-28` |
| `wip/harness-additions-2026-08-28` | `fb075a2b` | 2026-08-28 | 8 | **partial** | −1/+7 | 7 | 1/8 | no | none | 3374/3432 | — | `archive/2026-09/wip/harness-additions-2026-08-28` |
| `wip/harness-workspace-supervisor-20260826` | `b0b29812` | 2026-08-26 | 2 | **partial** | −0/+2 | 2 | 0/2 | no | 17/44 | 17/44 | — | `archive/2026-09/wip/harness-workspace-supervisor-20260826` |

### unique — 0

| branch | tip | tip date | ahead | class | cherry | cp-RO | patch-id | squash | merge-recon | tree | PR | archive tag |
|---|---|---|---:|---|---|---:|---|---|---|---|---|---|

### contained — 12

| branch | tip | tip date | ahead | class | cherry | cp-RO | patch-id | squash | merge-recon | tree | PR | archive tag |
|---|---|---|---:|---|---|---:|---|---|---|---|---|---|
| `chore/deps-consolidated-20260809` | `4be75bbb` | 2026-08-09 | 4 | contained | −0/+4 | 4 | 0/4 | yes | `89d20e64` | 10/10 | #274&nbsp;Merged | `archive/2026-09/chore/deps-consolidated-20260809` |
| `chore/harness-reconcile-20260808` | `05e43364` | 2026-08-09 | 19 | contained | −0/+19 | 19 | 0/19 | no | `696ed513` | 177/177 | #275&nbsp;Merged | `archive/2026-09/chore/harness-reconcile-20260808` |
| `chore/hygiene-academic-skills-20260825` | `6a47fb5d` | 2026-08-25 | 1 | contained | −0/+1 | 1 | 0/1 | no | 17/17 | 17/17 | #291&nbsp;Closed | `archive/2026-09/chore/hygiene-academic-skills-20260825` |
| `ci/execute-never-run-dualwrite-steps` | `f90b3e02` | 2026-08-13 | 2 | contained | −1/+0 | 0 | 1/1 | yes | 2/2 | 2/2 | #281&nbsp;Closed | `archive/2026-09/ci/execute-never-run-dualwrite-steps` |
| `lane-cigreen/dual-write-gates` | `28d42732` | 2026-08-13 | 1 | contained | −0/+1 | 1 | 0/1 | no | 2/2 | 2/2 | #282&nbsp;Closed | `archive/2026-09/lane-cigreen/dual-write-gates` |
| `lane-cigreen/sast-install-split` | `963315e3` | 2026-08-14 | 3 | contained | −2/+0 | 0 | 2/2 | yes | `5a3e3a04` | 1/2 | #283&nbsp;Closed | `archive/2026-09/lane-cigreen/sast-install-split` |
| `test/deny-credential-denylist-coverage` | `90b7b39c` | 2026-08-01 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `c8e7085e` | 2/2 | #261&nbsp;Merged | `archive/2026-09/test/deny-credential-denylist-coverage` |
| `wave3/ci-trigger` | `97ea5eab` | 2026-08-09 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `44238e84` | 0/1 | #276&nbsp;Merged | `archive/2026-09/wave3/ci-trigger` |
| `wave3/command-center` | `589d5422` | 2026-08-09 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `53c37c6c` | 30/31 | #280&nbsp;Merged | `archive/2026-09/wave3/command-center` |
| `wave3/monitor` | `a8e8c2d0` | 2026-08-09 | 3 | contained | −0/+3 | 3 | 0/3 | yes | `fbedcdf6` | 9/9 | #279&nbsp;Merged | `archive/2026-09/wave3/monitor` |
| `wave3/program-b` | `e3245cea` | 2026-08-09 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `25015ba9` | 4/5 | #278&nbsp;Merged | `archive/2026-09/wave3/program-b` |
| `wave3/skill-gate` | `147a2813` | 2026-08-09 | 1 | contained | −1/+0 | 0 | 1/1 | yes | `f15cddbf` | 2/2 | #277&nbsp;Merged | `archive/2026-09/wave3/skill-gate` |

## RESIDUE TABLE

| branch | residue paths | absent | re-derived | relocated | edited-on-main | no-added-lines | line survival |
|---|---:|---:|---:|---:|---:|---:|---:|
| `docs/cursor-cli-bridges` | 2 | 0 | 0 | 1 | 1 | 0 | 50% |
| `fix/deny-credential-gaps` | 9 | 8 | 0 | 0 | 1 | 0 | 2% |
| `import/agents-fullstate-2026-08-28` | 10 | 8 | 0 | 2 | 0 | 0 | 55% |
| `lane-cigreen/sast-install-split` | 1 | 0 | 0 | 0 | 1 | 0 | 100% |
| `wave3/ci-trigger` | 1 | 0 | 0 | 0 | 1 | 0 | 100% |
| `wave3/command-center` | 1 | 0 | 0 | 0 | 1 | 0 | 100% |
| `wave3/program-b` | 1 | 0 | 0 | 0 | 1 | 0 | 100% |
| `wip/harness-additions-2026-08-28` | 58 | 12 | 0 | 5 | 18 | 23 | 60% |
| `wip/harness-workspace-supervisor-20260826` | 27 | 10 | 0 | 0 | 16 | 1 | 9% |

## DETAIL BLOCKS

#### `docs/cursor-cli-bridges` — partially contained

- tip `fbc70f22` (2026-08-27), 15 commits ahead, 70 behind; merge-base `81f844d3`
- tree: 68/70 changed paths landed byte-identically, **2 residue paths**
- residue lines: 8 added lines are not blob-identical on main; **4 (50%) present verbatim at main tip** — 1 at the same path, 3 at a relocated path
- residue state: 1 relocated, 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `.agents/skills/bc-drive-plus/snapshot_ring.py` | `reconcile-flags/import-2026-08-28/skills/bc-drive-plus/snapshot_ring.py` | 3/3 |

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.gitignore` | 5 | 1 |

#### `fix/deny-credential-gaps` — partially contained

- tip `d3def686` (2026-08-26), 2 commits ahead, 542 behind; merge-base `f5eb12c1`
- tree: 0/9 changed paths landed byte-identically, **9 residue paths**
- residue lines: 810 added lines are not blob-identical on main; **18 (2%) present verbatim at main tip** — 18 at the same path, 0 at a relocated path
- residue state: 8 absent, 1 edited-on-main
- **absent from main in any form: 8 paths / 792 added lines**

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `e2e/openai_key_probe2.py` | 134 | **absent** | none |
| `e2e/openai_key_probe.py` | 129 | **absent** | none |
| `e2e/credential_blast_radius.py` | 113 | **absent** | none |
| `e2e/openai_usage_probe.py` | 107 | **absent** | none |
| `e2e/openai_usage_legacy.py` | 89 | **absent** | none |
| `e2e/transcript_leak_check.py` | 86 | **absent** | none |
| `e2e/openai_key_probe3.py` | 80 | **absent** | none |
| `e2e/transcript_leak_context.py` | 54 | **absent** | none |

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `hooks/deny-credential-reads/deny.py` | 18 | 18 |

#### `import/agents-fullstate-2026-08-28` — partially contained

- tip `c3cde97b` (2026-08-28), 1 commit ahead, 983 behind; merge-base **none — unrelated history**
- tree: 2655/2665 changed paths landed byte-identically, **10 residue paths**
- residue lines: 3416 added lines are not blob-identical on main; **1887 (55%) present verbatim at main tip** — 0 at the same path, 1887 at a relocated path
- residue state: 8 absent, 2 relocated
- **absent from main in any form: 8 paths / 1274 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `harness/tests/test_modules.py` | `.agents/harness/tests/test_modules.py` | 1415/1440 |
| `meta-tool/package-lock.json` | `tools/mcp/hacktricks-mcp-server/package-lock.json` | 472/702 |

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `harness/dispatcher.py.orig` | 412 | **absent** | none |
| `skills-index.md.bak` | 368 | **absent** | none |
| `agents.json.bak-frida-codex-20260427-001533` | 295 | **absent** | none |
| `scripts/sync_shared_state.ps1.bak-20260820-142444` | 86 | **absent** | none |
| `tests/test_secret_audit.py` | 47 | **absent** | none |
| `scripts/sync_shared_state.ps1.bak-20260401-212229` | 33 | **absent** | none |
| `skills/institutional-literature-access/SKILL.md.bak-2026-08-20` | 27 | **absent** | none |
| `skills/run-taskwatch_monitor/fixtures/demo.log` | 6 | **absent** | none |

#### `wip/harness-additions-2026-08-28` — partially contained

- tip `fb075a2b` (2026-08-28), 8 commits ahead, 983 behind; merge-base **none — unrelated history**
- tree: 3374/3432 changed paths landed byte-identically, **58 residue paths**
- residue lines: 3994 added lines are not blob-identical on main; **2383 (60%) present verbatim at main tip** — 21 at the same path, 2362 at a relocated path
- residue state: 23 no-added-lines, 18 edited-on-main, 12 absent, 5 relocated
- **absent from main in any form: 12 paths / 1280 added lines**

Relocated (≥50% of the branch's added lines found at a different path on main):

| branch path | → main path | lines |
|---|---|---:|
| `harness/tests/test_modules.py` | `.agents/harness/tests/test_modules.py` | 1415/1440 |
| `meta-tool/package-lock.json` | `tools/mcp/hacktricks-mcp-server/package-lock.json` | 472/702 |
| `tests/test_mcp_control_plane.py` | `.agents/tests/test_mcp_control_plane.py` | 288/307 |
| `scripts/audit_secret_artifacts.py` | `.agents/scripts/audit_secret_artifacts.py` | 152/159 |
| `scripts/validate_mcp_control_plane.py` | `.agents/scripts/validate_mcp_control_plane.py` | 35/41 |

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `harness/dispatcher.py.orig` | 412 | **absent** | none |
| `skills-index.md.bak` | 368 | **absent** | none |
| `agents.json.bak-frida-codex-20260427-001533` | 295 | **absent** | none |
| `scripts/sync_shared_state.ps1.bak-20260820-142444` | 86 | **absent** | none |
| `tests/test_secret_audit.py` | 47 | **absent** | none |
| `scripts/sync_shared_state.ps1.bak-20260401-212229` | 33 | **absent** | none |
| `skills/institutional-literature-access/SKILL.md.bak-2026-08-20` | 27 | **absent** | none |
| `skills/run-taskwatch_monitor/fixtures/demo.log` | 6 | **absent** | none |
| `browser-profiles/chrome-agent/TrustTokenKeyCommitments/2026.8.3.1/manifest.json` | 3 | **absent** | none |
| `browser-profiles/chrome-agent/Default/Network/TransportSecurity` | 1 | **absent** | none |
| `browser-profiles/chrome-agent/TrustTokenKeyCommitments/2026.8.3.1/_metadata/verified_contents.json` | 1 | **absent** | none |
| `browser-profiles/chrome-agent/TrustTokenKeyCommitments/2026.8.3.1/keys.json` | 1 | **absent** | none |

The other 18 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `browser-profiles/.gitignore` | 24 | 21 |
| `browser-profiles/chrome-agent/Default/Extension Rules/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Extension Scripts/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Extension State/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/GCM Store/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Local Extension Settings/bdccimcedobipcmhcikcnakjdemiechj/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Local Storage/leveldb/LOG` | 3 | 0 |
| `browser-profiles/chrome-agent/Default/Service Worker/Database/LOG` | 3 | 0 |

23 residue paths with no added lines (pure deletion or binary): `browser-profiles/chrome-agent/Default/DIPS`, `browser-profiles/chrome-agent/Default/DawnGraphiteCache/data_1`, `browser-profiles/chrome-agent/Default/DawnWebGPUCache/data_1`, `browser-profiles/chrome-agent/Default/Extension Rules/000003.log`, `browser-profiles/chrome-agent/Default/Extension Scripts/000003.log`, `browser-profiles/chrome-agent/Default/Extension State/000003.log` …

#### `wip/harness-workspace-supervisor-20260826` — partially contained

- tip `b0b29812` (2026-08-26), 2 commits ahead, 529 behind; merge-base `53c37c6c`
- tree: 17/44 changed paths landed byte-identically, **27 residue paths**
- residue lines: 8180 added lines are not blob-identical on main; **766 (9%) present verbatim at main tip** — 766 at the same path, 0 at a relocated path
- residue state: 16 edited-on-main, 10 absent, 1 no-added-lines
- **absent from main in any form: 10 paths / 6435 added lines**

Absent or re-derived — this is what retiring the branch takes out of the active estate:

| residue path | + lines | state | counterpart on main |
|---|---:|---|---|
| `agent-self/harness/workspace_index.py` | 1576 | **absent** | none |
| `agent-self/harness/tests/test_workspace_index.py` | 977 | **absent** | none |
| `agent-self/harness/workspace_mutation.py` | 854 | **absent** | none |
| `agent-self/harness/workspace_integrity.py` | 720 | **absent** | none |
| `agent-self/harness/hook_supervisor.py` | 691 | **absent** | none |
| `agent-self/harness/tests/test_workspace_mutation.py` | 460 | **absent** | none |
| `agent-self/harness/tests/test_hook_supervisor.py` | 453 | **absent** | none |
| `agent-self/harness/tests/test_workspace_integrity.py` | 448 | **absent** | none |
| `agent-self/harness/tests/test_dispatcher_supervised.py` | 224 | **absent** | none |
| `tools/mcp/cloud-hub/shadow/confirm-gate.jsonl` | 32 | **absent** | none |

The other 16 residue paths exist on main and were edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `agent-self/harness/dispatcher.py` | 445 | 117 |
| `agent-self/harness/ledger.py` | 323 | 179 |
| `agent-self/harness/tests/test_dispatcher_and_registration.py` | 183 | 56 |
| `agent-self/harness/tests/test_dispatcher_mixer_breaker.py` | 133 | 16 |
| `agent-self/harness/tests/test_ledger_receipts_and_taint.py` | 132 | 76 |
| `agent-self/harness/tests/test_cov_ledger.py` | 54 | 11 |
| `agent-self/harness/tests/test_modules.py` | 53 | 16 |
| `agent-self/harness/modules.py` | 165 | 137 |

1 residue path with no added lines (pure deletion or binary): `agent-self/config/settings.json`

#### `lane-cigreen/sast-install-split` — contained

- tip `963315e3` (2026-08-14), 3 commits ahead, 214 behind; merge-base `2ef977cd`
- tree: 1/2 changed paths landed byte-identically, **1 residue path**
- residue lines: 24 added lines are not blob-identical on main; **24 (100%) present verbatim at main tip** — 24 at the same path, 0 at a relocated path
- residue state: 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.github/workflows/quality.yml` | 24 | 24 |

#### `wave3/ci-trigger` — contained

- tip `97ea5eab` (2026-08-09), 1 commit ahead, 535 behind; merge-base `696ed513`
- tree: 0/1 changed paths landed byte-identically, **1 residue path**
- residue lines: 29 added lines are not blob-identical on main; **29 (100%) present verbatim at main tip** — 29 at the same path, 0 at a relocated path
- residue state: 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.github/workflows/quality.yml` | 29 | 29 |

#### `wave3/command-center` — contained

- tip `589d5422` (2026-08-09), 3 commits ahead, 535 behind; merge-base `696ed513`
- tree: 30/31 changed paths landed byte-identically, **1 residue path**
- residue lines: 22 added lines are not blob-identical on main; **22 (100%) present verbatim at main tip** — 22 at the same path, 0 at a relocated path
- residue state: 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.github/workflows/quality.yml` | 22 | 22 |

#### `wave3/program-b` — contained

- tip `e3245cea` (2026-08-09), 1 commit ahead, 535 behind; merge-base `696ed513`
- tree: 4/5 changed paths landed byte-identically, **1 residue path**
- residue lines: 22 added lines are not blob-identical on main; **22 (100%) present verbatim at main tip** — 22 at the same path, 0 at a relocated path
- residue state: 1 edited-on-main
- **absent from main in any form: 0 paths / 0 added lines**

The other 1 residue path exists on main and was edited further after this branch's content landed. Largest line gaps:

| path | + lines | still at main tip |
|---|---:|---:|
| `.github/workflows/quality.yml` | 22 | 22 |

