# MCP Servers Catalog

Drug-discovery research stack and the full MCP server inventory on this Windows
host. Source of truth: `~/.claude.json` (`C:\Users\Prekzursil\.claude.json`).

- **Platform:** Windows 11. Paths below are the literal Windows values stored in
  config. POSIX equivalents are noted where relevant (`D:\Program Files\...` -> a
  mounted/installed path on Linux/macOS; `~` = `C:\Users\Prekzursil` on Windows).
- **Config file location:** user-scope MCP servers live in `~/.claude.json` under
  the top-level `"mcpServers"` object. Per-project overrides and the
  enable/disable lists live under `projects.<projectPath>` (`mcpServers`,
  `disabledMcpServers`, `enabledMcpjsonServers`, `disabledMcpjsonServers`).
- **Status legend:** **active** = present in the user-scope `mcpServers` and not
  in the project `disabledMcpServers` list. **disabled (project)** = present in
  config but listed in `projects."C:/Users/Prekzursil".disabledMcpServers`.
- **Env var convention:** `${NAME}` placeholders are resolved from the OS
  environment at launch (Claude Code expands them). They are NOT literal secrets
  in the file.

The 4 research-relevant servers (`tooluniverse`, `rdkit`, `schrodinger`, plus
`gogcli-classroom`) are documented in detail in the "How to connect" section.

---

## Inventory (all servers in ~/.claude.json)

### User scope (`mcpServers`, ~/.claude.json)

