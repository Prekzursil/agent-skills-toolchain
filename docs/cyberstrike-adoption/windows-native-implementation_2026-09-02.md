# CyberStrike Windows-native implementation contract

**Date:** 02.09.2026  
**Version:** 1.1  
**Status:** source-controlled implementation contract; live readiness still requires the acceptance probes below

This document defines the approved Windows-native topology for CyberStrike 1.1.16. CyberStrike and Metasploit run directly on Windows 11 x64 under the current user. No VM or direct WSL execution is used. The already installed Docker Desktop WSL2 backend is the sole exception and may host only the digest-pinned Bolt container.

This document does not authorize a target or an offensive action. A current signed engagement, exact target allowlist, fresh confirmation, and the independent fail-closed guard remain mandatory. Permanent estate denies are evaluated before every signed allow.

## Immutable inputs

| Component | Exact input | Acceptance truth |
|---|---|---|
| CyberStrike | `@cyberstrike-io/cyberstrike@1.1.16` | npm SRI is exactly `sha512-Yf4fb54n6Apw7qZZFNG32Ok6aMBcfIW+OzvUHovsW/ImP/ETRHdX90ZjFT24/UFgmdYqNy+x9T0dF6yI451FQA==`. |
| Playwright worker dependency | `playwright@1.58.2` | Installed manually with lifecycle scripts disabled and normal TLS verification. |
| Metasploit | `metasploit-framework-6.5.3-20260826060514-1rapid7-1-x64.msi` | MSI SHA-256 `2556D431EF76FD85D39D0C914B604ADCF9D7050A61393B770C4319547501D8C7`; SHA-512 `1439EB70212AA5242D21F062C2D978C023134D2FEFCB0B0010C2F24E77117738300DEA66448A86A71DF88B2D7181A428C4932620D18B17E6B6E198977A895F8B`; valid detached PGP fingerprint `97B32012EA1176F053727A95C048F0B49DEEC457`. Authenticode is `NotSigned`, so that sub-gate is unavailable, not passed. |
| Bolt tag/source marker | `ghcr.io/cyberstrikeus/bolt:93bcf2c` | Never use `latest`. |
| Bolt OCI index | `sha256:90ef2d10a8e255369981e7ce2eb7b89e1ac337ad6a5cf9f21f803c8585eea277` | The runtime image reference includes this digest. |
| Bolt `linux/amd64` manifest | `sha256:b5ddb610ea214656fd97223ed790d3bb50a3d44ae188dc937e64c87a83cc4459` | The selected child manifest matches before any container starts. |

## Topology

```text
native Windows 11 x64, current Windows user
  |
  +-- CyberStrike 1.1.16 (npm, lifecycle scripts disabled)
  |     +-- existing effective XDG cyberstrike root; auth/database/session state stays in place
  |     +-- same-volume versioned staging + recoverable asset-only rename swap
  |     +-- Playwright 1.58.2 + matching Chromium, normal TLS verification
  |     +-- private signed guard and exact engagement workspace
  |     `-- Bolt client -> 127.0.0.1 only
  |
  +-- agent runtimes / external CyberStrike plugin
  |     `-- cyberstrike-gateway (only runtime-facing MCP registration)
  |           +-- harness_bridge_status / harness_capabilities / harness_invoke only
  |           `-- closed revisioned backend manifest; lazy owned stdio children
  |                 +-- cloud-audit 38 / github-security 39 / cve-mcp 41 / osint 37
  |                 `-- metasploit 16 via embedded ruby.exe + official msfmcpd
  |
  +-- Rapid7 Metasploit Framework 6.5.3-20260826060514
  |     `-- embedded\bin\ruby.exe embedded\framework\msfmcpd (gateway-owned only)
  |
  `-- Docker Desktop WSL2 backend (Bolt-only exception)
        `-- digest-pinned linux/amd64 Bolt container
              +-- loopback ingress
              `-- explicit per-container authorized-target egress
```

The private guard owns child process trees, engagement expiry, workspace binding, target egress, job/session ownership, and audit receipts. Raw `msfmcpd`, raw Metasploit RPC, Bolt, and the CyberStrike API are never exposed as general-purpose services.

