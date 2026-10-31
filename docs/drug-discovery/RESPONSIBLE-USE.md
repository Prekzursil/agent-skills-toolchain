---
title: RESPONSIBLE-USE
type: note
permalink: dqverify-repo-20261013/docs/drug-discovery/responsible-use
---

# Responsible API & Tool Use — drug-discovery MCP stack

These MCPs reach **public, shared, often free-tier** services. Use them within reason: query specifically, cache, and never loop. The goal is maximum signal per call, not exhausting a quota or tripping abuse limits.

## Golden rules (apply to every tool)
1. **Ask one precise question per call.** Resolve the exact drug/target/ID first (one lookup), then fetch — don't broad-scan then filter client-side.
2. **Cap results.** Use the smallest `limit`/page that answers the question; don't pull all 2206 tools' worth of data "just in case."
3. **No retry storms.** On error, read it and fix the query — never loop-retry a failing call. A failing call that you repeat 20× is abuse, not persistence.
4. **Cache + reuse.** If you already fetched a molecule's descriptors or a drug's label this session, reuse it; don't re-query.
5. **Batch where the API supports it** (e.g. one multi-ID call beats N single-ID calls).
6. **Respect ToS.** These are research aids; honor each provider's terms and rate limits.

## Per-service budget notes
| Service (via) | Limit reality | Discipline |
|---|---|---|
| **ToolUniverse** → PubMed/ChEMBL/FDA/OpenTargets/RCSB/etc. | Public APIs with per-IP rate limits; openFDA ~240 req/min unauth | Specific queries, small `limit`, add free `NCBI_API_KEY`/`FDA_API_KEY` (env, not source) only if you genuinely hit limits |
| **ToolUniverse** ~23 `openai`-backed "agentic" tools | Would consume a 3rd-party LLM key | **Skip** — keep core keyless; don't expose an LLM key |
| **Byteful residential proxy** (IG/FB egress) | **Free 1 GB trial** — finite | Social JSON is KB/call; still, avoid bulk media pulls. Monitor balance; rotate sticky endpoint only when needed |
| **Google Classroom** (gogcli) | Google API per-project quotas | Read-focused; student account = writes 403 anyway. Don't poll in a loop |
| **Instagram** (insta-mcp, private API) | **Ban-sensitive + flagged account** | Minimal calls, residential IP, human-paced. Never bulk-scrape; one targeted query at a time |
| **RDKit / Schrödinger** | Local (no network API) | RDKit unlimited. Schrödinger drivers consume **finite license tokens** + are slow — don't fire `glide_dock`/`fep_plus` concurrently or speculatively |

## Scope: these MCPs are DISABLED by default
To avoid spawning a 2206-tool server in every project, the 4 research MCPs (`tooluniverse`, `rdkit`, `schrodinger`, `gogcli-classroom`) are in each project's `disabledMcpServers` (`~/.claude.json`). **They are NOT loaded unless you enable them in a project.**

**Enable for a drug-discovery project:** remove the 4 names from that project's `disabledMcpServers` array in `~/.claude.json` (or use `/mcp` in-session to toggle if available), then restart the session. Re-disable when done to keep general projects lean.

Cross-platform: paths above are Windows (`D:\Program Files\Schrodinger 2022-4`, `.venv\Scripts\python.exe`); on POSIX set `$SCHRODINGER` to the suite root and use `.venv/bin/python` + bare `run`/driver names.