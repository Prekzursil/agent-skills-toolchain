---
title: codex-checkpoint-01a06324-18f6-7922-bfa4-90b27770281a-cyberstrike-windows-plan-2026-09-02
type: note
permalink: main/codex-checkpoints/codex-checkpoint-01a06324-18f6-7922-bfa4-90b27770281a-cyberstrike-windows-plan-2026-09-02
status: active
valid_as_of: 2026-09-02
tags:
- codex-checkpoint
- cyberstrike
- planning
---

# CyberStrike Windows-native plan checkpoint

- [requirement] Active goal from user: install/configure CyberStrike and add Metasploit at maximum permitted capability for future sessions; user also demanded Sliver but HOME hard-bans C2, so Sliver remains excluded.
- [requirement] Latest user refinement: do everything on Windows, no VM or direct WSL. User explicitly allows existing Docker Desktop WSL2 backend only for Bolt.
- [decision] CyberStrike install channel: exact npm package @cyberstrike-io/cyberstrike@1.1.16.
- [decision] Run on current Windows host and current Windows user account, not a dedicated account.
- [decision] Native Rapid7 Metasploit Framework Windows MSI; pin archived build 6.5.3-20260826060514. Use official msfmcpd through embedded Ruby if present/working; otherwise explicit private typed adapter over msfrpcd.bat, differential-parity tested to the official 16 tools. Never register raw msfmcpd or persist dangerous mode.
- [decision] Bolt runs only through Docker Desktop WSL2 exception, digest-pinned ghcr.io/cyberstrikeus/bolt:93bcf2c@sha256:90ef2d10a8e255369981e7ce2eb7b89e1ac337ad6a5cf9f21f803c8585eea277, loopback-only.
- [decision] All permitted tools installed/discoverable; no future session inherits authorization. Active, post-exploitation, Metasploit dangerous, Bolt, credential, or mutable actions require a current signed engagement and fresh confirmation. Permanent C2 denies precede signed allows.
- [fact] Live cyberstrike resolves C:\Users\Prekzursil\AppData\Roaming\npm\cyberstrike.ps1 and is 1.1.15. npm publishes 1.1.16 AGPL-3.0-only with integrity sha512-Yf4fb54n6Apw7qZZFNG32Ok6aMBcfIW+OzvUHovsW/ImP/ETRHdX90ZjFT24/UFgmdYqNy+x9T0dF6yI451FQA== and a postinstall.
- [fact] Live auth list has zero CyberStrike credentials; process env lacks provider keys, but .agents/local.json contains an OPENROUTER_API_KEY binding name. Reuse binding without exposing/copying value.
- [fact] Live .agents/agents.json lacks cloud-audit, github-security, cve-mcp, and osint; repo canonical manifest contains them. integrations.enabled remains empty/source-only.
- [fact] Private gateway tools/mcp/cyberstrike-harness-bridge is absent. Existing skill/docs pin 1.1.15 and include stale key-rotation/C2 language needing correction.
- [fact] Repo branch handoff/cloud-agent-2026-09-02 is dirty with unrelated changes. Do not stash/reset/overwrite; implementation needs owner/interactive clean worktree.
- [fact] Docker Desktop 4.88.1 / Engine 29.7.2 runs linux/amd64 via WSL2. Bolt image digest and amd64 digest sha256:b5ddb610ea214656fd97223ed790d3bb50a3d44ae188dc937e64c87a83cc4459 verified live. No Bolt image/container currently present.
- [fact] Metasploit absent from Windows and Ubuntu WSL. Rapid7 Windows wrappers include msfrpcd.bat but omit msfmcpd.bat; embedded Ruby direct launch is plausible but must be proven after MSI inventory.
- [fact] Current free RAM was 1.33 GB/31.63 GB; execution/heavy tests must wait for at least 8 GB free. AC4BFSP was absent.
- [fact] Bun 1.3.11 and cloud-audit source path exist; old skill expected 1.3.9. Test 1.3.11 first, use side-by-side 1.3.9 only if incompatible.
- [decision] Keep Defender and Windows Firewall enabled. No broad exclusions, autostart, service registration, raw HTTP MCP, generic RPC/console proxy, secrets in argv/logs, or credential rotation.
- [decision] Metasploit official MCP exposes 16 tools, four dangerous. Signed wrapper owns private stdio child, loopback RPC with env/file credentials, engagement-derived workspaces, owned job/session IDs, kill-on-expiry process tree. C2-equivalent paths (multi/handler, payload/stager/handler, Meterpreter/reverse-shell creation, persistent listeners, session command channels) always deny.
- [decision] Bolt requires verified per-container target egress enforcement or stays disconnected; no privileged mode, Docker socket, host network, wildcard bind, or broad mount.
- [decision] Native Windows cannot make linuxhook/ebpf/machook operational; keep them visible and explicitly unsupported. Bolt provides Linux tool catalog only via allowed Docker backend.
- [fact] Security reviewer completed and endorsed design after corrections; required tests: 16 Metasploit tools; 38/39/41/37 companions; negative signed-grant matrix; mutation checks; one approved non-C2 dangerous local-lab action; C2 always deny; raw bypass unreachable; process tree dies at expiry; fallback parity; Bolt ingress/egress/digest/key controls; future session inherits no grant.
- [next] Produce decision-complete <proposed_plan> only; no mutations in Plan Mode. Include summary, architecture/interfaces, implementation sequence, tests/acceptance, assumptions/boundaries. Mention exact Windows MSI pin, npm pin, Bolt digest, current-user containment compensations, dirty-worktree and RAM gates, Sliver exclusion, OpenRouter env binding reuse, never-rotate.
- [context] Current window id 01a06324-18f6-7922-bfa4-90b27770281a; previous 01a0630b-3510-7230-9d1d-a271ac92c2cc. User item IDs were not exposed in the visible transcript; relevant user turns are the initial AGENTS/home-contract injection, active-goal follow-up requesting Sliver+Metasploit maximum power, and latest refinement "see if youc an do all windows not vm or wsl".
- relates_to [[CyberStrike]]
- relates_to [[agent-skills-toolchain]]


