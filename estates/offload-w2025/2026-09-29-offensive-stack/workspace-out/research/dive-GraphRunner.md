# Deep-dive: GraphRunner (lane: ad-entra-paths)

Date: 2026-09-29. Candidate claim under test: "1345-star PowerShell post-exploitation toolset over Microsoft Graph: Entra recon, OAuth consent abuse, CA-policy dumps, M365 pillaging; no third-party modules."

Verdict up front: **claim verified on every point I could execute; repo is alive (last push 2026-04-09), real, widely referenced by third parties, and runs Windows-native with zero dependencies. Value: high.**

---

## 1. Repo metadata (command: `gh api repos/dafthack/GraphRunner`)

| Field | Value |
|---|---|
| stars | **1345** (claim exact) |
| language | PowerShell |
| license | MIT (LICENSE in repo) |
| open_issues_count | 4 — all four are open **PRs** (#35, #47, #50, #51); zero plain open issues |
| pushed_at | 2026-04-09T20:13:39Z (~5.6 months before today) |
| created_at | 2023-08-15T17:19:11Z |
| archived / fork / disabled | false / false / false |
| watchers | 19 |
| description | "A Post-exploitation Toolset for Interacting with the Microsoft Graph API" |

Releases: `gh api repos/dafthack/GraphRunner/releases` → `[]`. No releases, no packaged assets.

Commit cadence (`gh api .../commits?per_page=100`, dates of latest 100): 2023: 63, 2024: 21, 2025: 5, 2026: 11. Newest 2026-04-09. The 2026 burst is a real work session: `a182e0a Refactored Invoke-DumpCAPS and Invoke-DumpApps` (2026-04-07), `4ea4d95 Fix support for pwsh 5.1` (2026-04-09, removes a PS7-only ternary so Windows PowerShell 5.1 works). Owner (Beau Bullock, @dafthack, Black Hills InfoSec) still maintains; low cadence, not dead.

## 2. What the repo actually is (read from clone at out/research/_gr, HEAD = 4ea4d95)

`git ls-files` → complete file list:

```
GraphRunner.ps1            # the tool: 9,902 lines, 73 functions
GraphRunnerGUI.html        # browser GUI that pillages an account via an access token
IncomingWebhookTemplate.txt
PHPRedirector/{AutoOAuthFlow.py,index.php,ip.php,login.php}  # OAuth code-harvest redirector
default_detectors.json     # pillage search queries (AWS keys, private keys, conn strings, ...)
LICENSE  README.md
```

**Packaging: there is none.** No pyproject.toml, setup.py, requirements.txt, package.json, Dockerfile, or GitHub release assets. The REAL install is: clone/download, then in PowerShell:

```powershell
Import-Module .\GraphRunner.ps1
Get-GraphTokens   # device-code / ROPC / refresh-token / app-only auth → $tokens, $tenantid
```

(README.md:38-41, and the wiki at https://github.com/dafthack/GraphRunner/wiki — HTTP 200 today.)

## 3. Claim vs. source — capability check

All verified by grepping function definitions and resolving them at runtime (see §5):

- **Entra recon**: `Invoke-GraphRecon`, `Get-SecurityGroups`, `Get-DirectoryRoles`, `Invoke-GroupLookup`, `Get-UpdatableGroups`, `Get-DynamicGroups` (GraphRunner.ps1 function list).
- **CA-policy dumps**: `Invoke-DumpCAPS` plus a dedicated CAPS* helper family (Get-CAPSModernData/LegacyData/Summary etc.) — refactored by the author 2026-04-07.
- **OAuth consent abuse**: `Invoke-InjectOAuthApp`, `Invoke-DeleteOAuthApp`, `Invoke-AutoOAuthFlow` (local HttpListener catches auth codes, GraphRunner.ps1:1485-1520), consent-URL construction with `[System.Web.HttpUtility]::UrlEncode` at GraphRunner.ps1:695, plus the PHP redirector kit.
- **M365 pillaging**: `Invoke-SearchMailbox`, `Get-SharePointSiteURLs`, Teams modules (`Get-TeamsChat`, `Get-TeamsChannels`, `Get-Webhooks`...), `Invoke-SearchUserAttributes`, `Invoke-ImmersiveFileReader`, BEC persistence via `Invoke-CreateInboxForwardingRule` (GraphRunner.ps1:1680-1741).
- **No third-party modules**: TRUE for the PowerShell core. `Get-GraphTokens` help block: "Required Dependencies: None / Optional Dependencies: None". Only in-box .NET is used: `System.Web` (HttpUtility; `Add-Type` at GraphRunner.ps1:1485) and `System.Net.HttpListener`. **Caveat**: the optional OAuth-redirector helper `PHPRedirector/AutoOAuthFlow.py` imports third-party Python packages `requests` and `watchdog` — the "no dependencies" claim does not extend to that optional helper.

## 4. Dependencies and Windows support

- Core: zero external dependencies; `System.Web` and `System.Net` are Microsoft assemblies present on Windows.
- Verified on this box: `Add-Type -AssemblyName System.Web` succeeds under pwsh 7.6.6; `[System.Web.HttpUtility]::UrlEncode` resolves in a fresh pwsh 7 session even without Add-Type (ran out/research/gr_httputility.ps1).
- README claims "Works with Windows and Linux" (README.md:28). Windows verified (§5); Linux NOT tested here.
- Optional helper needs `pip install requests watchdog` (Python).

## 5. Windows-native feasibility — actually executed on this VM

Smoke test file out/research/gr_smoke.ps1, run with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...`:

```
PSVersion: 5.1.26100.33438
ParseErrors: 0                      (Parser::ParseFile, Windows PowerShell 5.1)
[banner prints]
ImportedOK: True
  HAVE: Get-GraphTokens, Invoke-DumpCAPS, Invoke-DumpApps, Invoke-SearchMailbox,
        Invoke-GraphRecon, Invoke-SecurityGroupCloner, Invoke-InjectOAuthApp,
        Get-SharePointSiteURLs, Invoke-SearchUserAttributes
```

Also 0 parse errors under pwsh 7.6.6. (`Invoke-MultiToken` in my checklist was a name I guessed — it does not exist in the file; not a tool defect.) No network calls happen at import; only the Write-Host banner and function definitions. Against a real tenant you supply tokens via `Get-GraphTokens` — not exercised here (no tenant creds in scope for this dive).

## 6. Issues / breakage history (`gh api .../issues?state=all`)

- #48 "Import-Module currently throws an error" (2025-07-22, mojibake UTF-8 corruption) — closed, and my §5 import on current HEAD passes, so fixed.
- #39 "-Device and -Browser broke the script" (2024-11, closed); #40 fixed it.
- #42 Invoke-SearchMailbox download issue (2025-04, closed); #32 SharePoint listing capped at 500 → fixed by PR #44 (2025-07, MaxSites param); #22 Get-SecurityGroups returning all groups → fixed via #23.
- Feature-issue #41 (permissive calendars) still just closed without implementation.
- Open PRs untouched by owner: #51 (custom User-Agent/ClientID, 2026-05), #50 (auth-code flow, 2025-09), #47, #35.
- Pattern: module-level regressions happen after refactors but the owner fixes them; nothing currently broken that I could find.

## 7. Independent mentions (Exa REST search, api.exa.ai, this session)

- SOC Prime: "GraphRunner Activity Detection: Hackers Apply a Post-Exploitation Toolset to Abuse Microsoft 365 Default Configurations" — defenders are writing detections for it.
- CraftedSignal threat-feed brief (2026-05): "ClearFake, ACR Stealer, and GraphRunner Emerge as Significant Threats" — evidence of real-world offensive use.
- Pwned Labs training lab ("Loot Exchange, Teams & SharePoint with GraphRunner"); three65pros.com writeup.
- Author-affiliated: BHIS "Introducing GraphRunner" blog + GraphRunner cheatsheet (2025-08-06).
- Alternatives / adjacent ecosystem: dirkjanm/ROADtools (Entra recon framework), Azure/Stormspotter, mlcsec/GraphPython (Python reimplementation of GraphRunner), rabbit-sec/GraphRobber. GraphRunner is the PowerShell-native option; ROADtools is the main Python alternative.

## 8. Corrected ToolFind

- name: GraphRunner
- install: `git clone https://github.com/dafthack/GraphRunner` then `Import-Module .\GraphRunner.ps1` (verified on Windows PowerShell 5.1 and parses clean on pwsh 7.6.6; optional OAuth helper: `pip install requests watchdog` + PHP host)
- windows: **native** — executed import successfully on this VM
- value: **high** — matches the ad-entra-paths lane exactly (Entra recon, CA-policy dumps, consent-grant abuse, M365 pillaging), zero-dependency single-file PowerShell, verified working on this Windows box, actively referenced in threat intel and detection content.

Caveats: last push 2026-04-09 (quiet ~5.6 months, but 2026 commits show active refactoring); Linux claim untested; GUI/redirector components are extras beyond the verified PowerShell core.