## One runtime-facing gateway

Register exactly one MCP server for this integration: `cyberstrike-gateway`. Its complete runtime-facing tool surface is exactly:

```text
harness_bridge_status
harness_capabilities
harness_invoke
```

`cloud-audit` (38 tools), `github-security` (39), `cve-mcp` (41), `osint` (37), and `metasploit` (16) remain backend-only entries in the gateway's closed, canonical, revisioned manifest. They comprise 171 backend security IDs; the manifest also retains ten approved Codex/fan-out bridge capabilities. They must not appear in Claude, Codex, Cursor, or another runtime as direct MCP registrations or raw tool families. The gateway compares each backend's normalized ordered tool names and strict schemas, not only its count, with the pinned canonical wire-schema hash before use; it keeps this upstream digest distinct from the gateway policy-overlay hash. Missing/extra/renamed tools, policy-pin mismatch, or schema drift fail startup closed as `capability_inventory_drift`, with per-backend diagnostic entries.

The flow is runtime or external CyberStrike plugin → three-tool gateway surface → exact `MANIFEST_REVISION` plus engagement/schema/risk/confirmation/idempotency/workspace checks → one gateway-owned lazy backend child → bounded redacted result plus append-only receipt. Missing credentials or unsupported platform state marks the affected manifest capabilities unavailable without removing them. No outage or mismatch permits a raw fallback, caller-selected executable/argv, or generic MCP/RPC/console proxy. No backend child starts merely because a runtime session starts; current implementation blocks every launch as `windows_job_object_containment_unverified` until fresh Windows Job Object containment evidence exists.

## CyberStrike 1.1.16: safe installation

### Why the upstream postinstall is disabled

Published package metadata declares:

```text
postinstall = bun ./postinstall.mjs || node ./postinstall.mjs
```

The reviewed 1.1.16 script copies web/skill/worker assets, removes existing shared web and skill directories, installs Playwright in a child process with `NODE_TLS_REJECT_UNAUTHORIZED=0`, and may persistently append npm's global directory to the Windows user PATH. Those side effects violate this estate's TLS and no-overwrite requirements. Do not run the package postinstall.

Never set `NODE_TLS_REJECT_UNAUTHORIZED=0`. When a corporate CA is required, use an owner-approved PEM through `NODE_EXTRA_CA_CERTS` and leave certificate verification enabled.

### Verify metadata and install without lifecycle scripts

Run from a trusted external operator directory, not from this repository or a target checkout:

```powershell
$CyberStrikeVersion = '1.1.16'
$CyberStrikeIntegrity = 'sha512-Yf4fb54n6Apw7qZZFNG32Ok6aMBcfIW+OzvUHovsW/ImP/ETRHdX90ZjFT24/UFgmdYqNy+x9T0dF6yI451FQA=='

if ($env:NODE_TLS_REJECT_UNAUTHORIZED -eq '0') {
    throw 'TLS certificate verification is disabled'
}

$Metadata = npm view "@cyberstrike-io/cyberstrike@$CyberStrikeVersion" version license dist.integrity dist.tarball scripts --json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'npm metadata lookup failed' }
if ($Metadata.version -ne $CyberStrikeVersion) { throw 'Unexpected CyberStrike version' }
if ($Metadata.license -ne 'AGPL-3.0-only') { throw 'Unexpected CyberStrike license metadata' }
if ($Metadata.'dist.integrity' -ne $CyberStrikeIntegrity) { throw 'Unexpected CyberStrike package SRI' }

npm install --global --ignore-scripts "@cyberstrike-io/cyberstrike@$CyberStrikeVersion"
if ($LASTEXITCODE -ne 0) { throw 'CyberStrike install failed' }

$NpmGlobalRoot = (npm root --global).Trim()
$CyberStrikePackageRoot = Join-Path $NpmGlobalRoot '@cyberstrike-io\cyberstrike'
$PackageManifestPath = Join-Path $CyberStrikePackageRoot 'package.json'
$PackageManifest = Get-Content -LiteralPath $PackageManifestPath -Raw | ConvertFrom-Json
if ($PackageManifest.version -ne $CyberStrikeVersion) { throw 'Installed package version mismatch' }

$NpmPrefix = (npm config get prefix).Trim()
$env:PATH = "$NpmPrefix;$env:PATH"  # process-local only
if ((cyberstrike --version).Trim() -ne $CyberStrikeVersion) {
    throw 'CyberStrike executable version mismatch'
}
```