| Name | What it does | Status | Transport | Command + args (+ env) |
|------|--------------|--------|-----------|------------------------|
| `tooluniverse` | 2206 biomedical tools (DDI / ADMET / CYP / targets / FDA labels / repurposing / pharmacovigilance). Harvard Zitnik lab, Apache-2.0. | active | stdio | `uvx tooluniverse==1.2.4` · env `PYTHONIOENCODING=utf-8` |
| `rdkit` | 74 cheminformatics tools (tandemai-inc/rdkit-mcp-server, MIT). | active | stdio | `C:\Users\Prekzursil\source\repos\rdkit-mcp-server\.venv\Scripts\python.exe run_server.py --transport stdio` |
| `schrodinger` | Custom 12-tool wrapper over a local Schrodinger 2022-4 suite (structure prep, descriptors, protein prep, grid generation, LigPrep, Glide docking, MM-GBSA, QikProp ADMET). | active | stdio | `C:\Users\Prekzursil\source\repos\schrodinger-mcp\.venv\Scripts\python.exe server.py` · env `SCHRODINGER=D:\Program Files\Schrodinger 2022-4` |
| `insta-mcp` | Instagram private-API tools (node). | active | stdio | `node C:/Users/Prekzursil/source/repos/insta-mcp/dist/index.js` |
| `mcp-funnel` | MCP aggregator/proxy that funnels other MCP servers (`.mcp-funnel.json`). | active | stdio | `cmd /c npx -y mcp-funnel C:/Users/Prekzursil/.mcp-funnel.json` |
| `ralph-orchestrator` | Ralph autonomous-loop orchestrator MCP. | disabled (project) | stdio | `C:\Users\Prekzursil\.cargo\bin\ralph.exe mcp serve` |
| `apify` | Apify actors / web scraping. | disabled (project) | HTTP (url) | url `https://mcp.apify.com/` |
| `binary-ninja-mcp` | Binary Ninja reverse-engineering bridge. | disabled (project) | stdio | `cmd /c npx -y binary-ninja-mcp --host localhost --port 9009` |
| `browserstack` | BrowserStack cloud test automation. | disabled (project) | stdio | `cmd /c npx -y @browserstack/mcp-server@1.2.11` · env `BROWSERSTACK_USERNAME`, `BROWSERSTACK_ACCESS_KEY` |
| `cheatengine` | Cheat Engine bridge (game RE / memory). | disabled (project) | stdio | `...\cheatengine-mcp-bridge\.venv\Scripts\python.exe ...\MCP_Server\mcp_cheatengine.py` |
| `chrome-devtools` | Chrome DevTools protocol driver. | disabled (project) | stdio | `cmd /c npx -y chrome-devtools-mcp@latest` |
| `codacy` | Codacy code-quality. | disabled (project) | stdio | `cmd /c npx -y @codacy/codacy-mcp@latest` · env `CODACY_ACCOUNT_TOKEN`, `CODACY_API_TOKEN` |
| `codecov` | Codecov coverage reports. | disabled (project) | stdio | `cmd /c npx -y @egulatee/mcp-codecov@latest` · env `CODECOV_BASE_URL`, `CODECOV_TOKEN` |
| `context7` | Up-to-date library/API docs (Upstash). | disabled (project) | stdio | `cmd /c npx -y @upstash/context7-mcp` · env `CONTEXT7_API_KEY` |
| `deepsource` | DeepSource code analysis. | disabled (project) | stdio | `node ...\deepsource-mcp-server\deepsource-mcp-wrapper.mjs` · env `DEEPSOURCE_API_KEY` |
| `digitalocean` | DigitalOcean Apps. | disabled (project) | stdio | `cmd /c npx -y @digitalocean/mcp --services apps --transport stdio` · env `DIGITALOCEAN_API_TOKEN` |
| `docker` | Docker control (uvx docker-mcp). | disabled (project) | stdio | `...\.local\bin\uvx.exe docker-mcp` |
| `excel` | Excel spreadsheet read/write. | disabled (project) | stdio | `...\.local\bin\uvx.exe excel-mcp-server stdio` |
| `figma` | Figma design files. | disabled (project) | HTTP (url) | url `https://mcp.figma.com/mcp` |
| `firecrawl` | Firecrawl web crawl/scrape. | disabled (project) | stdio | `cmd /c npx -y firecrawl-mcp@latest` · env `FIRECRAWL_API_KEY` |
| `frida-mcp` | Frida dynamic instrumentation. | disabled (project) | stdio | `...\frida-mcp\.venv\Scripts\frida-mcp.exe` |
| `ghidra-mcp` | Ghidra RE bridge (HTTP backend :8089). | disabled (project) | stdio | `...\ghidra-mcp\.venv\Scripts\python.exe bridge_mcp_ghidra.py --ghidra-server http://127.0.0.1:8089/` |
| `github` | GitHub Copilot MCP. | disabled (project) | HTTP (url) | url `https://api.githubcopilot.com/mcp` |
| `github_cli` | `gh` CLI bridge. | disabled (project) | stdio | `gh-cli-mcp` · env `GITHUB_MCP_PAT`, `GH_TOKEN` |
| `hexstrike-ai` | HexStrike AI offensive-security toolkit. | active | stdio | `...\hexstrike-ai\.venv\Scripts\python.exe hexstrike_mcp_launcher.py` |
| `huggingface` | Hugging Face hub MCP. | disabled (project) | HTTP (url) | url `https://huggingface.co/mcp?login` |
| `ida-pro-mcp` | IDA Pro RE bridge. | active | stdio | `...\ida-pro-mcp\.venv\Scripts\python.exe ...\ida_pro_mcp\server.py` |
| `linear` | Linear issue tracking. | disabled (project) | HTTP (url) | url `https://mcp.linear.app/mcp` |
| `markitdown` | Convert files -> Markdown. | disabled (project) | stdio | `...\.local\bin\markitdown-mcp.exe` |
| `mcp-graphql` | GraphQL endpoint tool. | disabled (project) | stdio | `cmd /c npx mcp-graphql` · env `ENDPOINT=http://localhost:4000/graphql` |
| `meta-tool` | Custom meta-tool MCP (tsx server). | disabled (project) | stdio | `node --import .../tsx/dist/loader.mjs ...\meta-tool\src\server.ts` |
| `notion` | Notion workspace. | disabled (project) | HTTP (url) | url `https://mcp.notion.com/mcp` |
| `pdf-reader` | PDF text extraction. | disabled (project) | stdio | `cmd /c npx -y @sylphx/pdf-reader-mcp` |
| `playwright` | Playwright browser automation. | disabled (project) | stdio | `cmd /c npx -y @playwright/mcp@latest` |
| `postgres` | Postgres (pgEdge MCP in Docker). | disabled (project) | stdio | `docker run -i --rm ghcr.io/pgedge/postgres-mcp:latest` |
| `qlty` | qlty code-quality MCP (node). | disabled (project) | stdio | `node ...\meta-tool\src\qlty_mcp_server.mjs` |
| `repomix` | Repomix repo packing. | disabled (project) | stdio | `cmd /c npx -y repomix --mcp` |
| `scrapegraph` | ScrapeGraph AI scraping. | disabled (project) | stdio | `...\.local\bin\uvx.exe scrapegraph-mcp==1.0.1` · env `SGAI_API_KEY` |
| `semgrep` | Semgrep SAST. | disabled (project) | stdio | `...\.local\bin\semgrep-mcp.exe --semgrep-path ...\semgrep.exe` |
| `sentry` | Sentry error monitoring. | disabled (project) | stdio | `cmd /c npx -y @sentry/mcp-server@latest` · env `SENTRY_ACCESS_TOKEN`, `SENTRY_HOST` |
| `sonarqube` | SonarQube/SonarCloud (Docker). | disabled (project) | stdio | `docker run -i --rm -e SONARQUBE_* docker.io/mcp/sonarqube:latest` · env `SONARQUBE_TOKEN/ORG/URL/IDE_PORT` |
| `tavily` | Tavily web search/extract. | disabled (project) | stdio | `cmd /c npx -y tavily-mcp@0.2.15` · env `TAVILY_API_KEY` |

