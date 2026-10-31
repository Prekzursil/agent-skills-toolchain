---
title: dive-SquidC5
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-squid-c5
---

# Deep-dive: SquidC5 (SquidSec/SquidC5) — "c2-agentic" lane

Date: 2026-09-29. All checks below were run during this ask. Repo cloned at commit
`134e405cc115f3986595d24856e6945a13b9c4f7` (2026-09-25) — same SHA as the latest release
`v0.1.319-134e405`.

Verdict up front: **REAL and ALIVE, not fake, not dead.** Claim is substantially
accurate; Windows-native feasibility **proven on this VM** (venv install + boot + release
exe boot + full pytest). One claim element (live Ollama `qwen3:4b` pairing) is verified in
code only — Ollama is not installed on this VM, so it could not be exercised end-to-end.
Value: **high**, with a single-maintainer risk.

---

## 1. Repo metadata (ask item: `gh api repos/<owner>/<repo>`)

Command: `gh api repos/SquidSec/SquidC5 --jq '{...}'` →

```
{"archived":false,"created_at":"2026-07-16T20:02:06Z","default_branch":"master",
 "description":"Security-first AI-native C5 teamserver ... for authorized red team & pentest. Built by SquidSec.",
 "forks":5,"full_name":"SquidSec/SquidC5",
 "homepage":"https://squidoffense.com/","language":"Python",
 "license":{"key":"mit","name":"MIT License","spdx_id":"MIT"},
 "open_issues":0,"pushed_at":"2026-09-25T22:44:29Z","size":2644,"stars":57,
 "topics":["ai","c2","c5","fastapi","mcp","penetration-testing","red-team","security"],
 "updated_at":"2026-09-28T15:39:25Z"}
```

- Stars 57, forks 5, open_issues **0**, MIT, Python, **not archived**.
- 305 commits (`Link: <...&page=305>` header on `GET /commits?per_page=1`), latest commit
  2026-09-25T22:36:04Z.
- 128 PRs: `gh api "search/issues?q=repo:SquidSec/SquidC5+is:pr"` → `{"total_count":128}`.
  Author split (`GET /pulls?state=all`): `{"DotNetRussell":99,"dependabot[bot]":1}` —
  effectively **one maintainer** (bus-factor 1).
- Contributors API: single row `{"login":"DotNetRussell","contributions":125}`.
- **30 releases**; latest `v0.1.319-134e405` published 2026-09-25T22:44:30Z with assets
  `README.txt, sbom.cdx.json, sc5-linux-x64, sc5-windows-x64.exe, SHA256SUMS.txt,
  squidc5-linux-x64, squidc5-windows-x64.exe` (README also promises linux-arm64 + CI-only
  `sc5beacon-*` agent builds; the release listing above shows the latest release does not
  attach arm64 server binaries — CI artifacts do).
- CI: last master run `{"name":"CI","conclusion":"success","created_at":"2026-09-25T22:36:07Z"}`.

## 2. README + packaging (ask item)

Files read: `README.md` (219 lines), `pyproject.toml`, `requirements.txt`,
`requirements-dev.txt`, `Dockerfile`, `docker-compose.yml`, `.env.example`,
`CHANGELOG.md`, `docs/` index (10 files), `web/` (9 files), `tests/` (72 files) — tree
via `gh api repos/.../git/trees/master?recursive=1` → 247 blobs total.

- **pyproject.toml**: `name = "squidc5"`, `version = "0.1.0"`, `requires-python = ">=3.11"`,
  entry points `squidc5 = "squidc5.main:cli"`, `sc5 = "squidc5.cli:main"` (pyproject.toml:57-59).
  Deps (pyproject.toml:22-34): fastapi, uvicorn[standard], pydantic, pydantic-settings,
  httpx, aiosqlite, python-multipart, cryptography, **mcp>=1.0.0**, sse-starlette, orjson.
  Classifiers say `Development Status :: 3 - Alpha` (pyproject.toml:14) — honest alpha.
- **Windows support of deps**: every dep ships wheels for Windows; proven empirically (§4).
  The Go beacon (agents/sc5beacon/go.mod) needs only gorilla/websocket + golang.org/x/crypto
  — cross-compiles to windows/amd64 in CI (`.github/workflows/ci.yml:78`
  `GOOS=windows GOARCH=amd64 go build ...`).
- **Docker is optional**: README:69-76 gives the Docker lab quick start, but README:78-85
  gives a plain venv quick start (`pip install -r requirements-dev.txt && pip install -e .`
  then `squidc5`) and README:87-107 the prebuilt-binary path. The Dockerfile
  (python:3.12-slim) and docker-compose.yml exist but nothing requires them. The claim
  "most Docker-free agentic C2" holds: Docker-free install is a first-class path and works.