Do not use `@latest`, `cyberstrike upgrade`, a curl/iwr installer, or an upstream source checkout as an install shortcut.

### Version-stage and recoverably swap only reviewed assets

Do not create or select a new empty `XDG_DATA_HOME` for the upgrade. That would strand the live `auth.json`, database, WAL/SHM, storage, logs, session history, and other state in the previous root. Resolve the effective data home exactly as CyberStrike does: use `XDG_DATA_HOME` when it is already set, otherwise `%USERPROFILE%\.local\share`; the live application root is its `cyberstrike` child. This upgrade procedure requires that existing root and never moves, copies, or replaces it.

Build a unique versioned staging tree *under the existing application root* so activation uses same-volume renames. Copy only public/versioned runtime assets; never copy `auth.json`, a database file, storage, logs, configuration, cookies, provider material, Bolt keys, or another secret/state file into staging or rollback.

```powershell
$EffectiveXdgDataHome = if ([string]::IsNullOrWhiteSpace($env:XDG_DATA_HOME)) {
    Join-Path $env:USERPROFILE '.local\share'
} else {
    [IO.Path]::GetFullPath($env:XDG_DATA_HOME)
}
$CyberStrikeDataRoot = [IO.Path]::GetFullPath((Join-Path $EffectiveXdgDataHome 'cyberstrike'))
if (-not (Test-Path -LiteralPath $CyberStrikeDataRoot -PathType Container)) {
    throw "Existing effective CyberStrike data root is absent: $CyberStrikeDataRoot"
}

$AssetVersion = '1.1.16'
$DeploymentId = "$AssetVersion-$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ'))-$([guid]::NewGuid().ToString('N'))"
$AssetStageRoot = Join-Path $CyberStrikeDataRoot ".asset-staging\$DeploymentId"
$AssetPayloadRoot = Join-Path $AssetStageRoot 'payload'
$AssetRollbackRoot = Join-Path $CyberStrikeDataRoot ".asset-rollback\$DeploymentId"
$AssetFailureRoot = Join-Path $CyberStrikeDataRoot ".asset-failed\$DeploymentId"
foreach ($ReservedPath in @($AssetStageRoot, $AssetRollbackRoot, $AssetFailureRoot)) {
    if (Test-Path -LiteralPath $ReservedPath) { throw "Deployment path already exists: $ReservedPath" }
}

$RequiredSources = @(
    (Join-Path $CyberStrikePackageRoot 'web'),
    (Join-Path $CyberStrikePackageRoot 'skill'),
    (Join-Path $CyberStrikePackageRoot 'hackbrowser-worker.js')
)
foreach ($RequiredSource in $RequiredSources) {
    if (-not (Test-Path -LiteralPath $RequiredSource)) {
        throw "Published asset is missing: $RequiredSource"
    }
}

New-Item -ItemType Directory -Path $AssetPayloadRoot | Out-Null
New-Item -ItemType Directory -Path (Join-Path $AssetPayloadRoot 'bin') | Out-Null
Copy-Item -LiteralPath (Join-Path $CyberStrikePackageRoot 'web') -Destination (Join-Path $AssetPayloadRoot 'web') -Recurse
Copy-Item -LiteralPath (Join-Path $CyberStrikePackageRoot 'skill') -Destination (Join-Path $AssetPayloadRoot 'skill') -Recurse
Copy-Item -LiteralPath (Join-Path $CyberStrikePackageRoot 'hackbrowser-worker.js') -Destination (Join-Path $AssetPayloadRoot 'bin\hackbrowser-worker.js')

if ($env:NODE_TLS_REJECT_UNAUTHORIZED -eq '0') { throw 'TLS certificate verification is disabled' }
npm install --prefix $AssetPayloadRoot --save-exact --ignore-scripts playwright@1.58.2 --no-fund --no-audit
if ($LASTEXITCODE -ne 0) { throw 'Staged Playwright package install failed' }

$PlaywrightManifest = Get-Content -LiteralPath (Join-Path $AssetPayloadRoot 'node_modules\playwright\package.json') -Raw | ConvertFrom-Json
$PlaywrightCoreManifest = Get-Content -LiteralPath (Join-Path $AssetPayloadRoot 'node_modules\playwright-core\package.json') -Raw | ConvertFrom-Json
if ($PlaywrightManifest.version -ne '1.58.2' -or $PlaywrightCoreManifest.version -ne '1.58.2') {
    throw 'Staged Playwright package versions do not match the approved pin'
}

$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $AssetPayloadRoot 'ms-playwright'
$PlaywrightCli = Join-Path $AssetPayloadRoot 'node_modules\playwright\cli.js'
& (Get-Command node -ErrorAction Stop).Source $PlaywrightCli install chromium
if ($LASTEXITCODE -ne 0) { throw 'Staged pinned Chromium install failed' }
```