> Note on "disabled (project)": these are listed in
> `projects."C:/Users/Prekzursil".disabledMcpServers`, so they are switched off
> for work rooted at `C:\Users\Prekzursil`. The entries still exist in user-scope
> `mcpServers` and can be re-enabled by removing them from that list. The disable
> list is part of a deliberate token-reduction harness — do not wipe it.

### Project scope (`projects."C:/Users/Prekzursil".mcpServers`)

| Name | What it does | Status | Transport | Command + args |
|------|--------------|--------|-----------|----------------|
| `codex` | OpenAI Codex CLI as an MCP server (cross-model consult / review). | active (project-only) | stdio | `codex mcp-server` |

### Not currently in config (see note)

| Name | What it does | Status | Transport | Notes |
|------|--------------|--------|-----------|-------|
| `gogcli-classroom` | Google Classroom over `gog.exe` v0.21.0 (gogcli-mcp-classroom). | NOT in `~/.claude.json` and NOT in `claude mcp list` at time of writing | stdio (npm) | Session notes say it was registered this session, but it is absent now. Re-add command in the "How to connect" section. |

---

## How to connect (research-relevant servers)

### 1. `tooluniverse`

- **What:** 2206 biomedical tools. The stdio entrypoint is
  `tooluniverse.smcp_server:run_default_stdio_server`.
- **Install/run:** launched on demand via `uvx tooluniverse==1.2.4` — `uvx`
  (from `uv`) fetches and runs the pinned PyPI package; no manual venv needed.
- **Config (`~/.claude.json` -> `mcpServers.tooluniverse`):**
  ```json
  { "type": "stdio", "command": "uvx",
    "args": ["tooluniverse==1.2.4"],
    "env": { "PYTHONIOENCODING": "utf-8" } }
  ```
- **Auth / scopes:** none — it calls public biomedical APIs (OpenFDA, etc.). No
  API key required for the registered toolset.
- **Why `PYTHONIOENCODING=utf-8`:** Windows defaults to cp1252 on stdio, which
  corrupts non-ASCII tool output over the stdio transport; this forces UTF-8.
- **Cross-platform:** `uvx` must be on PATH. On Windows it resolves to
  `...\.local\bin\uvx.exe`; on POSIX it is `~/.local/bin/uvx` (or wherever `uv`
  is installed). The package and args are identical across OSes.
- **Skills:** ToolUniverse skills are installed at `~/.agents/skills/tooluniverse-*`
  (drug-drug-interaction, admet-prediction, chemical-safety, target-research,
  drug-repurposing, pharmacovigilance, drug-mechanism-research).

### 2. `rdkit`

- **What:** 74 cheminformatics tools (tandemai-inc/rdkit-mcp-server, MIT) at
  `C:\Users\Prekzursil\source\repos\rdkit-mcp-server`.
- **Config (`~/.claude.json` -> `mcpServers.rdkit`):**
  ```json
  { "type": "stdio",
    "command": "C:\\Users\\Prekzursil\\source\\repos\\rdkit-mcp-server\\.venv\\Scripts\\python.exe",
    "args": ["C:\\Users\\Prekzursil\\source\\repos\\rdkit-mcp-server\\run_server.py",
             "--transport", "stdio"],
    "env": {} }
  ```
