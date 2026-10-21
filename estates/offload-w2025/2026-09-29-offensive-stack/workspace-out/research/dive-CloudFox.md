# Deep-dive: CloudFox (BishopFox/cloudfox)

Candidate (from "ad-entra-paths" lane): "2583-star situational-awareness for cloud pentests incl. IAM privesc analysis; prebuilt Windows exe."
Dive date: 2026-09-29. All checks run on this VM during this dive.

## 1. Repo metadata (gh api repos/BishopFox/cloudfox)

Ran: `gh api repos/BishopFox/cloudfox` →
- `stargazers_count`: **2583** — claim matches exactly
- `forks_count`: 256 | `open_issues_count`: 10 (issues+PRs)
- `pushed_at`: **2026-08-20T18:39:52Z** (~6 weeks before dive date) — alive, not stale
- `created_at`: 2022-09-08 | `archived`: false | `disabled`: false
- `license`: **MIT** | `language`: **Go** (not Python — no pyproject/setup.py/package.json exists)
- `default_branch`: main

Contributors (`gh api .../contributors`): sethsec-bf 377, carlosvendramini-bf 100, jbarciabf 73, sethsec 46, edcops1 30. Latest commit 2026-08-20 (matches pushed_at). CI: `.github/workflows/autorelease.yml`, `codespell.yml`. No Dockerfile anywhere in the tree.

## 2. Packaging & REAL install commands

Read `README.md:61-86` ("Install") and `Makefile`. It's a Go module (`go.mod:1-3`, `go 1.25.9`), so packaging = cross-compiled binaries:

1. **Prebuilt zip from releases** (primary). Verified assets via `gh api repos/BishopFox/cloudfox/releases`:
   - Latest tag **v2.0.5** (2026-05-26). 2026 releases: v2.0.2 (04-12), v2.0.3 (04-13), v2.0.4 (04-21), v2.0.5 (05-26).
   - `cloudfox-windows-amd64.zip` 104,039,199 bytes, **810 downloads**; linux-amd64 3,985. Six OS/arch targets incl. windows-amd64, linux-386/arm64, macos-amd64/arm64.
   - `Makefile:30-62` (`release:` target) is what produces these zips via `GOOS=windows GOARCH=amd64 go build` etc.
2. `brew install cloudfox` — verified live: `https://formulae.brew.sh/api/formula/cloudfox.json` → HTTP 200, `stable: 2.0.5`, bottled, zero dependencies (static Go binary).
3. `go install github.com/BishopFox/cloudfox@latest` (README.md:67).
4. Source build: `git clone … && go build .` (README.md:69-78).

## 3. Windows-native feasibility — VERIFIED BY EXECUTION, not just docs

Downloaded the actual release artifact on this VM and ran it:

```
curl -sL -o cloudfox-windows-amd64.zip \
  https://github.com/BishopFox/cloudfox/releases/download/v2.0.5/cloudfox-windows-amd64.zip
```
- zip = 104,039,199 bytes (matches API asset size). Contents: `cloudfox/cloudfox.exe`, `cloudfox/sha1sum.txt`.
- `sha1sum cloudfox.exe` → `291a954496f56038a533125a5589ba43c918c2bd` — identical to the published `sha1sum.txt` line.
- `./cloudfox.exe -v` → `... version 2.0.5`
- `./cloudfox.exe --help` → cobra help renders: commands aws / azure / gcp / completion / help.
- `./cloudfox.exe aws --help` → full AWS command list (~34 commands).
- `./cloudfox.exe aws iam-simulator --help` → renders with flags and usage examples.
- `./cloudfox.exe gcp --help` → renders (~60 commands).

No emulation, no WSL, no Docker: **native win32 execution passed.**

Code-level Windows support (read in clone at out/research/cloudfox-src):
- `aws/shared.go:115-123` — explicit `runtime.GOOS == "windows"` branch (pmapper data via `os.UserConfigDir()` + backslash paths).
- `gcp/services/foxmapperService/foxmapperService.go:271-294` — darwin/windows branches for data dirs.
- Deps `github.com/mattn/go-colorable`, `github.com/erikgeiner/coninput` (go.mod:199, :113) = Windows console color/input support.
- No unix-only syscall usage found: `grep -rl "runtime.GOOS|syscall\."` over *.go hits only the two files above.

Dependencies (go.mod, all pure-Go / cross-platform): aws-sdk-go-v2 (many services), Azure sdk-for-go + azidentity, google.golang.org/api + cloud.google.com/go, cobra, logrus, dominikbraun/graph, neo4j-go-driver (for pmapper/foxmapper graph work). Nothing Windows-hostile.

Runtime prerequisites (README.md:88-113): for real work it needs credentials — AWS CLI profiles/env/IMDS (+ suggested `SecurityAudit` + custom policy), Azure CLI session (Viewer role), or `gcloud auth application-default login` (roles/viewer+). The binary itself needs nothing installed.

## 4. "IAM privesc analysis" claim — TRUE

