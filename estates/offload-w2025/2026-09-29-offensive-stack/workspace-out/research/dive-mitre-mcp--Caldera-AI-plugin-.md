---
title: dive-mitre-mcp--Caldera-AI-plugin-
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-mitre-mcp-caldera-ai-plugin
---

# Deep-dive: mitre/mcp (Caldera AI plugin)

Lane: c2-agentic. Date of verification: 2026-09-29. All checks below were run in this session.

## Verdict up front

The repo is **real, official, and actively maintained** — it is exactly what the claim says, with one
material correction to the deployment story: it is **not** a remote bolt-on to an existing Caldera RPC.
It is an in-process Caldera plugin that must be cloned **into** the existing Caldera tree, pip-installed
into that Caldera venv, and loaded via `conf/local.yml` before a Caldera restart. No new Docker container
is required (repo ships no Dockerfile), but if the estate's Caldera runs containerized, adding this plugin
still means modifying that existing deployment.

## Repo metadata

`gh api repos/mitre/mcp` (run 2026-09-29):

```json
{"archived":false,"created_at":"2025-10-30T18:46:20Z","default_branch":"main",
 "description":"An AI-powered plugin for Caldera that orchestrates long-running LLM workflows to automatically create adversary emulation abilities and plan operations. Optionally enriches workflows with Retrieval-Augmented Generation (RAG) using Cyber Threat Intelligence (CTI) from STIX JSON files.",
 "forks":11,"homepage":"https://caldera.apache.org/","language":"Python","license":"Apache-2.0",
 "open_issues":0,"pushed_at":"2026-09-03T16:33:15Z","stars":40,"topics":["caldera","caldera-plugin"]}
```

