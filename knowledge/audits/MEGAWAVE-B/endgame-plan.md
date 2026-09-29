# MEGAWAVE-B — Lane B: D2 dead-port band + D4 registry pass + McpHub consolidation endgame

Lane B, read-only (patches PROPOSED, nothing applied). Generated 2026-09-28.
**Machine identity: VERIFIED `DESKTOP-A60S9GP` / user `Prekzursil` (home, NOT the VM)** — probe:
`python megawave-b-probe.py` → `hostname: DESKTOP-A60S9GP`, `username: Prekzursil`.
This matters: the sibling doc `MCP-CLASSIFICATION-2026-09-25.md` ran on VM OFFLOAD-W2025 and its
DELETE-9 verdicts are about the VM's copy of home's config. On home, every path those verdicts
flagged EXISTS (verified below), so nothing here is deletable for path-absence.

Evidence standard: every load-bearing claim is tagged VERIFIED (exact probe+output in §7) or
INFERRED with a band. UNVERIFIED names its settling test.

COVERAGE: §1 registry-vs-live COMPLETE · §2 D2 COMPLETE · §3 D4 COMPLETE · §4 endgame COMPLETE ·
§5 VM parity COMPLETE · §6 patches COMPLETE. Untagged entries are VERIFIED.

---

## 1. Registry-vs-live diff

Registry: `C:/Users/Prekzursil/.agents/agents.json` → `mcp.servers` — **97 entries** (VERIFIED:
probe3 `mcp.servers count: 97`). Plus a root-level `mcpServers` sibling object containing ONLY
`biomni` (a duplicate of `mcp.servers.biomni` — same url `http://127.0.0.1:7870/mcp`, same
enabled=true) — registry-hygiene defect, patch P3.

Liveness: one python-socket pass (probe1, 1.0 s timeout each) over every local port referenced by
the registry — no server was started. Second signal: the Claude session's own MCP-connect results
at session start (mechanically independent probe). Where they agree, the verdict is solid.

### 1a. Full table (port-bearing local entries first)

| server (agents.json) | endpoint | port | TCP | class | second signal |
|---|---|---|---|---|---|
| github-security | http://127.0.0.1:31110/mcp | 31110 | OPEN | live-front 31110-19 | tools surfaced in session |
| cve-mcp | http://127.0.0.1:31111/mcp | 31111 | OPEN | live-front | tools surfaced in session |
| osint | http://127.0.0.1:31112/mcp | 31112 | OPEN | live-front | tools surfaced in session |
| hexstrike-ai | http://127.0.0.1:31113/mcp | 31113 | OPEN | live-front | tools surfaced in session |
| firecrawl | http://127.0.0.1:31114/mcp | 31114 | OPEN | live-front | tools surfaced in session |
| hacktricks | http://127.0.0.1:31115/mcp | 31115 | OPEN | live-front (enabled=false — registered but off) | — |
| metasploit | http://127.0.0.1:31116/mcp | 31116 | CLOSED | live-front band, DEAD (enabled=false, on-demand) | session ECONNREFUSED — 2 signals agree DEAD |
| nuclei | http://127.0.0.1:31117/mcp | 31117 | OPEN | live-front | tools surfaced in session |
| cloud-audit | http://127.0.0.1:31118/mcp | 31118 | OPEN | live-front | tools surfaced in session |
| semgrep | http://127.0.0.1:31119/mcp | 31119 | **CLOSED** | live-front band, DEAD — **enabled=true → registry defect (patch P1)** | no `mcp__semgrep__*` tools in session — consistent |
| github-security-hub / cve-mcp-hub / osint-hub / hexstrike-ai-hub / nuclei-hub / cloud-audit-hub / semgrep-hub | same ports 31110-31119 (hermes targets) | — | as above | live-front duplicates (hub aliases) | — |
| sliver-full | http://127.0.0.1:31101/mcp | 31101 | OPEN | sub-band, **port alive / MCP dead** (enabled=false) | session CONNECT_TIMEOUT — QUARANTINE, never delete |
| biomni | http://127.0.0.1:7870/mcp | 7870 | OPEN | loopback HTTP | session ECONNREFUSED at start → server came up after session start (INFERRED, high) — port now live |
| basic-memory | http://127.0.0.1:18765/mcp | 18765 | OPEN | loopback HTTP (persistent daemon) | memory contract SSOT |
| agent-mail | http://127.0.0.1:18812/mcp/ | 18812 | OPEN | loopback HTTP (persistent daemon) | supervisor task |
| McpHub | sse://127.0.0.1:24680/sse | 24680 | OPEN | loopback SSE hub — the consolidation front | hub children in `.mcphub/config.json` |
| burp | stdio child fronting sse://127.0.0.1:9876 | 9876 | CLOSED | stdio→SSE bridge (on-demand launch recipe) | session ECONNREFUSED — agree DEAD (on-demand) |
| ghidra-mcp (arg) | http://127.0.0.1:8089/ | 8089 | CLOSED | backend-on-demand | expected: GUI/re-harness starts it |
| binary-ninja-mcp (arg) | localhost:9009 | 9009 | CLOSED | backend-on-demand | expected: BN GUI starts it |
| playwright-cdp (arg) | http://127.0.0.1:9222 | 9222 | CLOSED | backend-on-demand | expected: dedicated CDP profile |
| jupyter (env JUPYTER_URL) | http://localhost:8888 | 8888 | CLOSED | backend-on-demand | expected: science Jupyter lab |
| basic-memory stdio bridge (x_cursor) | stdio → :18765 | — | — | stdio bridge | — |