- **Config surface** (.env.example:14-37): `SQUIDC5_MCP_ENABLED=false` (default OFF),
  `SQUIDC5_LOCAL_LLM_ENABLED` (opt-in Ollama), `SQUIDC5_LOCAL_LLM_BASE_URL
  =http://127.0.0.1:11434/v1`, `SQUIDC5_LOCAL_LLM_MODEL=llama3.2` (free string — any Ollama
  model id, incl. `qwen3:4b`), `SQUIDC5_IMPLANT_REQUIRE_AUTH=true`.
- **Real install command** (verified, Windows):
  `python -m venv .venv && .venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt`
  then `pip install -e .` then `squidc5` (serves https://0.0.0.0:8443, token at
  `data/admin_token.txt`). Zero-setup alternative: download `squidc5-windows-x64.exe` +
  `sc5-windows-x64.exe` from Releases (checksums verified, §4).
- Note: `squidc5 --help` does NOT print help — the entry point boots the server directly
  (observed 2026-09-29). CLI subcommands live on `sc5` (`sc5 login/sessions/implants/...`,
  README:109-119).

## 3. Claim-by-claim code verification (paths in clone @134e405)

| Claim | Evidence |
|---|---|
| INKO neural operator chat | `src/squidc5/ai/ops_tools.py:441` — `CHAT_SYSTEM_PROMPT = """You are INKO (Intelligent Neural Kinetic Operator)..."""`; route `src/squidc5/api/routes.py:2555` `@api.post("/ai/chat")` |
| Sandboxed Admin AI, railed tools, HITL | `src/squidc5/ai/admin_ai.py:114-123` (fixed system prompts, sanitize, allow-listed capabilities), `sanitize_untrusted` at admin_ai.py:102-111; tool gating `src/squidc5/ai/ops_tools.py:940` "Run one allow-listed tool with scope + policy gates"; policy engine `src/squidc5/policy/engine.py:198-221` (deny_actions, risk>=deny_min deny, `deny_autonomous_planning` for chains); HITL queue is DB migration v2 (`src/squidc5/db/migrate.py`, seen live in boot log) + `/api/v1/policy/hitl` |
| Built-in scoped MCP, **off by default** | `src/squidc5/config.py:34 mcp_enabled: bool = False`; `src/squidc5/features.py:13`; double gate `src/squidc5/mcp/server.py:60-68` (feature flag AND settings). **Live**: `GET /mcp/tools` → `{"detail":"MCP disabled by feature flag (enable Admin → Features → mcp_enabled)"}` |
| Optional LOCAL OLLAMA | `src/squidc5/ai/admin_ai.py:472-483` — when `local_llm_enabled`, a synthetic `provider:"ollama"` row is used with `base_url` from config; loopback http explicitly allowed by SSRF guard `src/squidc5/security/ssrf.py:32-36` ("http only for explicit loopback lab (Ollama etc.)"); OpenAI-shim root fixed at admin_ai.py:91-93 (adds `/v1` for loopback). Model id passed verbatim → `qwen3:4b` works by config. **Live**: `/api/v1/ai/status` returned `"active_mode":"offline"` with 15 capabilities listed (no LLM configured) |
| Go implant factory, AEAD + SOCKS reverse-dial | `agents/sc5beacon/crypto.go:21` `chacha20poly1305.New(key[:])`, AAD `"sc5-aead-v1"` (crypto.go:33); `agents/sc5beacon/socks.go:11-31` "dial target, dial C2 data port, announce conn_id, bridge" (reverse-dial duplex); factory `sc5 implants build` / `POST /api/v1/implants/build` (README:55,134); CI cross-compiles `sc5beacon-windows-amd64.exe` (ci.yml:78) |
| Malleable profiles | `src/squidc5/profiles/{engine,http_beacon,models,transforms}.py` in tree; transforms claimed in README:56 (base64, prepend/append, xor, netbios) + `POST /api/v1/profiles/{id}/push`; tests `tests/test_fuzz_transforms.py`, `test_five_star_pack_*.py`. File existence + README verified; I did not line-read transforms.py |
| OAST | `src/squidc5/oast/store.py` + DNS/HTTP/SMTP listeners (`src/squidc5/listeners/{dns_listener,http_listener,smtp_listener}.py`); `sc5 oast` CLI; OAST API rows in README:148 |
| Audit hash-chain | `src/squidc5/db/store.py:612-627` — `chain = sha256(prev|ts|actor|...)` with `prev_hash` column (store.py:624-644); verifier `GET /api/v1/audit/verify`. **Live**: fresh boot returned `{"ok":true,"checked":2,"broken_at_id":null}` |
| ROE gates | `src/squidc5/engagement/policy.py:15-16` `banned_commands` (default `["rm -rf /","format c:"]`) + `end_ts` "deny tasking after"; `command_banned()` policy.py:39-41 |

