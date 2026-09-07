---
name: blue
description: Defensive operations package — full tier tables (FEW/MEDIUM/HEAVY/FULL/MAX/SOTA) for wiring detection, hardening, and guardrail enforcement with exact enable AND disable commands. Child of red-blue-purple.
---

# BLUE — defensive tier package

Cumulative tiers. Detection engineering + guardrail enforcement for the estate's own surfaces.

## Tier tables

### FEW — instant checks
| Capability | Components | Enable | Disable |
|---|---|---|---|
| Endpoint telemetry | sysmon (verify: `Get-Process Sysmon`) | already installed/running | owner-only (never disable) |
| Port census | loopback discipline scan `netstat -ano | grep LISTEN` vs expected map (314xx/313xx/55553/3001/18812/18765) | on demand | n/a |
| Hygiene | hosts file, scheduled-task census, `cyberstrike mcp list` drift check | on demand | n/a |

### MEDIUM — detection CLIs
| Capability | Components | Enable | Disable |
|---|---|---|---|
| Rule engines | sigma-cli, yara-x (`D:\opt\purple-tools\venv-detect\Scripts\`) | run from venv | n/a |
| Rule corpora | `purple-tools\sigma-rules\`, `yara-rules\` | cloned, on demand | n/a |
| Packet analysis | tshark captures → sigma pipeline | on demand | stop captures |
| Cloud CIS (single) | prowler (`venv-detect\Scripts\prowler.exe`) | per-account run | n/a |

### HEAVY — watchers + audits
| Capability | Components | Enable | Disable |
|---|---|---|---|
| Guardrail guard | `D:\opt\purple-tools`? no → lane: `D:\bolt\enum\pulls\cs-agent-integrity\mitigations\guardrail-guard.ps1` (hash-chain watcher + auto-restore; spec'd, task install owner-gated) | install per design-B (ProgramData ACL dir + SYSTEM task) | remove task; `ClearAlert` |
| Watch station | `D:\bolt\watch\watcher.py` (jfrog + targets) | start watcher | stop process |
| Cloud audits | cloud_audit tools (aws/azure/gcp iam/storage/network/logging/encryption), k8s_audit suite, ci_audit suite | `verify_readonly` first, then per-program | n/a |
| DFIR triage | velociraptor (`D:\opt\purple-tools\velociraptor.exe` offline collector) | generate collector config | n/a |

### FULL — detection-as-code
| Capability | Components | Enable | Disable |
|---|---|---|---|
| CI gates | repo audit workflows (mcp-audit, hook-audit, rule-audit, skill-dual-write, quality/charter) | active on PR/push | owner-only (charter-policed) |
| Secret defense | gitleaks full-history; secret scans before every commit | pre-commit habit + CI | n/a |
| Ingest scrubbing | sanitize at MCP-front/nuclei-wrapper boundary (design-A spec: `sanitize-spec.py` — zero-width/ANSI/tag/HTML-comment stripper; 100% covert removal measured) | wire into fronts (spec ready) | remove wrapper |

### MAX — enforcement + emulation
| Capability | Components | Enable | Disable |
|---|---|---|---|
| Dual-LLM gate | second-vendor reviewer on dangerous verbs (spec'd; 15s part-stream tap → full revert) | per design-B | stop tap task |
| Permission immutability | session.permission snapshots + drift alert (`guard_dbcheck.py`) | per design-B | stop task |
| Atomic tests | Invoke-AtomicRedTeam 2.3.0 (PS module) | `Invoke-AtomicTest -Technique T####` | n/a |
| Adversary emulation | Caldera compose `:8888` | `docker compose up -d` | `down` |
| Integrity fencing | provenance fences + taint tags at prompt-build (upstream + wrapper hybrid) | per design-A | remove fences |

### SOTA — measured defense
| Capability | Components | Enable | Disable |
|---|---|---|---|
| Scoring protocol | 27-cell factorial, N=40/cell, pre-registered hypotheses, Wilson CIs (`measurement\analyze.py`) | run protocol per defense change | n/a |
| Canary battery | 10 benign-but-forbidden tasks × 4 injection conditions (spec: `v5-baseline\canary-battery.md`) | fixtures + fresh agent session | dispose fixtures |
| Adaptive calibration | re-run battery vs crescendo/persona/hidden classes; Holm-corrected ME deltas | quarterly + after any defense change | n/a |
| SOTA-model immunity verification | fable-5/5.1, chatgpt-5.6/6 — verify "immune" claims via research lane (consolidated\sota-models\) | per research dispatch | n/a |

## Known ground truth (from the integrity lane — defend THESE)
- Tool outputs enter model context **unfenced**; `<system-reminder>` tags forgeable; permission map = only enforced boundary; loopback auth bypass on serve-mode; unsandboxed bash vs user-writable guardrail state.
- Effective stack today (measured): covert-channel scrubbing 100%, plain-directive 0% (guard's job), conceal-span ordering hazard S-3.

## Domain wiring
- **cyberstrike/tui**: guardrail-guard watches config+DB+skills; watch station; audits as MCP fronts (cloud-audit :31418)
- **claude**: audits via load_tools (cloud_audit, k8s_audit, ci_audit); guard scripts run estate-side
- **codex**: read-only audit CLIs via bash; registry only for targeted servers
- **cursor**: monitor bots read INBOX.md/runs/; cloud agents observable via conversation-search (`sessions --source cloud-cache`)
- **grok**: THE blue-domain resident — supervisor posture, RED-ladder nudges, digest cadence