- AWS: `aws/iam-simulator.go` (IAM policy simulator), `aws/pmapper.go` (ingests nccgroup PMapper graph → who can privesc to admin), `aws/cape.go` + `cape-tui.go` (cross-account privesc enumeration), `workloads` flags admin roles. README.md:164,175,183-193.
- GCP: `gcp/commands/privesc.go` (917 lines; cobra help text lists SA token creation, SA key creation, setIamPolicy, privileged compute/functions deploy, "60+ more techniques"; FoxMapper graph-based, requires `foxmapper gcp graph create` first — file read directly), plus `hiddenadmins.go`, `lateralmovement.go`, `dataexfiltration.go`, `foxmapper.go`.
- `gcp/services/iamService/iamService.go` is 1,986 lines of IAM enumeration logic.
- Azure is the thin spot: only whoami/inventory/rbac/storage/vms (README.md:197-204) — no Azure privesc analysis. Note: README.md:56 says "Azure | 4" but the table itself lists 5 commands; and "Kubernetes: Support Planned".

## 5. Issues / breakage (read via gh api issues?state=all&sort=updated)

- **README.md:4 banner (12/2025):** all versions < v1.17.0 stopped working after a format change in AWS's public service-mapping file (PR #109). Anyone on old binaries is dead → must be ≥1.17.0.
- Issue #129 (closed): `panic: concurrent map read and map write` in network-ports → fixed PR #130, shipped in v2.0.5.
- Issue #132 (closed): "Hang and 3 minute delay at Status: 36/37 regions complete for AWS" → fixed by PR #134 "Fix region slowness and hangs with opt-in/unreachable regions", **merged 2026-08-20 — AFTER v2.0.5 (2026-05-26)**. So the current prebuilt exe still has the region-hang; the fix is only on `main` (`go install …@latest` / source build) until the next tag. This is the one real gotcha for exe users.
- PR #125 (merged): Go 1.25.9 upgrade, "fix 24 stdlib vulnerabilities" — dep hygiene is current.
- Open items are small: PR #136 (add Darkmoon platform listing), PR #135 (outbound-assumed-roles bugfix), PR #133 (bedrock-agents module), issue #131 (HTML/MD report feature request).
- 10 open issues total on a 2.5k-star repo = healthy triage, not a bug graveyard.

## 6. Independent mentions & alternatives (exa REST search)

Search 1 (tool name) → mostly first-party: bishopfox.com tool page, "Introducing CloudFox" blog, "Introducing CloudFox GCP attack path identification for Google Cloud" blog, repo + wiki.
Search 2 (`cloudfox aws enumeration walkthrough -site:bishopfox.com -site:github.com`) → genuine third-party signal:
- Red Fox Security academy: "Using CloudFox for AWS Enumeration — Complete Pentester Guide"
- Pwned Labs walkthroughs on Medium (Blackhawakk; akarshad428)
- Alejandro Perez Medium: S3 replication privesc deep dive combining **Pacu, CloudFox, aws-enumerator**
- meterpreter.org coverage; 1337skills cheatsheet

Alternatives (README.md:289-311 FAQ "Prior work and related projects", read directly): ScoutSuite, Prowler (compliance/benchmark tools — different purpose), **Pacu** (adds exploitation automation, CloudFox deliberately avoids), Steampipe, PMapper, Cloudsplaining, weirdAAL, enumerate-iam. CloudFox's own positioning (README.md:291-293): no findings/alerts, built to speed manual pentesting.

## 7. Verdict

- Repo is real, maintained (2026 releases; last push 2026-08-20), MIT, exact 2583 stars as claimed.
- Claim-by-claim: 2583 stars ✔ (gh api); situational awareness for cloud pentests ✔ (README + 34 AWS / 5 Azure / ~60 GCP commands measured via --help); IAM privesc analysis ✔ (iam-simulator, pmapper, cape, GCP privesc/foxmapper — but Azure-side privesc absent); prebuilt Windows exe ✔ (downloaded, sha1-verified, executed natively on this VM).
- Caveats: 104 MB exe (all three cloud SDKs statically linked); region-hang fix (#134) unreleased in exe form as of dive date; needs real cloud creds to produce anything; GCP privesc needs a prior `foxmapper gcp graph create` run; <v1.17.0 builds are bricked.

## 8. Reproduction commands

```
gh api repos/BishopFox/cloudfox --jq '{stargazers_count,pushed_at,open_issues_count,license:.license.spdx_id,language}'
gh api repos/BishopFox/cloudfox/releases --jq '[.[]|{tag_name,published_at}]'
git clone --depth 1 https://github.com/BishopFox/cloudfox.git out/research/cloudfox-src
curl -sL -o cloudfox-windows-amd64.zip https://github.com/BishopFox/cloudfox/releases/download/v2.0.5/cloudfox-windows-amd64.zip
./cloudfox.exe -v ; ./cloudfox.exe aws iam-simulator --help ; ./cloudfox.exe gcp --help
curl -s -X POST https://api.exa.ai/search -H "x-api-key: $EXA_API_KEY" -d '{"query":"cloudfox aws enumeration walkthrough ..."}'
```
Working copy of source: `out/research/cloudfox-src`; verified binary: `out/research/cloudfox-bin/cloudfox/cloudfox.exe`.