Before activation, record hashes for every staged file and verify the reviewed `web/index.html`, skill inventory, worker hash, both Playwright package versions, and the expected Chromium executable. Gracefully stop CyberStrike and its owned HackBrowser worker, confirm they released the live assets, and keep the data root at the same resolved path. The activation allowlist is exact:

| Staged relative path | Live relative path |
|---|---|
| `web` | `web` |
| `skill` | `skill` |
| `bin\hackbrowser-worker.js` | `bin\hackbrowser-worker.js` |
| `node_modules\playwright` | `node_modules\playwright` |
| `node_modules\playwright-core` | `node_modules\playwright-core` |
| `node_modules\.bin\playwright` | `node_modules\.bin\playwright` |
| `node_modules\.bin\playwright.cmd` | `node_modules\.bin\playwright.cmd` |
| `node_modules\.bin\playwright.ps1` | `node_modules\.bin\playwright.ps1` |
| `ms-playwright` | `ms-playwright` |

For each allowlisted target, rename any existing live asset into the matching relative path beneath `$AssetRollbackRoot`, then rename the staged asset into the live path. Use checked `Move-Item -LiteralPath` operations without `-Force`; source, destination parent, and rollback path must all resolve beneath `$CyberStrikeDataRoot`. Each same-volume activation rename is atomic, while the multi-path sequence is explicitly recoverable rather than falsely described as one filesystem transaction. On any failure, move newly activated assets into `$AssetFailureRoot` and restore every prior asset from rollback in reverse order. Never delete either set and never recursively move the application root.

The non-asset preservation set includes `auth.json`, `cyberstrike.db`, `cyberstrike.db-wal`, `cyberstrike.db-shm`, `storage`, `log`, every Bolt key, configuration, session/history record, and every other entry not listed in the activation table. Verify their paths and private pre/post receipts without printing contents; any unexpected change fails activation and triggers rollback. The rollback and failed-deployment trees contain assets only, never duplicated secrets or state.

After activation, the sterile supervisor retains the original `$EffectiveXdgDataHome`, sets `PLAYWRIGHT_BROWSERS_PATH` to `$CyberStrikeDataRoot\ms-playwright`, validates the active asset hashes, and performs the local web/HackBrowser smoke. Missing assets make only the affected capability unavailable with the exact reason; they never cause a new data root, state migration, raw postinstall, or silent capability removal. Retain the protected asset rollback until owner-reviewed acceptance; do not permanently delete it.

## Native Rapid7 Metasploit MCP

Use the archived artifacts, never the mutable latest link:

```text
https://windows.metasploit.com/metasploit-framework-6.5.3-20260826060514-1rapid7-1-x64.msi
https://windows.metasploit.com/metasploit-framework-6.5.3-20260826060514-1rapid7-1-x64.msi.asc
```

Before installation, require all of the following provenance:

