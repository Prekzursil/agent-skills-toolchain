---
title: dive-bloodhound-mcp--the--13-composite-tools--MCP-from-the-ask-
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-bloodhound-mcp-the-13-composite-tools-mcp-from-the-ask
---

# Deep-dive: bloodhound_mcp (the "13 composite tools" MCP from the ask)

Candidate lane: ad-entra-paths. Dive date: 2026-09-29.
Repo: https://github.com/mwnickerson/bloodhound_mcp
Local clone for inspection: `out/research/_bhmcp` (shallow, depth 50).

## Verdict in one line

REAL, ACTIVE, and the exact MCP named in the ask. Every quantitative claim in the
candidate (13 tools, 10 resources, SpecterOps authorship, 2025-06-04 blog) verified
against code and primary sources. Two corrections: it is REST-only (no direct Neo4j
client), and it is not on PyPI — install is `uvx --from git+...`.

## 1. Repo metadata — `gh api repos/mwnickerson/bloodhound_mcp` (ran it)

```json
{"stars":136,"forks":28,"open_issues":0,"license":"GPL-3.0","language":"Python",
 "created_at":"2025-03-22T18:37:54Z","pushed_at":"2026-08-19T03:57:09Z",
 "archived":false,"disabled":false,"default_branch":"master",
 "description":"A Model Context Protocol (MCP) server to converse with data in Bloodhound"}
```

- 136 stars / 28 forks — modest but healthy for a niche offensive tool.
- Last push 2026-08-19 (~6 weeks before this dive) — NOT dead.
- 0 open issues AND 0 open PRs (the `open_issues` counter sums both).
- No GitHub releases: `gh api repos/.../releases` returned `[]` (empty output).

## 2. The "13 tools + 10 resources" claim — VERIFIED at three levels

1. **README** (`out/research/_bhmcp/README.md`):
   - Line 15: "13 composite MCP tools, 10 reference resources, and a system prompt".
   - Lines 21–35: tool table lists exactly the 13 from the ask: `domain_info`,
     `user_info`, `group_info`, `computer_info`, `ou_info`, `gpo_info`,
     `graph_analysis`, `adcs_info`, `cypher_query`, `data_quality`,
     `asset_groups`, `custom_nodes`, `file_upload`.
   - Lines 42–52: exactly 10 resources — `bloodhound://cypher/reference`,
     `cypher/offensive-queries` (the "offensive Cypher templates"),
     `guides/ad`, `adcs`, `azure` + their `-methodology` variants (the
     "AD/Azure/ADCS methodology"), `opengraph/guide`, `opengraph/examples`.
2. **Code** (this session, on the clone):
   - `grep -c "@mcp.tool" main.py` → **13**
   - `grep -c "@mcp.resource" main.py` → **10** (URIs at main.py:1375…:2246 match the table)
   - Plus one prompt (`bloodhound_assistant`, main.py:100).
3. **Ran it**: see §5 — the installed package's traceback paths
   (`...site-packages/lib/bloodhound_api.py`) show the same layout shipped from git.

## 3. Authorship / independent mentions — VERIFIED (exa + specterops.io)

Exa search (`api.exa.ai/search`, key from env, this session) returned:

- **Blog (the one the ask cited)**: "Chatting with Your Attack Paths: An MCP for
  BloodHound" — https://specterops.io/blog/2025/06/04/chatting-with-your-attack-paths-an-mcp-for-bloodhound/
  — published **Jun 4, 2025**, author **Matthew Nickerson, Consultant at
  SpecterOps** (Adversary Simulation; Director of Workshops at Red Team Village).
  Fetched and read via WebFetch this session. The claim "by Matthew Nickerson of
  SpecterOps (blog 2025-06-04)" is exactly right.
- **SpecterOps lists it as an official open-source tool**:
  https://specterops.io/open-source-tools/bloodhound-mcp/ — alongside BloodHound
  CE, Jailbreaker, Nemesis, Ghostwriter. (Fetched; the page is undated.)
- **Follow-up post**: "BloodHound MCP, One Year Later: What I Learned About MCPs,
  Models, and Context" — https://specterops.io/blog/2026/06/18/... (2026-06-18) —
  evidence of a maintained, reflected-upon project. Not fetched in full this session.
- Third-party MCP directories list it: mcpservers.org, glama.ai (2 pages),
  procursorrules.com.

## 4. Packaging, REAL install, Windows feasibility

### Packaging files that exist / don't exist
- Exists: `pyproject.toml` (setuptools backend), `uv.lock`, `main.py`, `lib/`,
  `tests/` (6 test files incl. `test_integration.py`), `examples/`.
- Does NOT exist: `setup.py`, `package.json`, `Dockerfile`, GitHub release assets
  (`find` for Dockerfile/package.json/setup.py → 0 hits; releases API → empty).
- `pyproject.toml`: name `bloodhound-mcp`, version 0.1.0, `requires-python >=3.11`,
  deps pinned **mcp==1.9.4, python-dotenv==1.1.1, requests==2.32.4**; console
  script `bloodhound-mcp = "main:main"`.