### 1b. http-remote entries (TCP not probed — remote; class = http-remote)

context7 (`mcp.context7.com`), github (`api.githubcopilot.com`), huggingface (`huggingface.co/mcp?login`
— session-level HTTP 401: auth broken, entry NOT dead; see P4 note), linear, notion, exa, deepwiki,
openaiDeveloperDocs, web-search-prime, web-reader, zread (api.z.ai), brightdata, figma. Reachability
from this lane: n/a (no egress probes fired; keep minimal).

### 1c. stdio entries (no port to probe — class = stdio)

binary-ninja-mcp, browserstack, cheatengine, chrome-devtools, claude-code-mcp, codacy, codecov,
deepsource, digitalocean, docker, excel, frida-mcp, github_cli, glm53-space, ida-pro-mcp, linkedin,
markitdown, mcp-graphql, pdf-reader, playwright, postgres, ralph-orchestrator, repomix, scrapegraph,
sentry, sonarqube, tavily, meta-tool, qlty, deepscan, cursor-bridge, arxiv, sci-hub, paper-search,
libgen, annas-archive, pubmed, openalex, crossref, video-agent-kit, cloud-hub, search-hub,
social-hub, tooluniverse, figma-rest, playwright-cdp, playwright-extension, mcp-windbg, zai-lane-a,
breach-intel, open-coscientist-lit-review, biomcp, jupyter, lifesciences, scholarly-access,
biomni-hub, kaggle, hacktricks(stdio tag remnant), mitmproxy, angr, dbx-ai.
Stdio crash-on-start class observed this session (CONNECTION_CLOSED): breach-intel, dbx-ai —
QUARANTINE (diagnose, don't delete).

**Dead-band 314xx / 3138x: ZERO entries — verified across all four config surfaces** (agents.json
read in full; `.claude.json` grep → only regex false-positives `31405` hook-duration and timestamp
`1789623146273`; `.codex/config.toml` → no matches; `.mcp.json` → no matches). The D2 band was a
VM-side 2026-09-19 finding; on home TODAY it is already reconciled. INFERRED (high): no patch for
a 314xx band exists to make on home.

---

## 2. D2 patch — dead-port entries

**Finding:** the literal dead-band (314xx/3138x) does not exist on home (§1). What DOES exist is
one in-band registry defect:

- **P1 — `semgrep` (agents.json, enabled=true → port 31119 CLOSED).** Two signals (TCP closed;
  no session tools). Its front is NOT a config-mapping problem: the hub is fleet-managed —
  VERIFIED `D:/opt/cyberstrike-mcp/cyberstrike-mcp-lib.ps1:78` → `Name='semgrep'; Port=31119;
  Band='Core'` (watched by `watchdog-mcp-estate.ps1`).
  - Option A (preferred, capability-preserving): restart the hub fleet via the cyberstrike-mcp
    lib/watchdog, then keep enabled=true. Zero registry edit.
  - Option B (if the hub must stay down): flip enabled=false + append sticky
    `[2026-09-28: front :31119 down; restart via cyberstrike-mcp-lib.ps1 fleet then re-enable]`.
    Exact edit in §6.
- **metasploit :31116** — enabled=false, on-demand; NOT a defect (backend-on-demand class). No
  patch. The "live equivalent front" for metasploit is the same cyberstrike-mcp hub pattern; the
  lib's Core band owns the start path.
- **sliver-full :31101** — port OPEN but MCP handshake CONNECT_TIMEOUT (2 signals). QUARANTINE —
  do not delete on a snapshot; diagnose the sliver MCP service separately.

---

## 3. D4 — documentation pass

Reference doc: `C:/Users/Prekzursil/.agents/knowledge/audits/MCP-CLASSIFICATION-2026-09-25.md`
(VM-side, 47 labels: 9 DELETE / 22 KEEP / 16 QUARANTINE + sci-hub note).

**3a. Servers with NO row in the doc (59 + 1 note-only):**
annas-archive, arxiv, basic-memory, biomni-hub, binary-ninja-mcp, browserstack, brightdata, burp,
chrome-devtools, cloud-audit-hub, cloud-hub, codecov, cve-mcp-hub, context7, crossref, deepscan,
deepsource, deepwiki, digitalocean, exa, excel, figma, figma-rest, github-security-hub,
glm53-space, hacktricks, hexstrike-ai-hub, jupyter, kaggle, libgen, lifesciences, linear, linkedin,
markitdown, mcp-graphql, mcp-windbg, meta-tool, metasploit, notion, nuclei-hub, openaiDeveloperDocs,
openalex, osint-hub, pdf-reader, playwright, playwright-cdp, playwright-extension, pubmed, qlty,
ralph-orchestrator, repomix, scrapegraph, search-hub, semgrep-hub, sentry, sliver-full, social-hub,
tavily, tooluniverse, video-agent-kit — plus **sci-hub** (note-only: standing owner quarantine rule,
not a classification row).
(Caveat: the doc's population was "the 47 unreachable" — most of these 59 were reachable/other
classes and out of its scope. This row is a coverage statement, not an accusation. INFERRED: a
D4 documentation pass should add at least the -hub aliases, the 31101-31119 on-demand trio, and
the hub trio cloud/search/social-hub.)

**3b. Security-cluster enabled-state (agents.json, VERIFIED):**

| server | enabled | transport/front | live? |
|---|---|---|---|
| hexstrike-ai | true (+`-hub` hermes true) | http :31113 | OPEN |
| nuclei | true (+`-hub` true) | http :31117 | OPEN |
| metasploit | false | http :31116 | CLOSED (on-demand) |
| sliver-full | false | http :31101 | port OPEN, MCP dead (CONNECT_TIMEOUT) |
| mitmproxy | false (parked-stdio-use-mcphub) | stdio | not started |
| frida-mcp | false (parked) | stdio | not started |
| cheatengine | false (parked; impl in toolchain `tools/mcp/cheatengine-mcp-bridge`) | stdio | not started |

---

## 4. ENDGAME PLAN — the "9+codacy" keep-list

**McpHub-fronting shape (all 10): DIRECT CHILD of the McpHub process** — every one of the 10 is
registered as a stdio child in `C:/Users/Prekzursil/.mcphub/config.json` (mode `discover`, idle
300 s, health autoRestart) and fronted to ALL clients as the single SSE endpoint
`http://127.0.0.1:24680/sse` (TCP OPEN; `McpHub` entry enabled=true in agents.json and
.claude.json). VERIFIED per-server child blocks at: codex :401, github_cli :109, ocr-suite :375,
openmm-md :381, paper-search :526, perplexity :387, postgres :149, rdkit :241, sonarqube :198,
codacy :38. **None of the 10 uses the per-server mcp-http-host/mcp-proxy front** — that machinery
(`tools/mcp/mcp-http-host` PR #159 + `tools/mcp/mcp-host-supervisor` + `docs/mcp-consolidation-plan.md`)
is the estate's ALTERNATIVE endgame shape. Relationship: McpHub = one process fronting many
children (the sticky doctrine since 2026-09-24); mcp-http-host = one bridge per server (the
Tier-A consolidation plan). They are complementary layers, not rivals; §6 keeps McpHub as the
front of record per the owner directive and the sticky notes.

Per-server plan (impl paths VERIFIED existing on home; entry-file checks in §7):

| server | current impl location | McpHub shape today | relocation target (`tools/mcp/<name>/`) | what retires |
|---|---|---|---|---|
| codex | npm global `codex` CLI → `cmd /c codex mcp-server` (`C:\Users\Prekzursil\AppData\Roaming\npm\codex.CMD`; `which codex` VERIFIED) | direct child (.mcphub :401) | N/A — external npm package, no source to relocate. Add registry entry (P2) for sync-managed parity; the VM's "entrypoint absent" verdict does NOT apply here | nothing (this IS the Layer-1 rail) |
| github_cli | npm global `gh-cli-mcp` (`…\npm\gh-cli-mcp.CMD`; which VERIFIED) | direct child (:109) | N/A — external npm | nothing |
| ocr-suite | `D:/mcp-servers/abbyy-finereader-ocr-mcp/` (`index.py` + `.venv` VERIFIED) | direct child (:375) | `tools/mcp/ocr-suite/` — copy tree, repoint .mcphub + new agents.json entry at toolchain copy, validate, then move original to trash | `D:/mcp-servers/abbyy-finereader-ocr-mcp` (after validation) |
| openmm-md | code ALREADY in toolchain: `tools/mcp/openmm-md-mcp/` (server.py, omm_pipeline.py, environment.yml, smoke_test.py VERIFIED) + runtime env `D:/micromamba/envs/openmm-md/python.exe` (VERIFIED) | direct child (:381) — but points at `source/repos/openmm-md-mcp/server.py`, NOT the toolchain copy | DONE for code; P2 registers the TOOLCHAIN path. Runtime env stays in micromamba (document; 8-12 GB env, do not move — INFERRED high) | `C:/Users/Prekzursil/source/repos/openmm-md-mcp` copy (after .mcphub repoint + validation) |
| paper-search | `D:/ReverseTools/mcp/paper-search-mcp/` (venv exe VERIFIED) | direct child (:526) | `tools/mcp/paper-search-mcp/` (consolidation-plan Tier A: share-now, stateless) | `D:/ReverseTools/mcp/paper-search-mcp` (after relocation+validation) |
| perplexity | `D:/ReverseTools/mcp/perplexity-web-mcp/` (pwm-mcp.exe VERIFIED) | direct child (:387) | `tools/mcp/perplexity-web-mcp/` | `D:/ReverseTools/mcp/perplexity-web-mcp` (after) |
| postgres | docker image `ghcr.io/pgedge/postgres-mcp:latest` (docker.exe VERIFIED on PATH; image presence UNVERIFIED — settling test `docker images`, not run to avoid waking Docker Desktop) | direct child (:149) | N/A — image, not source. Keep parked; on-demand start | nothing |
| rdkit | `C:/Users/Prekzursil/source/repos/rdkit-mcp-server/` (run_server.py AND rdkit_mcp_launch.py + .venv all VERIFIED) | direct child (:241, run_server.py --transport stdio). census 2026-07-24: supports streamable-http and ran as duplicate shared service (Tier D) | `tools/mcp/rdkit-mcp-server/` | `source/repos/rdkit-mcp-server` copy (after) |
| sonarqube | docker image `docker.io/mcp/sonarqube:latest` (presence UNVERIFIED, same settling test) | direct child (:198) | N/A — image | nothing |
| codacy | npm `@codacy/codacy-mcp` | direct child (:38) — **UNPINNED `@latest`** vs agents.json pin 0.6.24 (drift → P4) | N/A — external npm | nothing |

**Retire-list summary (after validation; move-to-trash, never delete — owner file rule):**
`D:/mcp-servers/abbyy-finereader-ocr-mcp`, `D:/ReverseTools/mcp/paper-search-mcp`,
`D:/ReverseTools/mcp/perplexity-web-mcp`, `C:/Users/Prekzursil/source/repos/openmm-md-mcp`,
`C:/Users/Prekzursil/source/repos/rdkit-mcp-server`. Plus registry-shape retirements (not rows):
per-client stdio consumption of the parked entries — rows STAY with sticky
`parked-stdio-use-mcphub` (doctrine: keep enabled=false, consume via :24680). Root
`mcpServers.biomni` duplicate retires now (P3).

---

## 5. VM-parity gaps (what the VM registry has that home lacks, for this set)

Source: MCP-CLASSIFICATION-2026-09-25.md (VM-side census, 3 days old — INFERRED high that it
still holds; this wave has not written the VM). The VM's agents.json carries **5 keep-list entries
home's agents.json lacks: `codex`, `ocr-suite`, `openmm-md`, `perplexity`, `rdkit`** (home has
github_cli, paper-search, postgres, sonarqube, codacy — 5 of 10). The mirror-image is the point
of the classification doc: on the VM those 5 carry home-style paths that can never run there
(its "not dead servers — home's config in the VM's file" finding, VERIFIED as a document).
Resolving parity per the owner directive means: home ADDS the 5 (P2, pointing at VERIFIED home
paths); the VM DELETES its path-broken copies (that machine's D2/D4 action — out of this lane's
write scope). After both, the two registries agree on the set while each carries only runnable
paths. Reverse-direction check (home has / VM lacks): none found for this set — the doc's 47
labels minus these 10 are RE/research stack, deliberately VM-specialised per the DOCTRINE LOCK.

---

## 6. needsMainLoop — exact patches to apply (LANE B APPLIES NOTHING)

### P1 — agents.json `semgrep`: flip enabled (or start the hub — owner choice)
Option B edit (only if the hub stays down):
```diff
--- a/C:/Users/Prekzursil/.agents/agents.json  (mcp.servers.semgrep)
+++ b
@@
-      "semgrep": {
-        ...
-        "enabled": true,
+      "semgrep": {
+        ...
+        "enabled": false,
```
plus append to `description`: `[2026-09-28: front :31119 down (TCP closed, no session tools);
restart via D:/opt/cyberstrike-mcp/cyberstrike-mcp-lib.ps1 Core band then re-enable]`.
Preferred alternative: NO registry edit — restart the hub fleet (cyberstrike-mcp lib), re-probe
:31119, keep enabled=true.

### P2 — agents.json: ADD the 5 missing keep-list entries (all enabled=false, parked-stdio shape)
Insert into `mcp.servers` (keys alphabetical position; shapes mirror the existing parked entries):

```json
"codex": {
  "label": "codex",
  "description": "Official OpenAI codex mcp-server (Layer-1 cross-vendor rail). Impl: npm global codex CLI. [STICKY 2026-09-28: consume via McpHub SSE :24680 (child .mcphub/config.json:401); enabled=false in per-client registries]",
  "targets": ["codex", "claude"],
  "enabled": false,
  "transport": "stdio",
  "command": "cmd",
  "args": ["/c", "codex", "mcp-server"],
  "credentialNames": [],
  "tags": ["approved", "shared", "local", "stdio", "parked-stdio-use-mcphub", "multi-client-hub"]
},
"ocr-suite": {
  "label": "ocr-suite",
  "description": "ABBYY FineReader OCR MCP. Impl: D:/mcp-servers/abbyy-finereader-ocr-mcp (relocation target tools/mcp/ocr-suite/). [STICKY 2026-09-28: consume via McpHub SSE :24680 (child .mcphub/config.json:375); enabled=false]",
  "targets": ["claude"],
  "enabled": false,
  "transport": "stdio",
  "command": "D:\\mcp-servers\\abbyy-finereader-ocr-mcp\\.venv\\Scripts\\python.exe",
  "args": ["D:\\mcp-servers\\abbyy-finereader-ocr-mcp\\index.py"],
  "credentialNames": [],
  "tags": ["approved", "local", "stdio", "parked-stdio-use-mcphub", "multi-client-hub"]
},
"openmm-md": {
  "label": "openmm-md",
  "description": "OpenMM molecular-dynamics MCP. Code CANONICAL at agent-skills-toolchain tools/mcp/openmm-md-mcp; runtime env D:/micromamba/envs/openmm-md. [STICKY 2026-09-28: consume via McpHub SSE :24680 (child .mcphub/config.json:381); enabled=false]",
  "targets": ["claude"],
  "enabled": false,
  "transport": "stdio",
  "command": "D:\\micromamba\\envs\\openmm-md\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\source\\agent-skills-toolchain\\tools\\mcp\\openmm-md-mcp\\server.py"],
  "credentialNames": [],
  "tags": ["approved", "local", "stdio", "parked-stdio-use-mcphub", "multi-client-hub", "science"]
},
"perplexity": {
  "label": "perplexity",
  "description": "Perplexity web MCP (pwm-mcp). Impl: D:/ReverseTools/mcp/perplexity-web-mcp (relocation target tools/mcp/perplexity-web-mcp/). [STICKY 2026-09-28: consume via McpHub SSE :24680 (child .mcphub/config.json:387); enabled=false]",
  "targets": ["claude"],
  "enabled": false,
  "transport": "stdio",
  "command": "D:\\ReverseTools\\mcp\\perplexity-web-mcp\\.venv\\Scripts\\pwm-mcp.exe",
  "args": [],
  "credentialNames": [],
  "tags": ["approved", "local", "stdio", "parked-stdio-use-mcphub", "multi-client-hub"]
},
"rdkit": {
  "label": "rdkit",
  "description": "RDKit cheminformatics MCP (74 tools, MIT). Impl: source/repos/rdkit-mcp-server (relocation target tools/mcp/rdkit-mcp-server/); supports stdio + streamable-http. Entry-file form matches the live .mcphub child (run_server.py) — see P4 drift note. [STICKY 2026-09-28: consume via McpHub SSE :24680 (child .mcphub/config.json:241); enabled=false]",
  "targets": ["claude"],
  "enabled": false,
  "transport": "stdio",
  "command": "C:\\Users\\Prekzursil\\source\\repos\\rdkit-mcp-server\\.venv\\Scripts\\python.exe",
  "args": ["C:\\Users\\Prekzursil\\source\\repos\\rdkit-mcp-server\\run_server.py", "--transport", "stdio"],
  "credentialNames": [],
  "tags": ["approved", "local", "stdio", "parked-stdio-use-mcphub", "multi-client-hub", "science"]
}
```

### P3 — agents.json: remove the root `mcpServers.biomni` duplicate
```diff
--- a/C:/Users/Prekzursil/.agents/agents.json (bottom of file)
+++ b
@@
-  "mcpServers": {
-    "biomni": { ... identical to mcp.servers.biomni ... }
-  }
```
`mcp.servers.biomni` stays (it is the kept entry; url/enabled identical — VERIFIED probe3:
`root mcpServers keys: ['biomni']`).

### P4 — drift flags (separate reconcile, NOT in this patch set)
1. `.mcphub/config.json:38` codacy `@codacy/codacy-mcp@latest` → pin `@0.6.24` (match agents.json).
2. rdkit entry-file drift: `.mcphub` uses `run_server.py`; `tools/mcp/canonical-mcp-servers.json`
   uses `rdkit_mcp_launch.py`. Both files exist; pick one form and reconcile both surfaces.
3. `tools/mcp/mcp-host-supervisor` guardrails reject ports 8765/8812 as "live" — those are the
   OLD basic-memory/agent-mail ports (now 18765/18812); update the reject-list before any
   supervisor fleet.json enables those ports.
4. huggingface entry: session-level HTTP 401 with `headers.Authorization: ${HUGGINGFACE_TOKEN}` —
   the endpoint rejects a raw-token header (needs `Bearer` prefix); auth defect, NOT a dead server.
   Owner decides; NEVER-ROTATE applies (no token change proposed).

### Sequencing for main loop
1. Apply P1 (option B) + P3 in one agents.json edit (registry-validate after).
2. Apply P2 (adds only — no existing row touched except none).
3. Run `sync_shared_state.ps1` (registry is the SSOT; merges to Codex/Claude/Cursor surfaces).
4. P4 items as separate scoped commits. Relocations (§4) are owner-gated moves — NOT in this
   patch set; each needs copy → repoint .mcphub → validate (`initialize` + `tools/list` through
   :24680) → trash original.

---

## 7. Evidence log (VERIFIED probes + exact outputs)

1. Machine identity: `python megawave-b-probe.py` → `hostname: DESKTOP-A60S9GP`,
   `username: Prekzursil`, `userprofile: C:\Users\Prekzursil`.
2. TCP pass (same probe, 2026-09-28): OPEN 7870/18765/18812/24680/31101/31110/31111/31112/31113/
   31114/31115/31117/31118; CLOSED 8089/8888/9009/9222/9876/31116/31119. No server started.
3. PATH lookups: `gh-cli-mcp → …\npm\gh-cli-mcp.CMD`, `codex → …\npm\codex.CMD`,
   `docker → C:\Program Files\Docker\Docker\...\docker.EXE`, plus npx/uvx/uv/node/python all found.
4. Impl existence: ALL 11 entry paths EXIST (probe3 full table — paper-search exe, perplexity exe,
   ocr index.py+.venv, openmm server.py+env python, rdkit run_server.py+rdkit_mcp_launch.py+.venv,
   codex.CMD, gh-cli-mcp.CMD).
5. Registry counts: `mcp.servers count: 97`; `root mcpServers keys: ['biomni']`; keep-list
   presence codex ABSENT / github_cli PRESENT enabled=True / ocr-suite ABSENT / openmm-md ABSENT /
   paper-search PRESENT enabled=False / perplexity ABSENT / postgres PRESENT enabled=False /
   rdkit ABSENT / sonarqube PRESENT enabled=False / codacy PRESENT enabled=False (probe3).
6. `.claude.json` mcpServers: 30 servers, NONE of the keep-list present (probe2; full name list
   captured). McpHub present+enabled there.
7. Dead-band grep: `.claude.json` pattern `314[0-9][0-9]|3138[0-9]` → 2 false positives
   (31405 hook-duration; substring of timestamp 1789623146273); `.codex/config.toml` → none;
   `.mcp.json` → none; agents.json full read → none.
8. `.mcphub/config.json` read in full: all 10 keep-list children present at the cited line
   numbers; mode `discover`; `codacy` unpinned @latest; `rdkit` uses run_server.py.
9. `tools/mcp/` listing: 29 entries incl. openmm-md-mcp, hexstrike-ai, hacktricks-mcp-server,
   cheatengine-mcp-bridge, mcp-http-host, mcp-host-supervisor, canonical-mcp-servers.json.
10. `D:/ReverseTools/mcp` (5 impls), `D:/mcp-servers` (1), `C:/Users/Prekzursil/source/repos`
    (14, incl. openmm-md-mcp + rdkit-mcp-server).
11. `grep -n "31119" D:/opt/cyberstrike-mcp/cyberstrike-mcp-lib.ps1` → `78: Name='semgrep';
    Port=31119; Band='Core'` (watchdog-mcp-estate.ps1 also matches 31119).
12. Session-level second signals (Claude session start, this session): ECONNREFUSED biomni/burp/
    metasploit/sliver; CONNECTION_CLOSED breach-intel/dbx-ai; CONNECT_TIMEOUT sliver-full;
    HTTP 401 huggingface.
13. tools/mcp/openmm-md-mcp contents: .gitignore LICENSE README.md environment.yml omm_pipeline.py
    server.py skill smoke_test.py (probe3).

**UNVERIFIED (named settling tests):** docker image presence (`docker images`);
`mcp-proxy`/McpHub per-host commit cost (consolidation-plan §3a open question); VM current state
(3-day-old document; probe over tailnet before acting on the VM).
