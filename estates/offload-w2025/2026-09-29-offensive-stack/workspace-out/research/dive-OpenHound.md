# Deep-dive: OpenHound (SpecterOps/OpenHound)

Lane: ad-entra-paths · Date: 2026-09-29 · Verifier: lead-verifier subagent

## Verdict up front

**REAL and ACTIVE.** SpecterOps' official OpenGraph collector framework for BloodHound. Claim is
~85% accurate: pipeline (collect→preprocess→convert), OpenGraph file output for BH ingest, and the
jamf/okta/github extensions all verify; ConfigManBearPig-as-dependent verifies. Two corrections:
(1) it is NOT "new Sep 2026" — repo created **2026-04-13**, first release same day; Sep 2026 is just
when v0.4.x landed. (2) "the dockerless way" is half-true — the standalone CLI needs no Docker, but
the project officially ships Docker/Helm/Docker Hub images too (that's the BHE managed mode).

**Windows-native: VERIFIED by running it.** `pip install "openhound[all]"` succeeded in a throwaway
venv on this VM (Windows, CPython 3.14), and `openhound --help` / `openhound collect github --help`
executed correctly, with all three extension collectors registered.

## 1. Repo metadata — `gh api repos/SpecterOps/OpenHound`

Ran: `gh api repos/SpecterOps/OpenHound --jq '{stars: .stargazers_count, ...}'`

| field | value |
|---|---|
| stars | 30 |
| forks | 5 |
| open_issues | 4 (all are open PRs, see §5) |
| license | Apache-2.0 |
| language | Python |
| created_at | **2026-04-13**T16:14:50Z |
| pushed_at | 2026-09-29T17:27:21Z (today) |
| default_branch | main, not archived |
| watchers | 1 |

- 29 releases, v0.1.1 (2026-04-13) → **v0.4.1 (2026-09-16)**. All releases are tag-only: **zero
  binary release assets**; distribution is PyPI + container images.
- 9 contributors; top: ktstrader (34 commits), d3vzer0 (33), emmanuelrobles (7). Two-main-dev
  SpecterOps staff project + a few community commits.
- Commit activity (last ~26 weeks, `gh api repos/SpecterOps/OpenHound/stats/commit_activity`):
  steady weekly commits (0–16/wk), no dead gap.
- Branch list shows in-flight feature work matching the open PRs (BED-9510 BHE Auth, BED-9512
  check-available-jobs, BED-9509 AWS secrets manager) — pushed_at=today comes from these branches.

## 2. What it is (README + docs)

Read: repo `README.md`, `pyproject.toml`, official docs
`https://bloodhound.specterops.io/openhound/overview.md` and `/openhound/community.md`.

- README: "standardized framework for building OpenGraph collectors and converters. Built on
  [DLT] (Data Load Tool)... enforces a collect-first, convert-later pipeline." Docs add: "currently
  in beta and is under active development", "run OpenHound either as a containerized service or as
  a standalone CLI application."
- Pipeline (docs + code):
  1. `openhound collect <collector> ./output` — DLT-based collection, raw JSONL (compressed) on disk.
  2. `openhound preprocess <collector> ./output/<c> ./lookup.duckdb` — optional DuckDB lookup DB.
  3. `openhound convert <collector> ./output/<c> ./graph/<c>` — OpenGraph JSON files
     "that you can upload to BloodHound"; auto-splits graphs into multiple files for upload.
- Other CLI verbs (verified live, §4): `create` (cookiecutter scaffold for new collectors),
  `searches` (saved searches), `rules` (privilege-zone selectors).
- File ingest evidence in code: `src/openhound/destinations/opengraph/destination.py` — the
  `opengraph_file` DLT destination writes `{"graph": {"nodes": [...], "edges": [...]}}` JSON parts
  (`{table}-{part}.json`, 1000-item batches, staging+commit markers for retry-safety). That is the
  OpenGraph JSON format BHCE/BHE ingest as files.

## 3. Packaging / REAL install command

Read: `pyproject.toml`, `Dockerfile`, PyPI JSON, `.github/workflows/`.

- PyPI: `curl -s https://pypi.org/pypi/openhound/json` → HTTP 200, name `openhound`,
  latest **0.4.1** (uploaded 2026-09-16T16:05:42), 30 versions, files
  `openhound-0.4.1-py3-none-any.whl` + sdist (pure-Python wheel). `requires_python >=3.13`.
- **Docs-recommended install** (bloodhound.specterops.io/openhound/community.md):
  ```
  uv tool install openhound                # core, no collectors
  uv tool install "openhound[all]"         # + jamf, okta, github
  uv tool install "openhound[okta,jamf,github]"   # pick collectors
  uv tool upgrade openhound                # upgrade, then reinstall collectors
  ```
  (README's pip-extras link is an internal preview URL
  `didactic-adventure-wrzl3gr.pages.github.io` — stale link in README; the extras themselves are real
  in pyproject.)
- `pyproject.toml` pins: `dlt==1.26.0`, `duckdb==1.5.2`, `pydantic==2.13.3`, plus typer,
  alive-progress, tqdm, psutil, griffe/mkdocstrings (doc generation), cookiecutter+jinja2
  (scaffolding), pydantic-extra-types, types-requests. Build: hatchling + hatch-vcs.
  Extras: `all` = openhound-jamf==0.3.0, openhound-github==0.16.1, openhound-okta==0.7.0.
- Entry point: `openhound = "openhound.main:app"` (Typer CLI). Extensions register via
  `[project.entry-points."openhound.sources"]` (seen in ConfigManBearPig pyproject).
- Docker path (for the record, contradicts "dockerless" as identity): `Dockerfile` (uv builder →
  distroless; targets `cli` and `enterprise` scheduler), `example-configurations/bloodhound-{community,enterprise}/docker-compose.yml`,
  `deployments/helm/openhound/` chart, Docker Hub `specterops/openhound`, ECR publishing added in
  PR #82. Docker/Helm is the BHE "managed" deployment; CE docs push the standalone CLI.

## 4. REAL Windows-native feasibility — executed, not inferred

**Check run on this VM (win32, CPython 3.14.0):**

```
C:/Python314/python.exe -m venv $TEMP/oh-test
$TEMP/oh-test/Scripts/python.exe -m pip install "openhound[all]"    # EXIT=0
$TEMP/oh-test/Scripts/openhound.exe --help
```

Result: CLI renders help with commands `collect, convert, preprocess, create, searches, rules`;
installed `openhound 0.4.1, dlt 1.26.0, duckdb 1.5.2, pydantic 2.13.3, openhound-github 0.16.1,
openhound-okta 0.7.0, openhound-jamf 0.3.0`. `openhound collect --help` lists `github, jamf, okta`
(entry-point dispatch works), and `openhound collect github --help` shows the full Typer pipeline
with DLT contract options.

- Dependency Windows support: duckdb 1.5.2 ships `cp313/cp314 win_amd64 + win_arm64` wheels (PyPI
  JSON check). dlt 1.26.0: `requires_python <3.15,>=3.9.2`, ships `pywin32` / `win-precise-time`
  Windows markers (PyPI JSON check). Everything else is pure Python.
- Known Windows caveats (not blockers for core OpenHound):
  - Python 3.13–3.14 only (dlt caps at <3.15; openhound requires >=3.13).
  - ConfigManBearPig's pyproject.toml documents that **uv-managed (python-build-standalone)
    interpreters abort TLS handshakes on Windows** ("libcrypto-3-x64.dll lacks the OPENSSL_Applink
    cross-CRT shim"), and sets `python-preference = "only-system"`. Relevant to any collector doing
    TLS-heavy collection on Windows; the core openhound install I ran (system CPython) is unaffected.
- Did NOT run a live collection (would need GitHub/Okta/Jamf credentials) — CLI dispatch verified,
  end-to-end collect→convert not executed here.

## 5. Issues / discussions breakage read

Ran: `gh api repos/SpecterOps/OpenHound/issues?state=all&per_page=100` and
`gh api graphql ... discussions { totalCount }`.

- **0 true bug reports; 0 discussions.** All 100 first-page items are PRs (internal BED-* ticket
  workflow); 4 open items are feature PRs (#88 BHE auth path, #80 secrets.toml mount in the
  example docker-compose). Community troubleshooting happens in Slack/Reddit (README links), not GitHub.
- Fixed breakage visible in PR history (useful risk profile): duplicate DLT delivery fixed (#73,
  "Fix OpenGraph batching and prevent duplicate DLT delivery"), table-wide edge batching fix
  (#70), DLT telemetry was on by default until explicitly disabled (#55), non-sensitive data had to
  be moved out of secrets.toml (#57/#54), Docker Scout vulnerabilities patched (#69). The
  destination code even carries a comment "Read normalized JSONL directly to avoid DLT 1.26.x
  duplicate batches" — the project patches upstream DLT quirks quickly.

## 6. ConfigManBearPig + ecosystem (claim check)

- `gh search repos ConfigManBearPig` → **SpecterOps/ConfigManBearPig**, "Python collector for
  adding SCCM attack paths to BloodHound with OpenGraph", **150 stars**, updated 2026-09-18.
  Its `pyproject.toml` declares `dependencies = ["openhound>=0.2.12", ...]` and an
  `[project.entry-points."openhound.sources"] sccm = ...` hook; install pattern documented in-file:
  `uv tool install openhound --with configmanbearpig`, CLI verb `openhound collect sccm`. Confirms
  OpenHound is the base of CMBP 2.0. Same author's Mayyhem/openhound-collector-common (6★) also
  mentions MSSQLHound as an OpenHound-based on-prem collector.
- jamf/okta/github extensions: separate repos SpecterOps/openhound-{jamf,okta,github}, pinned as
  pip extras, dispatch verified live (§4). ✅
- Independent mentions (Exa neural search):
  - **AWSHound** (n0pe-sled blog 2026-08-10; specterops.io blog 2026-08-19) — open-source AWS
    OpenGraph collector that emits "a compressed .zip archive of graph JSON" for BHCE upload.
    **Not built on OpenHound** (blog never mentions it) — it hand-authors OpenGraph JSON. This is
    the main *alternative path*: OpenGraph is the platform format; OpenHound is SpecterOps'
    framework for producing it.
  - **ShareHound** (specterops.io blog 2025-10-30) — OpenGraph collector for network shares.
  - **runzero** blog "Identifying exposures at scale with BloodHound OpenGraph" (2026-07-08) —
    independent vendor content validating the OpenGraph ecosystem.
  - OpenGraph Library (bloodhound.specterops.io/opengraph/library.md) lists ~28 extension
    categories (1Password, Ansible, Atlassian, Cisco Duo, CyberArk, Entra ID, FreeIPA, GitLab,
    Kubernetes, MSSQL, Exchange, OCI, Salesforce, Snowflake, System Center, Tailscale, vCenter,
    npm, ...) — a broad, growing beyond-AD ecosystem that OpenHound is the canonical build target for.

## 7. Corrected claim, fact by fact

| claim | verdict |
|---|---|
| "New (Sep 2026)" | ❌ created 2026-04-13, 29 releases since; Sep 2026 = v0.4.x window. Active (pushed 2026-09-29). |
| "SpecterOps collector framework" | ✅ SpecterOps org, BloodHound-adjacent branding, staff contributors. |
| "collect→preprocess→convert" | ✅ exact CLI verbs, verified running. |
| "producing OpenGraph datasets for BloodHound File Ingest" | ✅ OpenGraph JSON parts; docs: "upload to BloodHound"; auto-split for upload. |
| "the dockerless way" | ⚠️ half — standalone `uv tool install` CLI is the CE path, but Docker/Helm/Docker Hub are first-class (BHE managed mode). |
| "base of ConfigManBearPig" | ✅ CMBP pyproject depends on `openhound>=0.2.12`, entry-point registration, `openhound collect sccm`. |
| "jamf/okta/github extension collectors" | ✅ pip extras + separate repos + live dispatch. |

## 8. Commands run (exact)

- `gh api repos/SpecterOps/OpenHound` (+ `--jq` field extraction)
- `gh api repos/SpecterOps/OpenHound/contents` and `/contents/{README.md,pyproject.toml,Dockerfile,src/openhound/main.py,src/openhound/destinations/opengraph/destination.py}`
- `gh api repos/SpecterOps/OpenHound/git/trees/main?recursive=1`
- `gh api repos/SpecterOps/OpenHound/releases`, `/issues?state=all`, `/contributors`, `/stats/commit_activity`, `/commits`, `/branches`, graphql discussions
- `curl -s https://pypi.org/pypi/openhound/json`, `/duckdb/1.5.2/json`, `/dlt/1.26.0/json`
- `curl -s https://bloodhound.specterops.io/llms.txt`, `/openhound/overview.md`, `/openhound/community.md`, `/opengraph/library.md`, `_llms/blood-hound/open-graph.md`
- `gh api repos/SpecterOps/ConfigManBearPig/contents/pyproject.toml`; `gh search repos ConfigManBearPig`
- `curl -s https://api.exa.ai/search ...` (2 queries: keyword + neural/blog)
- Windows install test: `python -m venv $TEMP/oh-test && pip install "openhound[all]"` (EXIT=0),
  then `openhound --help`, `openhound collect --help`, `openhound collect github --help` — all executed.

Not run: a live end-to-end collect→convert (needs source credentials); WebFetch of the
specterops.io AWSHound blog was run (confirmed OpenHound not mentioned).