- MSI SHA-256 `2556D431EF76FD85D39D0C914B604ADCF9D7050A61393B770C4319547501D8C7` and SHA-512 `1439EB70212AA5242D21F062C2D978C023134D2FEFCB0B0010C2F24E77117738300DEA66448A86A71DF88B2D7181A428C4932620D18B17E6B6E198977A895F8B`;
- valid detached OpenPGP signature (`gpg` exit `0`) by `Release Engineering <r7_re@rapid7.com>`, full key fingerprint `97B32012EA1176F053727A95C048F0B49DEEC457`;
- signing-key material pinned to Rapid7's `metasploit-omnibus` commit `21d459344aa291e9d8c0abdd6cbd9806fdb84791`, file `config/templates/metasploit-framework-wrappers/msfupdate.erb`, whose recorded SHA-256 is `D12FEA4D1339EBECB09D8CC36920D9F5E5E7E9FFFBE092B1E1CD09255CC16825`;
- optional payload-stream corroboration SHA-256 `CD976D3A02EA16FB8C6AEF1CE3738AC039B5F9C49DA16E6F6ED4CF5E25B344AC` after offline extraction.

The MSI itself reports Authenticode `NotSigned`. That check is recorded as `unavailable: artifact_not_authenticode_signed`; it is not a failure of the detached PGP proof, but it can never be marked passed and a valid Authenticode signer is not an acceptance requirement. Do not substitute trust in a short key ID or an unpinned keyserver result for the full fingerprint and pinned Rapid7 source above. After installation, verify `C:\metasploit-framework\version-manifest.txt` records the approved build. Keep Microsoft Defender and Windows Firewall enabled. If either control quarantines or blocks a component, report that capability unavailable; do not disable a control or add a broad exclusion.

Rapid7's Windows package generator does not create `msfmcpd.bat`. The official path uses the MSI's embedded Ruby directly:

```powershell
$MetasploitRoot = 'C:\metasploit-framework'
$MetasploitRuby = Join-Path $MetasploitRoot 'embedded\bin\ruby.exe'
$MetasploitFramework = Join-Path $MetasploitRoot 'embedded\framework'
$MetasploitMcp = Join-Path $MetasploitFramework 'msfmcpd'
$MetasploitGemfile = Join-Path $MetasploitFramework 'Gemfile'

foreach ($RequiredPath in @($MetasploitRuby, $MetasploitMcp, $MetasploitGemfile)) {
    if (-not (Test-Path -LiteralPath $RequiredPath -PathType Leaf)) {
        throw "Required Metasploit MCP path is unavailable: $RequiredPath"
    }
}

$env:BUNDLE_GEMFILE = $MetasploitGemfile
$env:PATH = "$(Join-Path $MetasploitRoot 'embedded\bin');$env:PATH"
Push-Location -LiteralPath $MetasploitFramework
try {
    & $MetasploitRuby $MetasploitMcp --version
    if ($LASTEXITCODE -ne 0) { throw 'Official msfmcpd probe failed' }
} finally {
    Pop-Location
}
```

For real service startup, `cyberstrike-gateway` sets the child CWD and `BUNDLE_GEMFILE`, injects RPC/MCP settings and credentials through an ACL-restricted file or the child environment, and owns a private stdio child. Never put a username, password, token, or key in argv. Never register raw `msfmcpd` or `metasploit`, enable HTTP transport, expose `msfrpcd`, or provide a generic RPC/console proxy. The runtime sees only the gateway's three tools; the 16 Metasploit entries remain behind its manifest, policy, redaction, and audit boundary.

The expected official MCP inventory is exactly:

```text
msf_credential_info msf_host_info msf_loot_info msf_module_check
msf_module_execute msf_module_info msf_module_results msf_note_info
msf_running_stats msf_search_modules msf_service_info msf_session_list
msf_session_read msf_session_stop msf_session_write msf_vulnerability_info
```

Exactly four upstream tools are marked dangerous: `msf_module_check`, `msf_module_execute`, `msf_session_stop`, and `msf_session_write`. The guard must still classify module and argument semantics. If the official script does not exist or its embedded-Ruby probe fails, keep all 16 entries visible as `unavailable: official_msfmcpd_not_runnable`. The only permitted fallback is a private typed adapter over `msfrpcd.bat` that proves schema/result parity to all 16 official tools and passes the same negative policy suite; a generic adapter is forbidden.

## Bolt through the Docker Desktop exception