## Resume checkpoint - window 01a0634e-ce60-7b43-9797-9db4f45e0a6a - 02.09.2026 21:25 Europe/Bucharest

- [requirement] Authoritative active goal remains: Implement the approved Windows-native CyberStrike 1.1.16 + native Metasploit + guarded gateway + Bolt-only-Docker plan. Latest user message injected HOME AGENTS contract; its item id is unavailable in the visible transcript.
- [decision] Use exact npm CyberStrike 1.1.16, exact Rapid7 MSI 6.5.3-20260826060514, Bolt OCI index sha256:90ef2d10a8e255369981e7ce2eb7b89e1ac337ad6a5cf9f21f803c8585eea277 and linux/amd64 manifest sha256:b5ddb610ea214656fd97223ed790d3bb50a3d44ae188dc937e64c87a83cc4459.
- [decision] Permanent exclusions: no Sliver/C2, payload handlers/listeners, reverse shells, Meterpreter command channels, persistence, credential harvesting, or session-write. Never rotate credentials. Only one runtime MCP registration, cyberstrike-gateway, exposing exactly three tools.
- [decision] Current dirty branch handoff/cloud-agent-2026-09-02 may be edited only on target paths verified clean; no git writes, stash, reset, branch, commit, or push. Existing dirty modules.py/test_modules.py/test_native_events.py and unrelated files are untouched.
- [fact] Fully re-read HOME AGENTS.md, .codex/AGENTS-RUNTIME.md, memory-contract, shared cyberstrike SKILL.md, capabilities.md, plugin-bridge.md, executing-plans, and using-git-worktrees. The current branch is non-main; no clean matching worktree exists, so user-approved path-level reconciliation is used.
- [fact] Live gate: Administrator true; RAM 1.83 GB/31.63 GB; AC4BFSP absent; Node v24.16.0, npm 11.17.0, Bun 1.3.11; CyberStrike 1.1.15; Metasploit absent; Docker running. Defer heavy tests, Docker pull, database setup, and parallel worker waves until 8 GB free. Do not kill user processes.
- [fact] CyberStrike npm meta and platform tarballs were packed with scripts disabled and SRI recomputed. Meta SRI sha512-Yf4fb54n6Apw7qZZFNG32Ok6aMBcfIW+OzvUHovsW/ImP/ETRHdX90ZjFT24/UFgmdYqNy+x9T0dF6yI451FQA==. Windows SRI sha512-XbmvwTCtncxnRUh+Xhju8NINE9ZjXnMTBu+JwMGPfNxxD0WIp6ozqQOqj8bATEFVnpWuHCb62LXGcHcf2Ce02g==; exe SHA256 8AA4531E3075949E159AFEA9BBB5FB7B9A918F4B81100FD5BC3CD9E6626023A2; unsigned; Defender no-remediation scan clean. Postinstall contains NODE_TLS_REJECT_UNAUTHORIZED=0 for Playwright, so install must use --ignore-scripts and manual safe deployment.
- [fact] Rapid7 immutable MSI downloaded to C:\Users\Prekzursil\.cache\cyberstrike-adoption\metasploit\6.5.3-20260826060514. Size 399974400; SHA256 2556D431EF76FD85D39D0C914B604ADCF9D7050A61393B770C4319547501D8C7. Authenticode NotSigned. Detached PGP verified exit 0 using Rapid7 Release Engineering key fingerprint 97B32012EA1176F053727A95C048F0B49DEEC457 extracted from pinned metasploit-omnibus commit 21d459344aa291e9d8c0abdd6cbd9806fdb84791.
- [fact] Offline MSI payload inspection proves bin/msfconsole.bat, bin/msfrpcd.bat, embedded/bin/ruby.exe, embedded/framework/msfmcpd, MCP configs/specs. No bin/msfmcpd.bat. ProductVersion 6.5.3.1. Managed launch should be embedded Ruby plus official msfmcpd script, absolute argv/CWD, stdio, stable create-once RPC credentials.
- [fact] Disk receipt created and re-read: source/agent-skills-toolchain/docs/cyberstrike-adoption/artifact-provenance_2026-09-02.md, 5980 bytes, SHA256 EBC2EB0742EA83D2198C4BDFD12E9972A77CE5123B9BEA958713569F505F9FA5, sentinel present.
- [fact] Defender baseline before modifications: AntivirusEnabled true, RealTimeProtectionEnabled false, DisableRealtimeMonitoring true, signature 1.457.447.0, one existing exclusion path and process; do not reveal paths or change config. A no-remediation scan of the 400 MB MSI is still running in unified exec session 97117; monitor with write_stdin, do not rerun. Earlier liveness showed MsMpEng CPU delta 3.03s/3s.
- [progress] Plan: (1) reconciliation completed; (2) artifact verification in progress pending MSI scan completion; (3) implementation pending/in progress via agents; (4) mandatory code/security reviews; (5) shared sync; (6) install/smoke; (7) final receipts/memory.
- [progress] Agent gateway_impl (tdd-guide) is implementing new tools/mcp/cyberstrike-harness-bridge and root workspace changes. Agent harness_provider_impl is editing only adapters.py/dispatcher.py/schema/new focused test. Agent cyberstrike_docs_impl is updating repo .agents/skills/cyberstrike and skills/cyberstrike byte-identically. Follow-up cyberstrike_architecture is implementing external AGPL plugin under AppData/Local/CyberStrike/agent-skills-toolchain-bridge. Wait for results; verify disk rather than agent claims.
- [fact] gateway pattern recommendation: TypeScript ESM Node >=22, exact MCP SDK pin, three tools, HMAC loopback hub, strict backends, canonical manifest hash, idempotency/redacted audit, no raw registration; real Windows Job Object absent in repo, so fail closed with visible unavailable reason if not proven.
- [next] First poll exec session 97117. Then collect/verify agent file changes and run targeted tests. Invoke mandatory TypeScript/Python/code/security reviewers and fix findings. Update source canonical MCP manifest and live .agents/agents.json only after gateway build passes, keeping raw cloud-audit/github-security/cve-mcp/osint/metasploit absent. Run sync_shared_state.ps1 only after backup and parse validation.
- [next] Install CyberStrike with lifecycle scripts disabled and backup-first manual web/skill/worker deployment; preserve config/auth/db/state. Install Metasploit only after scan and RAM gate allow, with no Defender/Firewall change. Bolt remains unpulled/disconnected until digest, config, create-once secret, loopback and per-container egress are proven.
- relates_to [[CyberStrike]]
- relates_to [[agent-skills-toolchain]]


