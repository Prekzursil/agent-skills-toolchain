# Deep-dive: AzureHound (SpecterOps/AzureHound)

Lane: ad-entra-paths · Date: 2026-09-29 · Verifier: ran every check on this VM (Git Bash on Windows 10 26100).

## Claim under test
"SpecterOps' Azure/Entra data exporter for BloodHound CE — the collector that puts Entra objects and attack paths into the BH graph."

**Verdict: ACCURATE.** Verified against README, source, CI, release assets, a live binary run on this VM, and independent third-party coverage.

## 1. Repo health — `gh api repos/SpecterOps/AzureHound` (executed)
| field | value |
|---|---|
| full_name | SpecterOps/AzureHound |
| description | "Azure Data Exporter for BloodHound" |
| stars | 962 |
| forks | 148 |
| open_issues_count | 38 (only 9 are real issues; rest are PRs — counted via `gh api issues?state=all&per_page=100` filtering out `pull_request`) |
| language | Go |
| license | GPL-3.0 |
| created / pushed | 2022-05-26 / **2026-09-21** (8 days before this dive) |
| archived | false |

Not dead, not fake. Recent commits (via `gh api .../commits`): `chore: update go to 1.27.1 and dependencies to latest BED-9657 (#213)` 2026-09-21; `fix: BED-9539 Handle license error when pulling users` 2026-09-03; `fix: Add additional handling for Authentication_RequestFromNonPremiumTenantOrB2CTenant` 2026-09-02.

## 2. Releases / packaging — `gh api repos/SpecterOps/AzureHound/releases` (executed)
- Latest stable **v3.1.1** published **2026-09-08**, preceded by rc1 (08-31) and rc2 (09-03) — disciplined RC cadence.
- Assets per release: `{darwin,linux,windows}×{amd64,arm64}` zips + sha256. `AzureHound_v3.1.1_windows_amd64.zip` = 5,025,203 bytes, 545 downloads; v3.1.0 windows_amd64 664 downloads.
- A `rolling` prerelease tag tracks `main` (README.md:16-21).
- Docker: `Dockerfile` (golang:1.27.1 → distroless base-debian12:nonroot, Dockerfile:3,13); CI pushes to `ghcr.io/SpecterOps/AzureHound` and `public.ecr.aws/production/azurehound` (build.yml containerize job).

