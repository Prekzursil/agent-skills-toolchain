---
title: dive-EntraGoat
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-entra-goat
---

# Deep-dive: EntraGoat (ad-entra-paths lane)

Date: 2026-09-29. Verifier: deep-dive subagent. Source repo cloned to `out/research/entragoat-src`.

## Claim under test
"986-star deliberately vulnerable Microsoft Entra ID environment with realistic attack challenges — the zero-Docker target range for exercising the whole Entra lane."

**Verdict: CONFIRMED on every checkable point.** Real, active, well-adopted, Windows-native, zero Docker.

## 1. Repo metadata (ran `gh api repos/Semperis/EntraGoat`)

| Field | Value |
|---|---|
| stars | **986** (claim exact match) |
| forks | 97; watchers 14 |
| created | 2025-07-15 |
| pushed_at | **2026-05-06T11:19:10Z** (~5 months before today 2026-09-29 — quiet, not dead) |
| open_issues | 6 (4 are small open PRs incl. dependabot #1; 1 real open bug, see §5) |
| license | MIT |
| language | PowerShell (org: Semperis — reputable AD/identity security vendor) |
| releases/tags | **none** (`gh api .../releases` and `.../tags` both returned `[]`) — install is git-clone-only |
| archived/disabled | false/false |

## 2. Real install command (from README.md:20-46 and docs/getting-started.md)

Recommended path (README "Option A: PowerShell GUI *(recommended, no Node.js)*"):

```powershell
git clone https://github.com/Semperis/EntraGoat && cd EntraGoat
Install-Module Microsoft.Graph -Scope CurrentUser -Force
.\Start-EntraGoat.ps1
```

- Option B (optional): `cd frontend && npm install && npm start` — React 17→19-era CRA app (`frontend/package.json`: react-scripts 5.0.1, react ^19). **Not required.**
- Option C: run scenario scripts directly (`scenarios/EntraGoat-Scenario{1..6}-Setup.ps1`).
- **No pip, no npm, no Docker.** `find . -name Dockerfile -o -name pyproject.toml -o -name setup.py -o -name "*.psd1"` over the clone returned only `./frontend/package.json`. "Zero-Docker" claim is literally true.

## 3. Windows-native feasibility: NATIVE, fully

- Entry script `Start-EntraGoat.ps1:1` declares `#requires -Version 5.1`; lines 24-27 `Add-Type -AssemblyName PresentationFramework/PresentationCore/WindowsBase/System.Xaml` → WPF GUI, Windows-only by design. Works on Windows PowerShell 5.1 (ships with Windows) and pwsh 7+ (README.md:28; docs/getting-started.md "OS: Windows (required for the PowerShell GUI — WPF)").
- Only runtime dependency: **Microsoft Graph PowerShell SDK** sub-modules (Microsoft.Graph.Authentication, .Applications, .Users, .Identity.DirectoryManagement — `scenarios/EntraGoat-Scenario1-Setup.ps1:35-38`), which are first-party Microsoft modules with full Windows support. Setup scripts even auto-install them from the gallery on prompt (`EntraGoat-Scenario1-Setup.ps1:52-65`).
- Scenario scripts themselves went cross-platform: Linux `New-SelfSignedCertificate` breakage (issue #10) was fixed 2026-05-02 by commit "fix: replace New-SelfSignedCertificate with cross-platform .NET API".
- **Non-local prerequisite (not a Windows issue):** you must supply an Entra ID test/trial tenant with Global Administrator (docs/getting-started.md prerequisites table; scenario scripts hard-code test creds, e.g. `EntraGoat-Scenario1-Setup.ps1:18-20`). Free trial tenants satisfy this.

## 4. Content: 6 scenarios, complete lifecycle

Per scenario: `scenarios/` setup + `cleanups/` cleanup + `solutions/` walkthrough + hidden flag (README.md:52-63). Difficulty ladder Beginner→Advanced covering SP ownership abuse, app-only Graph permission abuse, group membership escalation, PIM eligibility, Administrative Units, CBA certificate abuse. Scripts are substantial (532-855 lines each; `grep -c "" scenarios/*.ps1`).

## 5. Issues / breakage (ran `gh api repos/Semperis/EntraGoat/issues?state=all`)

- **Issue #15 (OPEN, 2026-08-07):** Scenario 4 solution fails 403 `PermissionScopeNotGranted` — write scopes for "MS Graph Command Line Tools" SP not consented; reporter had to grant consent as GA to finish. Unresolved. Known sharp edge on S4.
- Issue #10 (closed): Linux cert bug — fixed (see §3).
- Open PRs #1 (dependabot npm group, 2025-08), #3/#5/#8 (small solution-script fixes from 2025-08, unmerged). Repo has been in maintenance-quiet since the 2026-05 UI-polish push; 6 open items total. Not dead: org-driven, conference-presented through 2026.

## 6. Independent mentions (Exa REST search, `api.exa.ai/search`, two queries)

- Help Net Security news coverage: helpnetsecurity.com/2025/08/12/entragoat-vulnerable-microsoft-entra-id-simulate-identity-security-misconfigurations/ (2025-08-12)
- Stream Security: "From Playground to Production: Detecting EntraGoat Scenarios" (2025-08-26) — blue-team detection content built on it
- Security Boulevard series: getting-started (2025-08-04), scenario walkthroughs Aug–Nov 2025 (incl. Scenario 3, 2025-11-06)
- The SOC Spot: "Entra ID Attack & Defense: Investigating Service Principal Misuse with EntraGoat" (2025-12-04)
- Tomer Nahum independent walkthroughs (tomernahum.com, 2025-08)
- Conference presence per README.md:94-102: Black Hat USA 2025 Arsenal, DEF CON 33 Demo Labs, BSides Frankfurt, SEC-T 0x11, Black Hat SecTor/Europe 2025, Black Hat Asia 2026 Arsenal.

Ecosystem adoption is real and includes defensive/detection use, not just red-team.

## 7. Value assessment for this estate

- Fills the Entra ID lane gap exactly: the tool file previously had only BadZure (Azure-wide, Terraform-heavy); EntraGoat is Entra-ID-specific, CTF-shaped, zero infra beyond a free trial tenant.
- Windows-native and Docker-free — matches this VM's constraint perfectly (pwsh + Graph SDK only).
- Caveats carried into the score: no releases/tags (pin by commit), last push 2026-05-06, open S4 breakage (#15), trial-tenant + GA prerequisites are outside the repo.

**Corrected claim wording:** everything in the original claim checks out; add "no tagged releases; quiet since May 2026; Scenario 4 CLI solution path currently broken per open issue #15."