## 4. Windows-native feasibility — RUN ON THIS VM (the decisive checks)

### 4a. Source install (venv, Python 3.14.6)
```
"C:/Python314/python.exe" -m venv /tmp/sc5venv
/tmp/sc5venv/Scripts/python.exe -m pip install -r /tmp/SquidC5/requirements.txt -r /tmp/SquidC5/requirements-dev.txt
→ PIP_EXIT=0, all wheels (fastapi-0.142.0, cryptography-50.0.1, mcp-2.2.0, pydantic-2.13.5, pywin32-312, ...)
/tmp/sc5venv/Scripts/python.exe -m pip install -e /tmp/SquidC5
→ "Successfully installed squidc5-0.1.0" EXIT=0
```
Boot (entry point runs the server; no `--help`):
```
/tmp/sc5venv/Scripts/squidc5.exe
→ TLS self-signed generated (data/tls/server.crt), migrations v1..v7 applied,
  "Bootstrap admin token written to data\admin_token.txt",
  "Starting SquidC5 0.1.0 on https://0.0.0.0:8443"
```
Live probes (2026-09-29, Windows, no Docker):
- `curl -sk https://127.0.0.1:8443/api/v1/health` → `{"status":"ok"}`
- `GET /api/v1/ai/status` (Bearer admin token) → `"enabled":true,"status":"offline_fallback",
  "capabilities":[15 items: anomaly_explain, beacon_anomaly, doc_generate, evasion_suggest,
  hitl_brief, implant_build_plan, opsec_review, payload_template, phishing_asset,
  profile_mutate, recon_assist, report_draft, session_triage, shell_classify, task_suggest]`
- `GET /api/v1/ai/tools` → tool list with per-tool `scopes` + `policy_action` (railed)
- `GET /mcp/tools` → gated off (see §3)

### 4b. Release binaries (no Python at all)
```
gh release download --repo SquidSec/SquidC5 --pattern "squidc5-windows-x64.exe" \
  --pattern "sc5-windows-x64.exe" --pattern "SHA256SUMS.txt"
sha256sum -c SHA256SUMS.txt → sc5-windows-x64.exe: OK ; squidc5-windows-x64.exe: OK
(linux rows "FAILED open or read" — not downloaded, expected)
SQUIDC5_PORT=9443 SQUIDC5_DATA_DIR=... ./squidc5-windows-x64.exe
→ https://127.0.0.1:9443/api/v1/health → {"status":"ok"}
→ GET /api/v1/audit/verify → {"ok":true,"checked":2,"broken_at_id":null}
```
Exe stopped (taskkill) after the test. 26 MB PyInstaller-style single binary.

### 4c. Test suite on Windows (full suite, as evidence for breakage claims)
Command: `SQUIDC5_DATA_DIR=/tmp/sc5test-data python -m pytest -q --basetemp=/tmp/sc5-pytest`
(note: first run without `--basetemp` died on a pytest tmpdir junction bug; that is a
pytest/8.3-shortpath artifact, not a repo issue) → **`4 failed, 369 passed in 209.09s`**.
All 4 failures are Windows-environment artifacts, not code breakage:
- `test_admin_token_perms.py::test_admin_token_file_mode_0600`,
  `test_llm_key_encryption.py::test_resolve_generates_secrets_key_file`,
  `test_plugins_signing.py::test_resolve_generates_file_mode` — assert `st_mode & 0o777 == 0o600`;
  NTFS reports 33206 (→ 0o666). POSIX-only assertion.
- `test_listener_restore.py::test_restore_running_listeners_on_startup` —
  `[winerror 10048] only one usage of each socket address` on rebinding 127.0.0.1:18765
  (Windows TIME_WAIT/REUSEADDR semantics).
On the project's Linux CI the same suite is green (`CI conclusion: success` on master
2026-09-25). Nothing in the failures affects normal server operation on Windows (the exe
boot + API probes all passed).