- **Auth / scopes:** none — local compute only.
- **GOTCHA (transport):** the server **defaults to SSE on :8000**. You MUST pass
  `--transport stdio` (as configured) or Claude Code cannot speak to it.
- **GOTCHA (RDKit version):** upstream pins a dead `rdkit==2025.3.1`. This install
  uses `rdkit 2026.3.3`, installed with `pip install --no-deps .` so the dead pin
  is not re-pulled. If you recreate the venv, repeat that (install rdkit first,
  then `pip install --no-deps .`).
- **Cross-platform:** Windows uses `.venv\Scripts\python.exe`; on POSIX it is
  `.venv/bin/python`. Update both the `command` and the script path. The
  `--transport stdio` flag is identical.

### 3. `schrodinger` (custom-built)

- **What:** a thin, security-conscious wrapper over a local Schrodinger 2022-4
  suite (build 79134) at `C:\Users\Prekzursil\source\repos\schrodinger-mcp`.
  It NEVER imports `schrodinger` in-process; every tool builds an argv list and
  hands it to a single non-tool `_exec()` chokepoint, run WITHOUT a shell.
- **Config (`~/.claude.json` -> `mcpServers.schrodinger`):**
  ```json
  { "type": "stdio",
    "command": "C:\\Users\\Prekzursil\\source\\repos\\schrodinger-mcp\\.venv\\Scripts\\python.exe",
    "args": ["C:\\Users\\Prekzursil\\source\\repos\\schrodinger-mcp\\server.py"],
    "env": { "SCHRODINGER": "D:\\Program Files\\Schrodinger 2022-4" } }
  ```
- **Auth / scopes:** no network auth. The product-driver tools (`prepwizard`,
  `glide_grid`, `ligprep`, `qikprop_admet`, `glide_dock`, `prime_mmgbsa`) consume
  **Schrodinger license tokens** and run synchronously with `-WAIT`. A
  FlexLM/license server (or local license file) must be reachable for those.
- **Security model:**
  - `$SCHRODINGER` (the install root) is the only required config. It defaults to
    `D:\Program Files\Schrodinger 2022-4` if the env var is unset; the config sets
    it explicitly.
  - All subprocess execution is centralized in `_exec()` (the single chokepoint,
    `shell=False`, not exposed as a tool), so untrusted tool params never reach
    `subprocess.run` directly.
  - `_safe_path()` validates every client-supplied path before it can reach an
    argv: rejects empty / flag-like (`-...`) values, normalizes to absolute, and
    optionally enforces existence.
  - `run_schrodinger_python` is an explicit escape hatch that runs arbitrary
    Python inside the Schrodinger interpreter — **local single-user use only.**