## External plugin checkpoint - window 01a06360-7693-7c51-b287-6801d905b7a2 - 02.09.2026

- [requirement] Parent/root resumed this agent to implement only the external AGPL CyberStrike plugin at C:\Users\Prekzursil\AppData\Local\CyberStrike\agent-skills-toolchain-bridge. Latest incident constraint: do not launch live CyberStrike or any MCP/backend; static and mock unit tests only. The final sterile launcher must set CYBERSTRIKE_CONFIG_DIR to the reviewed external root, disable project/default/external config sources, expose exactly three bridge tools, and permanently deny C2 before signed allows. Relevant user item ids are unavailable in this compacted agent transcript.
- [fact] Re-read HOME AGENTS.md, Codex runtime contract, memory contract, CyberStrike SKILL.md and plugin-bridge.md, plus executing-plans. Inspected pinned npm @cyberstrike-io/plugin@1.1.16 and SDK types with npm pack --ignore-scripts only. No CyberStrike/MCP/backend process was launched by this agent.
- [fact] Created and disk-re-read external files: package.json, tsconfig.json, cyberstrike.jsonc, NOTICE.md, .gitignore, lib/constants.ts, config-policy.ts, redaction.ts, runtime-state.ts, protocol.ts, bridge-client.ts and five mock/unit test files. Target was absent before creation. Bun 1.3.11 mock-only suite passes 20/20.
- [decision] Package is private-to-prevent-publish but AGPL-3.0-only; exact dependency @cyberstrike-io/plugin 1.1.16. Config hardens top level and each agent, permanently denies nine direct-spawn tools, converts harness_invoke allow to ask, rejects any skill allow, and preserves deny.
- [decision] HMAC client accepts only http://127.0.0.1:<port>/ and canonical 32-byte standard-base64 key from env; signs method/path/time/32-byte nonce/body hash; rejects oversized or non-JSON responses. No secret values are written.
- [fact] Gateway agent locked foundation: implemented GET /health, GET /v1/capabilities, POST /v1/invoke. GET /v1/scope, POST /v1/skills/authorize, and exact 17 POST hook routes authenticate but return 503 gateway_capability_unimplemented; unknown paths 404. Plugin must deny scope/skill/high-risk on 503 and may fail open only bounded observations.
- [fact] Parent reported a separate live incident: existing default config had launched enabled Sliver; processes stopped, entries disabled, Sliver directory moved recoverably to protected quarantine. This agent stated chain-of-custody: it ran only npm metadata/pack and Bun unit mocks, never CyberStrike or MCP/backend.
- [next] Implement sterile PowerShell launcher using isolated XDG_CONFIG/DATA/CACHE/STATE under external root to prevent legacy global config/plugin loading; reject inherited CYBERSTRIKE_CONFIG, CONFIG_DIR, CONFIG_CONTENT, TEST_HOME, and likely permission override; require preexisting URL/HMAC env without generating/rotating; never execute launcher in this task.
- [next] Finish plugin/harness-bridge.ts, hook policy, independent empty skill-lock verifier, permanent C2 classifier, exactly three tools, mock tests and typecheck. Install dependencies with scripts disabled only if needed; do not start CyberStrike. Then mandatory TypeScript/code/security review when slots/RAM permit, fix findings, create >=1KB disk receipt ending UNIT-COMPLETE, re-read/hash artifact, and report to root.
- relates_to [[CyberStrike]]
- relates_to [[agent-skills-toolchain]]