The only accepted runtime reference is:

```text
ghcr.io/cyberstrikeus/bolt:93bcf2c@sha256:90ef2d10a8e255369981e7ce2eb7b89e1ac337ad6a5cf9f21f803c8585eea277
```

Before any pull/start, inspect the remote index and verify that its index digest is `sha256:90ef2d10a8e255369981e7ce2eb7b89e1ac337ad6a5cf9f21f803c8585eea277` and its `linux/amd64` child digest is `sha256:b5ddb610ea214656fd97223ed790d3bb50a3d44ae188dc937e64c87a83cc4459`. Use `--platform linux/amd64`. A tag match without both digest checks is not acceptance.

The container remains disconnected until all of these are proven:

- ingress binds only to `127.0.0.1` on a fixed reviewed port;
- no `--privileged`, Docker socket, host network, broad mount, or wildcard bind;
- admin material comes from a Docker secret or ACL-restricted env file, never argv/logs;
- per-container egress can reach only the signed target allowlist and required explicitly approved infrastructure;
- the live container image ID and platform match the approved child manifest;
- the signed wrapper owns stop/expiry and verifies the process/container is gone;
- a future session starts with no inherited engagement grant.

If per-container target egress cannot be mechanically enforced, retain the 45-tool Bolt catalog as visible but `unavailable: target_egress_not_enforced` and do not connect the client.

## Capability support matrix

| Surface | Windows-native disposition | Reason / gate |
|---|---|---|
| CyberStrike CLI/TUI/web | Supported | Exact 1.1.16 binary, in-place asset-only swap inside the existing effective data root, loopback health, sterile supervisor. |
| HackBrowser | Conditionally supported | Exact worker, Playwright 1.58.2, matching Chromium, normal TLS, asset-only rollback, dedicated agent browser profile. |
| `cyberstrike-gateway` | Only runtime-facing MCP registration | Exactly three public tools; five backend-only closed inventories remain visible and fail closed. Current backend launch status is `unavailable: windows_job_object_containment_unverified`. |
| Metasploit 16-tool MCP | Conditionally supported backend only | Exact MSI hashes and detached PGP signer; Authenticode sub-gate unavailable (`NotSigned`); official embedded-Ruby `msfmcpd`; gateway-owned private stdio. |
| `winhook` | Visible, high-risk gated | Administrator plus exact signed technique and confirmation. `defender_exclude` is permanently unavailable because Defender remains enabled. |
| `ebpf` / Linux hooks | Visible, unsupported | Native Windows cannot execute them; direct WSL/VM is outside the approved topology. |
| `machook` | Visible, unsupported | Host is not macOS. |
| `awshook`, `azurehook`, `kubehook`, `cipipe` | Visible, currently unavailable | Exact Windows interpreter/dependency and ambient identity probes have not passed. |
| Bolt 45-tool Linux catalog | Visible, currently disconnected | Docker Desktop exception requires both digests plus verified target egress and loopback ingress. |
| Sliver | Visible only in the denial inventory; not installed | Permanent estate C2 deny. There is no enabling workflow. |
| C2-equivalent Metasploit/session paths | Visible with `permanent_c2_deny` | Permanent deny precedes RoE and confirmation. |

## Permanent security invariants

### Never rotate

NEVER rotate credentials, tokens, or keys. Do not propose rotation and do not touch a credential-rotation manifest. Restarts reuse existing ACL-protected material. If material is missing or suspected exposed, stop, report the blast radius, and leave it unchanged. An owner-explicit retirement is separate from rotation and must remain recoverable; never permanently delete a credential file.

### C2 and Sliver are not RoE-enablable

The following are permanent hard denies evaluated before signed allows:

- installing, starting, exposing, connecting, or enabling Sliver or another C2 framework;
- `multi/handler`, payload/stager/handler creation, persistent listeners, or callbacks;
- Meterpreter or reverse-shell creation and operation;
- interactive session command channels, including Metasploit `msf_session_write`;
- any attempt to encode the same behavior behind a generic shell/RPC/console proxy.