- **The 12 tools (exact names + signatures from `server.py`):**

  License-token-free (structure / cheminformatics):
  | Tool | Signature | Purpose |
  |------|-----------|---------|
  | `schrodinger_version` | `() -> str` | Suite version + resolved env (`run -v`). |
  | `backend_info` | `() -> dict` | Schrodinger build + bundled RDKit version + install path (via `_sch_helper.py info`). |
  | `smiles_to_3d` | `(smiles, out_path, title="") -> dict` | SMILES -> 3D `.sdf`/`.mae` via RDKit ETKDGv3 + MMFF (extension picks format). |
  | `molecule_properties` | `(smiles) -> dict` | Drug-likeness panel: formula, MW, logP, HBD/HBA, TPSA, rot-bonds, rings, QED, Lipinski. |
  | `convert_structure` | `(src, dst) -> dict` | Convert `.sdf <-> .mae <-> .pdb` via `schrodinger.structure`. |
  | `run_schrodinger_python` | `(code, timeout_s=300) -> dict` | Escape hatch: arbitrary Python inside the Schrodinger interpreter. |

  Product drivers (consume license tokens; synchronous `-WAIT`):
  | Tool | Signature | Purpose |
  |------|-----------|---------|
  | `prepwizard` | `(input_file, output_mae, ph=7.0, fill_sidechains=True, timeout_s=1800) -> dict` | Protein Preparation Wizard: clean/protonate a raw receptor `.pdb`/`.mae` (add H, bond orders, fill side chains, PROPKA at `ph`) -> prepared `.mae` ready for `glide_grid`. |
  | `glide_grid` | `(receptor_mae, out_grid_zip, center="", ligand_molnum=0, inner_box=10, outer_box=30, timeout_s=1800) -> dict` | Generates the Glide docking grid (`.zip`) from a prepared receptor; box via explicit `center="x,y,z"` OR `ligand_molnum` (1-based co-crystal ligand). Consumes a Glide token. |
  | `ligprep` | `(input_file, output_mae, timeout_s=1200) -> dict` | LigPrep: ionization/tautomer/stereo states `.smi/.sdf/.mae` -> MAE. |
  | `qikprop_admet` | `(structure_file, timeout_s=900) -> dict` | QikProp ADMET/physchem on a 3D structure; returns result CSV path + head. |
  | `glide_dock` | `(grid_file, ligands_mae, precision="SP", timeout_s=3600) -> dict` | Glide docking into a grid (`.zip`) built by `glide_grid`; `precision = HTVS \| SP \| XP`; returns `*_pv.maegz` pose-viewer path. |
  | `prime_mmgbsa` | `(pose_viewer, timeout_s=3600) -> dict` | Prime MM-GBSA binding free-energy (`dG_Bind`) rescoring of docked poses (the `*_pv.maegz` from `glide_dock`); returns result CSV. Consumes a Prime token. |

  Verified working: validated live end-to-end on 2026-06-06 (full `prepwizard` ->
  `glide_grid` -> `ligprep` -> `glide_dock` -> `prime_mmgbsa` pipeline on PDB 3PTB,
  plus `qikprop_admet`); the Python API runs via `run.exe python3` (build 79134).
  See `schrodinger-mcp/VALIDATION.md`.
- **Cross-platform:** the server self-detects `run.exe`/`run` and `<driver>.exe`/
  `<driver>` (`_run()` / `_driver()`), so it works on POSIX once `$SCHRODINGER`
  points at the install root. On Windows the install is on `D:\` (note the space
  in `Schrodinger 2022-4`); on POSIX set `SCHRODINGER` to e.g.
  `/opt/schrodinger2022-4`. Update `command` to `.venv/bin/python` on POSIX.

### 4. `gogcli-classroom`

> **Status note:** at the time this catalog was written, `gogcli-classroom` is
> **not present** in `~/.claude.json` and does **not appear** in `claude mcp list`.
> The session notes record it was authorized and round-trip-verified, so it was
> likely added to a transient/CLI-managed store that is not currently active.
> Re-register it with the command below.

- **What:** Google Classroom access via `gogcli-mcp-classroom` (npm, global) over
  the `gog.exe` CLI v0.21.0 at `C:\Users\Prekzursil\tools\gogcli\gog.exe`.
- **Transport:** stdio (the npm bin `gogcli-mcp-classroom` spawns `gog.exe`).
- **Re-register (the exact command used this session):**
  ```bash
  claude mcp add gogcli-classroom \
    -e GOG_ACCOUNT=prekzursil1993@gmail.com \
    -e GOG_PATH=C:\Users\Prekzursil\tools\gogcli\gog.exe \
    -- gogcli-mcp-classroom
  ```
- **Auth / scopes:** Google OAuth **Desktop** client in the Google Cloud project
  "WebCoder". The account `prekzursil1993@gmail.com` is authorized; the OAuth
  token is stored in the **OS keyring** (not in `~/.claude.json`). Loopback
  auto-capture worked during auth; the `--remote` manual flow failed due to
  browser churn — prefer loopback.
- **Scope limitation:** the authorized account is a **student** account ->
  Classroom **write** tools return **403**. Reads and own-submission operations
  work. Round-trip verified:
  `gog -a prekzursil1993@gmail.com classroom courses list` returned 3 real courses.
- **Cross-platform:** `GOG_PATH` is the Windows binary
  `C:\Users\Prekzursil\tools\gogcli\gog.exe`; on POSIX point it at the
  platform `gog` binary. `GOG_ACCOUNT` and the npm package name are identical.

---

## Quick verification

```bash
# Health-check all registered MCP servers:
claude mcp list

# Inspect one server's resolved config:
claude mcp get schrodinger
```

At time of writing, `tooluniverse`, `rdkit`, and `schrodinger` all report
`✓ Connected`. `gogcli-classroom` is absent — re-add per section 4.