- 40 stars, 11 forks, 0 open issues/PRs. Pushed 26 days ago. Not archived, not a fork.
- **Provenance is genuinely official**: repo lives under `github.com/mitre`; the official Caldera team
  Medium post "Connecting LLMs to Caldera with the MCP Plugin" (medium.com/@mitrecaldera, 2025-11-10,
  by Ethan Michalak and Mark Perry — fetched via web_reader) announces it, ties it to DEF CON research
  ("Post-DEF CON" is the message of the repo's first commit, 2025-10-30: `Merge branch 'postdefcon' into 'main'`),
  and links `github.com/mitre/MCP`. There is a Gitee mirror (`gitee.com/mirrors_mitre/MCP`).
- **Caldera core itself has moved to Apache**: `gh api repos/mitre/caldera` and
  `gh api repos/apache/caldera` return identical data (created_at 2017-11-29, pushed_at 2026-08-27,
  7298 stars) — a GitHub org transfer, and the plugin's homepage is `caldera.apache.org`. So "MITRE's
  official Caldera plugin" is accurate today, but the Caldera project is now an ASF project; this plugin
  still lives in the `mitre` org.

## Claim-by-claim

| Claim | Verdict | Evidence |
|---|---|---|
| Official MITRE Caldera plugin | ✅ | mitre org; official Medium announcement 2025-11-10; topics `caldera`,`caldera-plugin`; `hook.py` implements the Caldera plugin contract (`name='mcp'`, `address='/plugin/mcp/gui'`, hook.py:29-32) |
| Orchestrates long-running LLM workflows | ✅ | DSPy ReAct agent loop (README Architecture; `app/dspy_env.py` `dspy.configure(lm=dspy.LM(**lm_kwargs))`); MLflow trajectory logging per run (`app/mlflow_run.py`) |
| Auto-generates adversary-emulation abilities | ✅ | "Author" workflow (`app/workflows/author.py`); command-generation DSPy chain is platform-aware: `IdentifyTechnologies` docstring "For windows, the basic shell interpreter is powershell.exe. For linux, ... bash." (app/dspy_env.py:172-181) |
| Plans operations | ✅ | "Plan and Execute" workflow (`app/workflows/plan_execute.py`) |
| Optional RAG over STIX CTI | ✅ | CTI ingest pipeline produces STIX 2.1 bundles; selected bundles injected as `cti_context` before the ReAct loop (README Workflows + Architecture); `conf/default.yml` `cti:` section with `context_budget_tokens: 24000` |
| "Newer than Caldera" | ✅ | Repo created 2025-10-30 vs core's 2017; pushed 2026-09-03 vs core's 2026-08-27 — even fresher than core |
| "Bolts onto the estate's EXISTING caldera rpc, no new Docker" | ⚠️ half | No new Docker ✅ (no Dockerfile anywhere in the tree; loads in-process). But it is **not** a remote attachment: `hook.py` runs inside the Caldera server, and the plugin registers aiohttp routes on Caldera's own server (`app/mcp_api.py`). Install = clone into `plugins/` of the existing tree + pip into its venv + restart. `CALDERA_URL` exists only for spawned subprocesses in split deployments (`.env.example` comments) |

## REAL install command (README.md, verified verbatim)

From the **Caldera root** (the existing Caldera checkout):

```bash
git clone https://github.com/mitre/mcp.git plugins/mcp
source venv/bin/activate
pip install -r plugins/mcp/requirements.txt
python -m spacy download en_core_web_lg
cp plugins/mcp/.env.example plugins/mcp/.env
```

Then add `mcp` to the `plugins:` list in `conf/local.yml` (alongside `magma`, `sandcat`, `stockpile`)
and restart Caldera (`python server.py --insecure`; add `--build` if UI assets changed). Note the extra
step pip cannot do: the spaCy `en_core_web_lg` model is a separate command.

**Packaging reality**: no `pyproject.toml`, no `setup.py`, no `package.json`, no Dockerfile,
**no releases and no tags** (`gh api repos/mitre/mcp/releases` → `0`; tags list empty). You install
HEAD of `main`, unpinned — and `main` takes breaking refactors (`refactor(cti)!` #42, `refactor(config)!` #26,
`chores(cti)!` #28). If the estate adopts this, pin a commit hash.

## Dependencies and Windows support (checked against PyPI JSON API, this session)

`requirements.txt` (read from repo):

- Core-owned floors: `aiohttp>=3.14.1`, `aiohttp-jinja2>=1.5.1`, `jinja2>=3.1.6`, `lxml>=6.1.0`, `PyYAML>=6.0`
- Plugin-only (unpinned): `aiofiles`, `beautifulsoup4`, `dspy`, `litellm`, `mcp>=1.9,<2`, `mlflow`, `numpy`,
  `psutil`, `pydantic`, `python-dotenv`, `rapidfuzz`, `requests`, `spacy`, `trafilatura`

Windows-wheel check (`curl pypi.org/pypi/<pkg>/json`, current versions):

| Package | Version | Windows |
|---|---|---|
| spacy | 3.8.16 | 9 win wheels ✅ |
| lxml | 6.1.3 | 32 win wheels ✅ |
| numpy | 2.5.3 | 18 win wheels ✅ |
| rapidfuzz | 3.14.6 | 22 win wheels ✅ |
| psutil | 7.2.2 | 6 win wheels ✅ |
| litellm | 1.103.0 | win wheel ✅ |
| mlflow / dspy / trafilatura | 3.16.1 / 3.4.0 / 2.2.0 | pure-python ✅ |

Code-level portability (read from repo):

- MLflow server spawn uses `sys.executable, "-m", "mlflow", "server"` — portable, explicitly not a bare
  `mlflow` binary (hook.py:170-180).
- MCP tool servers spawn via `StdioServerParameters(command=sys.executable)` + `mcp.client.stdio.stdio_client`
  (app/workflows/plan_execute.py:250-256).
- `pdftotext` (poppler) invoked via `asyncio.create_subprocess_exec` with `FileNotFoundError` → explicit
  501 "Install poppler" response (app/mcp_api.py:~987-1000). TXT/MD/HTML ingest work without it.
- Plugin discovery parses other plugins' `MCP_METADATA` with `ast.literal_eval` — never executes plugin
  code in the parent (app/discovery/servers.py).
- Path handling is `os.path`/`pathlib` throughout; no `/bin/bash`, `os.fork`, or POSIX-only signals found
  in the spawn paths.

**Honest limits of this feasibility finding**: this is **static verification only — I did not install or
run the plugin on Windows in this ask**. The README/quickstart are bash-flavored and the poppler note
covers only macOS (`brew`) and Debian/Ubuntu (`apt`); on Windows you'd need a manual/scoop poppler for
PDF ingest, or accept the graceful degradation. The plugin also runs **inside the Caldera server process**,
so Windows-native feasibility ultimately inherits from wherever the estate's Caldera server runs; Caldera
core's own OS matrix was not verified in this ask. All of the plugin's own code and deps are
Windows-portable per the evidence above.

## Breakage / issue history

`gh api repos/mitre/mcp/issues?state=all` → 30 items, all closed, 0 open.

- **Maintenance responsiveness is excellent**: bugs filed and fixed within days in late Aug 2026 —
  #35 (CTI banner can't be dismissed) → fixed same day in #38; #29 (Run History phantom RUNNING rows) → #31;
  #30 (workflow page lock-in) → #40. 5 commits since 2026-09-01; ~10 PRs merged in the last week of Aug 2026.
- **Security posture of the MCP SDK** is actively reasoned about: `docs/fastmcp-upgrade-plan.md` (2026-08-30)
  verifies against OSV/GHSA that neither `mcp` 1.29.1 nor `fastmcp` 3.4.7 advisories reach their
  stdio-only deployment (0 affecting, 0 reachable), and `mcp` is pinned `>=1.9,<2` (PR #25).
- **Unresolved report**: issue #19 "Missing parsers and cleanup parameters in create_linux_ability and
  create_windows_ability tools" (filed 2026-05-10, external) was **stale-bot closed 2026-09-10 with no
  merged fix** (PR #20 closed unmerged). So the ability-authoring tools' parser/cleanup gap has no merged
  fix as of this dive. Several other external PRs were also closed unmerged (#13, #14, #17, #18, #22) —
  single-maintainer project, external fixes get declined.
- **CI does not run the tests**: `.github/workflows/python-lint.yml` is flake8 syntax-only
  (`--select=E9,F63,F7`). The repo carries a real 44-file pytest suite (`pytest tests`, per README) that
  CI never executes. Quality signal is the suite's existence, not CI enforcement.
- **Bus factor 1**: `gh api repos/mitre/mcp/contributors` → single contributor `HackedRico` (Ricky Chen),
  96 commits, all of them.

## Independent mentions (exa search, this session)

- Official-but-first-party: Medium post by the Caldera team (2025-11-10) — provenance anchor, describes
  LLM planner / ability factory / RAG-over-STIX and the Magician LLM agent lineage.
- Gitee mirror `mirrors_mitre/MCP`; LinkedIn reposts of the announcement (Nov 2025).
- **Third-party alternatives exist** (relevant to the estate's "attach to existing rpc" framing):
  `cowboy-samurai/caldera-mcp` (PyPI `caldera-mcp` 0.1.2 — a standalone MCP server speaking Caldera's REST
  API from outside), `PSOC-Sam/caldera-mcp-foundry`, `scthornton/secmcp`. Those attach remotely to an
  existing Caldera without touching its tree; `mitre/mcp` is the heavier official in-process option with
  its own Vue UI, DSPy loop, and MLflow observability.

## Score

- Value: **high** — official, active (pushed 2026-09-03), squarely on-lane (agentic ops planning +
  ability generation for a platform the estate already runs), real dependency hygiene (SDK CVE analysis,
  credential-handling guards with tests: `test_set_config_secrets.py`, `test_api_authorization.py`).
- Windows: **native-feasible (static evidence)** — all deps ship win wheels or are pure-python; all spawn
  paths use `sys.executable`; PDF needs a Windows poppler (optional, degrades gracefully). Not installed
  or run during this dive; it must load into an existing Caldera server tree.
- Risks: bus factor 1; no releases/tags (pin a commit); breaking `!` refactors on main; CI lints but
  never runs the test suite; one stale-closed unresolved ability-tool report (#19); plugin spawns its own
  MLflow server on 127.0.0.1:5000 by default (conflict-detection exists, `mlflow.port` overridable in
  `conf/local.yml` — hook.py `_probe_listener`/`_reclaim_port`).

## Corrected ToolFind (returned via submit_result)

- name: mitre/mcp (Caldera MCP plugin)
- repo: https://github.com/mitre/mcp
- what: MITRE's official in-process Caldera plugin (created 2025-10-30, pushed 2026-09-03, Apache-2.0,
  40★) running DSPy ReAct + LiteLLM workflows that author abilities/adversaries and plan+execute
  operations, with optional RAG over STIX CTI and MLflow-run observability; loads INTO the existing
  Caldera tree (no new container) rather than attaching remotely to its REST API. Windows-native
  feasible on static evidence (all deps have win wheels/pure-python; subprocess spawns use
  sys.executable; PDF ingest needs optional poppler); not live-tested. Risks: bus factor 1
  (single maintainer), no releases/tags (pin a commit), CI lints but doesn't run the 44-file test suite,
  and one stale-closed unresolved report on missing ability parsers (#19).
- install: `git clone https://github.com/mitre/mcp.git plugins/mcp` from the Caldera root, then
  `pip install -r plugins/mcp/requirements.txt` + `python -m spacy download en_core_web_lg` into the
  Caldera venv, `cp plugins/mcp/.env.example plugins/mcp/.env`, add `mcp` to `plugins:` in
  `conf/local.yml`, restart Caldera. No pip-installable package, no releases — pin a commit hash.
- windows: native
- value: high