### Not on PyPI
- `curl -s -o /dev/null -w "%{http_code}" https://pypi.org/pypi/bloodhound-mcp/json`
  → **404**. (A `/project/` URL returns 200 but serves a Fastly challenge page —
  content inspection showed no project data; the JSON API 404 is authoritative.)

### REAL install command (README.md:79–97)
```bash
export BLOODHOUND_DOMAIN=... BLOODHOUND_TOKEN_ID=... BLOODHOUND_TOKEN_KEY=...
uvx --from git+https://github.com/mwnickerson/bloodhound_mcp bloodhound-mcp
# dev: git clone … && uv sync
```
Needs Python 3.11+ and uv. No pip/PyPI path, no Docker path. Note the
`bloodhound-mcp` console entry point itself was added 2026-08-17
(commit 7a13fe0, PR #25 "Add installable console entry point") — before that,
`uvx --from git+... python main.py` style invocation was needed.

### Windows-native feasibility — TESTED HERE, PASSES
On this Windows VM (uv 0.12.20 at `C:\Python314\Scripts\uv.exe`, system Python
3.14.6), I ran the exact README command with dummy creds pointed at a dead port:

```
BLOODHOUND_DOMAIN=127.0.0.1 BLOODHOUND_TOKEN_ID=dummy BLOODHOUND_TOKEN_KEY=dummy \
BLOODHOUND_PORT=9 BLOODHOUND_SCHEME=http \
uvx --from git+https://github.com/mwnickerson/bloodhound_mcp bloodhound-mcp
```

Result: uvx cloned the repo, resolved and installed the pinned deps, built the
package, found the entry point, and launched the server — which then performed the
documented startup credential preflight (README.md:107–110) and exited with a
rich-formatted `lib.bloodhoundApi.BloodhoundConnectionError: Failed to connect to
BloodHound API: ... 127.0.0.1:9 ... [WinError 10061] ... actively refused it`,
traceback running through `lib/bloodhound_api.py:542 validate_credentials →
/api/v2/self`. (The `EXIT=0` in my transcript is `tail`'s status in the pipe, not
the server's; the traceback is the observable outcome.) That is end-to-end proof of
**native Windows install + launch** with zero WSL/Docker. Dependency Windows
support is proven empirically by the same run: mcp==1.9.4, requests==2.32.4,
python-dotenv==1.1.1 all installed and imported on win32.

## 5. Correction: "BloodHound CE REST + Neo4j" is really REST-only

- Every call in `lib/bloodhound_api.py` hits `/api/v2/*` REST endpoints
  (`/api/v2/self`, `/api/v2/available-domains`, `/api/v2/search`,
  `/api/v2/file-upload/...` — grep output this session, lines 370–621).
- `grep -n "neo4j\|bolt://" lib/bloodhound_api.py` → no matches; no neo4j driver
  in `pyproject.toml` deps. Cypher queries execute server-side against Neo4j via
  BloodHound CE's cypher REST endpoint.
- README.md:315 roadmap item "Direct Neo4j access mode (bypass REST API…)" is
  unchecked — i.e. NOT implemented. The claim's "+ Neo4j" should read "via
  BloodHound CE REST (which fronts Neo4j)".

## 6. Issues / breakage — clean

`gh api "repos/mwnickerson/bloodhound_mcp/issues?state=all&per_page=50"` → 25
items, ALL closed; only two are actual issues (#14 "look into … SSE supported MCP
service", 2025-07-09, closed; the rest are PRs). No open breakage, no unmerged
fixes rotting. Recent history is itself maintenance against upstream BloodHound CE
releases: "audit BloodHound edge schema for CE 9.1.0" (2026-07-22), "validate
BloodHound credentials at startup" (2026-08-12), "add console entry point"
(2026-08-18). Commit cadence runs 2025-03-24 → 2026-08-18.

## 7. Caveats for the estate

- Requires a running BloodHound CE (or Enterprise) instance with data loaded, plus
  an API token (Token ID + Key). It is the analysis/upload layer, not a collector —
  though `file_upload` (incl. `upload_bytes` base64 path, README.md:254–263) lets
  an agent push SharpHound/AzureHound ZIPs from memory without touching disk.
- Read/write to the graph is whatever the token allows; README.md:280–293 warns AD
  data goes to the LLM provider — use a local-LLM bridge or lab data; the estate is
  single-owner so this is an accepted-risk call, but it is documented.
- `mcp==1.9.4` is an older pin of the MCP SDK (current SDK line is well past it);
  works fine (proven above) but the pin means updates flow only via repo commits.
- GPL-3.0 — fine for internal use, relevant if anything is ever redistributed.
- BloodHound-version coupling: `custom_nodes` extension APIs need CE 8.0+/9.0+
  (README.md:269–276); older CE instances get the legacy subset.

## 8. Scoring

- windows: **native** (proven by running the real install command on this VM).
- value: **high** — it is the exact tool the ask named; verified active, verified
  inventory, SpecterOps-adopted, and it closes a real gap: natural-language +
  structured attack-path/ADCS/Azure analysis over BloodHound CE with in-band
  collection upload, from the same agent session.