### 4d. Ollama qwen3:4b pairing — NOT RUN LIVE
`curl http://127.0.0.1:11434/v1/models` → no response; `ollama` not on PATH; nothing
listens on 11434. Ollama is not installed on this VM, so the end-to-end pairing could not
be exercised. What IS verified: config knobs (.env.example:35-37), the local-LLM fallback
row (admin_ai.py:472-483), the SSRF loopback-http exemption (ssrf.py:32-36), and the
OpenAI-shim `/v1` root fix for loopback (admin_ai.py:91-93). Setting
`SQUIDC5_LOCAL_LLM_ENABLED=true SQUIDC5_LOCAL_LLM_MODEL=qwen3:4b` is the documented
pairing path; treat the live qwen3:4b behavior (e.g. JSON-mode reliability of a 4B model
against the fixed system prompts) as **untested**.

## 5. Issues / discussions / breakage (ask item)

- Issues: 0 open, 0 closed (`search/issues?q=repo:SquidSec/SquidC5+is:issue` →
  `{"items":[],"total_count":0}`; issues list minus PRs = 0).
- Discussions: `GET /discussions` → HTTP 410 "Discussions are disabled for this repo";
  GraphQL `discussions{totalCount}` → 0.
- So there is **no community breakage signal — and no community validation either**.
  The only breakage evidence available is the test suite (§4c: 4 Windows-artifact
  failures) and green CI.

## 6. Independent mentions (ask item: exa/firecrawl)

Exa (`POST https://api.exa.ai/search`, query "SquidC5 SquidSec C5 teamserver", 10 results):
- LinkedIn DotNetRussell 2026-08-04: "My 2026 BlackHat/DefCon surprise release. Introducing
  SquidC5" → released at Black Hat / DEF CON 2026.
- **Black Lantern Security "Crow's Nest" digest 2026-08-17** lists SquidSec/SquidC5
  (crowsnest.blacklanternsecurity.com) — strongest genuinely third-party signal found.
- LinkedIn posts by the same author (2026-08-08 "Malleable profiles and real OAST...",
  2026-08-14 "Can your C2 server do this? SquidC5 can") — self-promotion, weak independence.
- squidc5.de.softonic.com listing (auto-aggregator), repositorystats.com (auto).
- `squidhacker.com` "SQUID SEC" (author's own site).
Firecrawl `/v1/search` for "SquidC5": **0 hits** — web footprint is thin; nearly all
mentions trace to the author. Activity signal: GitHub itself (305 commits since July,
30 releases, pushes through 2026-09-25) is the real activity source.

Alternatives found (exa, "AI-native C2 framework MCP agentic teamserver LLM red team 2026"):
MCP wrappers bolted onto classic C2s — `Faceless0x7/AdaptixC2-MCP-Server`,
`v0idravl/sliver-mcp`, `schwarztim/sec-havoc-c2-mcp`, `g4sk0/mergen-mcp`; plus
`NyxeraLabs/RedForgeC2` and arXiv 2511.15998 "Abusing MCP for LLM-Powered Agentic Red
Teaming". None of those is an AI-native teamserver in-process; SquidC5's differentiator
(built-in INKO/Admin AI + its own MCP server + HITL/ROE rails, Docker-optional) holds in
this lane. Related org project: SquidSec/SquidGate (PR gate, referenced README:194).

## 7. Risks / corrections to the claim

1. **Bus factor 1**: one author (DotNetRussell) wrote 99/100 PRs; zero external issues.
2. **Self-marketed**: most external mentions are the author's LinkedIn; only Black
   Lantern Security's Crow's Nest is independent. 57 stars is early.
3. **Alpha**: `Development Status :: 3 - Alpha`, package version 0.1.0; the GitHub
   releases (v0.1.3xx) are the version of record (pyproject.toml:36).
4. **"Pairs directly with qwen3:4b"** — config-supported and code-verified, but not
   exercised live here (§4d); a 4B model vs JSON-only fixed prompts is unproven.
5. Latest release attaches linux-x64 + windows-x64 only; arm64/agent binaries are CI
   artifacts, not always attached to the release (releases list, §1).
6. README's binary table omits the Windows server/CLI exes even though they are shipped
   (README:92-105 lists Linux rows; releases contain `sc5-windows-x64.exe`,
   `squidc5-windows-x64.exe` — verified by download + sha256).

## 8. Checks the ask named — status

- gh api repo metadata: DONE (§1).
- README + packaging files read: DONE (§2).
- Dependency Windows support: DONE — proven by install (§4a), not just read.
- Issues/discussions for breakage: DONE — none exist (§5); suite run as substitute
  breakage evidence (§4c).
- exa/firecrawl independent mentions: DONE (§6).
- Real install command + Windows-native feasibility: DONE, proven by booting both the
  venv server and the release exe on this VM (§4a/4b).
- Live Ollama qwen3:4b pairing: NOT RUN — Ollama absent on this VM (§4d).