## External plugin progress - window 01a06375-b872-7c80-a561-9549ac8e780d - 02.09.2026 22:10 Europe/Bucharest

- [requirement] Active subtask remains external AGPL plugin only at C:\Users\Prekzursil\AppData\Local\CyberStrike\agent-skills-toolchain-bridge; no live CyberStrike, gateway, MCP, or backend launch. Relevant user item id unavailable in this subagent transcript.
- [fact] Re-read HOME AGENTS, Codex runtime, memory contract, canonical CyberStrike SKILL plus capabilities/plugin-bridge references, and TDD skill. TDD's referenced testing-anti-patterns.md is missing; used dependency injection and real filesystem behavior as fallback.
- [fact] Installed exact external package dependencies with npm install --ignore-scripts --no-audit --no-fund --package-lock=false. This added node_modules only; no lifecycle scripts and no lockfile.
- [decision] Gateway agent confirmed POST /v1/invoke requires exact signed envelope {protocol,requestId,timestamp,correlationId,origin,hopCount,input}; response echoes envelope plus result. Scope/skills/all 17 hooks remain authenticated 503 gateway_capability_unimplemented.
- [bug] Real gateway manifest serializes to 83,351 bytes, exceeding old shared 65,536 response cap. Gateway agent is raising response-only cap to 262,144 while keeping requests 65,536; external plugin aligned. This preserves all visible capabilities without widening inputs.
- [progress] TDD RED observed: old client rejected >65KiB manifest and sent raw POST bodies; invoke envelope tests failed. Implemented MAX_REQUEST_BYTES=65536, MAX_RESPONSE_BYTES=262144, signed POST envelopes, response correlation validation, and canonical manifest revision verification.
- [fact] Focused static/mock suite now passes 11/11: bridge-client + protocol. No process except Bun test and ephemeral test loopback HTTP servers; no production gateway/backend launch.
- [decision] Official CyberStrike source inspection confirmed config precedence: managed ProgramData config is highest, home .cyberstrike is always scanned, CYBERSTRIKE_PERMISSION can override permissions, config-dir plugins auto-discover one level, and plugin hooks run serially. Sterile launcher must reject managed/home auto-load sources and inherited CONFIG/CONFIG_DIR/CONFIG_CONTENT/TEST_HOME/PERMISSION before setting isolated XDG dirs.
- [next] Continue TDD: add skill-trust verifier tests/module (official raw Ed25519 key, classifications, strict empty lock, tree hash/TOCTOU), permanent C2 policy tests/module, plugin exact three-tool/hook tests and implementation, then sterile PowerShell launcher + artifact-lock + static tests.
- [next] Run full typecheck/mock tests, mandatory TypeScript/code/security reviewers, fix findings, create >=1KB disk receipt with UNIT-COMPLETE sentinel, hash/re-read, report root. Never launch live CyberStrike/backend in this subtask.
- relates_to [[CyberStrike]]
- relates_to [[agent-skills-toolchain]]