## 3. README — read at out/research/azurehound-repo/README.md (shallow clone)
- Line 3: "The BloodHound data collector for Microsoft Azure" — matches the claim.
- Install (README.md:10-33): release binaries from GitHub Releases, or `go build -o azurehound -ldflags="-s -w -X github.com/SpecterOps/AzureHound/v2/constants.Version=..."` with Go ≥1.25 (go.mod actually demands **go 1.27.1** — go.mod:3 — README's "1.25 or later" is stale).
- Usage (README.md:43-71): `azurehound list -u "$USERNAME" -p "$PASSWORD" -t "$TENANT"`; JWT path via `az account get-access-token` piped to `--jwt`; `configure`/`start` for BloodHound Enterprise collectors.
- Docs live in BloodHound CE docs (README.md:35-39).

## 4. Windows-native feasibility — VERIFIED BY EXECUTION on this VM
Commands run and outputs:
- `curl -sL -o ... AzureHound_v3.1.1_windows_amd64.zip` → 5,025,203 bytes (byte-identical to the release asset size); `file` reports valid ZIP. (Note: this box's `tar` is GNU tar and refuses zip; extracted with `C:/Python314/python.exe -c "import zipfile; ..."`.)
- `out/research/azh-bin/azurehound.exe --version` → **`azurehound version v3.1.1`** ✔
- `azurehound.exe --help` → full CLI, including **Windows-only `install` / `uninstall` commands** ("Installs AzureHound as a system service for BloodHound Enterprise") and Windows-form default config `C:\Users\prekzursil\.config\azurehound\config.json`. ✔
- `azurehound.exe list --help` → subcommands `az-ad`, `az-rm`, apps, app-owners, app-role-assignments, devices, group-members/owners, automation-account-role-assignments, container-registries, function-apps, … — i.e., exactly the Entra + ARM object surface BloodHound graphs.

Source-level Windows support:
- `main_windows.go:29-41`: on Windows the binary detects `svc.IsWindowsService()` (golang.org/x/sys/windows/svc) and runs as a native Windows service; otherwise normal CLI.
- `winres/` + `go run winres/generate-windows-resources/...` in CI embeds a version-info resource into the .exe (build.yml "Generate Windows Resources" step; go.mod:45-46,55 `tc-hib/go-winres`).
- CI build matrix: `os: [darwin, linux, windows] × arch: [amd64, arm64]`, cross-compiled from ubuntu runners with plain `go build` + `GOOS/GOARCH` (no cgo) → pure-Go static binaries.
- Dependencies (go.mod:5-23): Azure SDK `azcore`/`azidentity`, MSAL-for-go (indirect), cobra/pflag/viper, zerolog, lumberjack, `judwhite/go-svc` (Windows service lifecycle). All pure Go; `golang.org/x/sys` has first-class Windows support. No cgo, no WSL, no docker needed on Windows.

**windows = native.** Not winget-packaged (`winget search azurehound` → "No package found"; note winget source update also failed on this box, so that's a weak negative).

## 5. Issues / breakage — `gh api repos/SpecterOps/AzureHound/issues?state=all` (executed)
Discussions: **disabled** (HTTP 410). Only 9 non-PR issues total — very low noise. Breakage history exists and gets fixed:
- #186 / #160 (closed 2026-04): JWT parsing failed with `illegal base64 data` — RawStdEncoding vs RawURLEncoding; fixed.
- #173 (closed 2026-04): "unable to continue processing users, User is not in the allowed roles"; fixed (see also commit BED-9539, 2026-09-03 "Handle license error when pulling users").
- #122 (closed 2025-10): JWT auth regression in versions >2.2.1; fixed.
- #115 (closed 2025-08): Docker image critical vulns; addressed.
- Open: #197 "Cannot process Subscriptions due to Multi-Factor authentication" (interactive auth required for some tenants — an Azure-side constraint, not a code bug); #128 "List tenants in az-ad collection uses different audience than the rest of the objects" (updated 2026-07); #135 custom user-agent feature request.

## 6. Independent mentions (exa REST search, executed; Firecrawl scrape FAILED — "Unauthorized: Invalid token" — so page content confirmed via WebFetch instead)
- **Unit42 / Palo Alto Networks** — "Cloud Discovery With AzureHound / threat-actor-misuse-of-azurehound" (https://unit42.paloaltonetworks.com/threat-actor-misuse-of-azurehound/). WebFetch summary: open-source Go tool, part of the BloodHound suite, enumerates Entra ID + Azure via Graph and Azure REST APIs, maps potential attack paths; used by defenders/red teams AND abused by threat actors (Curious Serpens, Void Blizzard, Storm-0501) after initial access. Strong dual-use relevance signal — this is the tool real adversaries run in cloud discovery.
- **dafthack/GraphRunner** (Black Hills InfoSec) — the main *alternative*, but different niche: M365 post-exploitation module set, not a BloodHound graph feeder.
- **rabbit-sec/GraphRobber** — small alternative BloodHound-style collector for Azure.
- Referenced by RedFoxSec "Entra ID (Azure AD) Enumeration: Complete Attacker Guide", Syslifters pentest handbook (attack-path data collection), swisskyrepo/InternalAllThings azure-enumeration docs.
- Official docs: bloodhound.specterops.io CE collection pages (azurehound, azurehound-flags).

## 7. Corrected ToolFind
- name: AzureHound
- repo: https://github.com/SpecterOps/AzureHound
- what: SpecterOps' official Go collector that exports Entra ID (az-ad) and Azure Resource Manager (az-rm) objects — users, groups, apps, service principals, roles, subscriptions, automation accounts, function apps, container registries — into JSON/streams ingestible by BloodHound CE, producing the Azure/Entra attack-path graph. Same binary doubles as a Windows service for BloodHound Enterprise.
- install: `curl -LO https://github.com/SpecterOps/AzureHound/releases/download/v3.1.1/AzureHound_v3.1.1_windows_amd64.zip` then unzip (verified: python zipfile; this box's GNU tar refuses zip) and run `azurehound.exe`; or any release/rolling zip from GitHub Releases; or from source `go build` (needs Go 1.27.1 per go.mod); or `docker run ghcr.io/SpecterOps/AzureHound`. No winget/choco package.
- windows: native (binary executed on this VM; Windows-service mode coded in main_windows.go).
- value: **high** — it is the canonical, actively-maintained (v3.1.1 on 2026-09-08; commits 2026-09-21) collector for the exact capability gap this lane names: getting Entra attack paths into the BloodHound graph. GPL-3.0, fine for internal use.

## Caveats / not done
- Firecrawl scrape failed with Invalid token (env key rejected server-side); exa + WebFetch used instead. Firecrawl check = not run successfully.
- Did not authenticate the collector against a real tenant (no tenant creds in scope) — collection behavior is taken from README, `list --help` output, and the Unit42 description, not from a live collection run.
- Open issue #197 means some tenants (MFA/interactive-required) can't use pure username/password for az-rm subscription data; JWT path (az CLI token) is the workaround shown in README.md:57-62.