No Rules of Engagement, signed manifest, permission choice, human confirmation, model policy, or administrator role can turn these denies into allows. The affected inventory stays visible with `permanent_c2_deny`; there is no probe or remediation that enables it.

## Acceptance gate

Do not report the topology ready until fresh evidence proves all applicable clauses:

1. `npm view` returns version 1.1.16, AGPL-3.0-only, and the exact SRI above.
2. The installed executable reports exactly 1.1.16 and its package manifest matches.
3. No lifecycle script ran; no process or user scope has `NODE_TLS_REJECT_UNAUTHORIZED=0`; the user PATH was not persistently changed by setup.
4. The original effective XDG data home remains selected; only allowlisted web/skill/worker/Playwright/Chromium assets were same-volume rename-swapped; the pre-existing `auth.json`, DB/WAL/SHM, storage, logs, session/config/state, and secret paths are unchanged and were never copied into staging/rollback.
5. Active versioned web/skill/worker/Playwright/Chromium artifacts exist, match recorded hashes/versions, launch from the existing data root, and retain a verified asset-only rollback set.
6. The archived Rapid7 MSI matches both exact hashes, the detached signature matches the full pinned Rapid7 fingerprint/source, Authenticode is explicitly recorded unavailable as `NotSigned`, and the installed build manifest, embedded Ruby, and `msfmcpd` pass.
7. Only `cyberstrike-gateway` is registered in existing and fresh runtime sessions; its public inventory is exactly three tools, and raw companion/Metasploit registrations and tool families are absent.
8. The gateway retains exact closed backend inventories of 38, 39, 41, 37, and 16 tools with pinned name/schema hashes. No backend starts while Windows Job Object containment remains `unavailable: windows_job_object_containment_unverified`; after that gate passes, an authorized smoke lazy-starts only the selected backend.
9. The Metasploit MCP inventory is exactly 16, with exactly four upstream-dangerous tools, and the negative C2 matrix always denies.
10. Bolt's OCI index and `linux/amd64` child match both expected digests; ingress, egress, mounts, secrets, and stop-on-expiry tests pass before connection.
11. Unsupported/unavailable capabilities remain visible with stable reasons; no capability was silently pruned or substituted.
12. A fresh future session inherits no target authorization, dangerous-mode allow, Bolt grant, Metasploit grant, or mutable action approval.
13. Dual-written CyberStrike skill files are byte-identical and the repository skill validator passes.

Budget-, RAM-, timeout-, or dependency-aborted probes are `FAILED-TO-RUN`, never PASS. A process exit code without the expected on-disk artifact or live probe is not completion.

## Primary sources

- CyberStrike npm metadata: `https://registry.npmjs.org/@cyberstrike-io%2fcyberstrike/1.1.16`
- CyberStrike 1.1.16 package/postinstall source: `https://github.com/CyberStrikeus/CyberStrike/blob/main/packages/cyberstrike/script/postinstall.mjs`
- CyberStrike installation/TLS guidance: `https://docs.cyberstrike.io/docs/getting-started/installation/`
- Rapid7 Windows archive: `https://windows.metasploit.com/`
- Rapid7 nightly-installer documentation: `https://github.com/rapid7/metasploit-framework/blob/master/docs/metasploit-framework.wiki/Nightly-Installers.md`
- Rapid7 Windows wrapper list: `https://github.com/rapid7/metasploit-omnibus/blob/master/config/software/metasploit-framework-wrappers-windows.rb`
- Rapid7 Windows wrapper template: `https://github.com/rapid7/metasploit-omnibus/blob/master/config/templates/metasploit-framework-wrappers-windows/msfwrapper.bat.erb`
- Rapid7 pinned signing-key source: `https://github.com/rapid7/metasploit-omnibus/blob/21d459344aa291e9d8c0abdd6cbd9806fdb84791/config/templates/metasploit-framework-wrappers/msfupdate.erb`
- Official Metasploit MCP entrypoint: `https://github.com/rapid7/metasploit-framework/blob/master/msfmcpd`
- Official Metasploit MCP tools: `https://github.com/rapid7/metasploit-framework/tree/master/lib/msf/core/mcp/tools`

UNIT-COMPLETE: cyberstrike-windows-native-docs-2026-09-02
