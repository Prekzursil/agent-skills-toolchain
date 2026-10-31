---
title: dive-mythic-ornn
type: note
permalink: dqverify-repo-20261013/estates/offload-w2025/2026-09-29-offensive-stack/workspace-out/research/dive-mythic-ornn
---

# Deep-dive: mythic_ornn

- **Repo:** https://github.com/n0qword/mythic_ornn
- **Claim (from ask):** LLM-driven generator for Mythic Agents/Payload-Types/C2-Profiles — "the open-source implementation of the SpecterOps 'disposable tooling' demo (credits @xpn)"; pruned Mythic docs as RAG layer; AGENT.md prompt mode turns any coding agent into a Mythic dev WITHOUT Docker (scaffold only); build mode generates runnable agents from the Mythic UI.
- **Date of dive:** 2026-09-29
- **Methods run this session:** `gh api repos/n0qword/mythic_ornn` (+ trees/contents/commits/contributors/releases/issues/tags APIs), shallow `git clone` to %TEMP% for full file reads, Exa search + Exa contents (blog verification), firecrawl `/v1/scrape` (failed: "Unauthorized: Invalid token"), WebFetch (Kitploit page).

## 1. Repo reality — NOT fake, NOT dead, but young and single-maintainer

`gh api repos/n0qword/mythic_ornn` (run 2026-09-29):

```json
{"archived":false,"created_at":"2026-07-31T06:07:44Z","default_branch":"master",
 "description":"LLM-driven generator for Mythic Agents, Payload-Type and C2 Profiles.",
 "forks_count":3,"open_issues_count":0,"pushed_at":"2026-08-24T05:29:35Z",
 "language":"MDX","license":null,"stargazers_count":54,"size":636,
 "updated_at":"2026-09-25T22:52:58Z"}
```

- **54 stars, 3 forks** in ~2 months (created 2026-07-31) — respectable for niche red-team tooling.
- **Last push 2026-08-24** — 36 days quiet as of 2026-09-29. Young, not dead.
- **License: NONE** (`license: null`). No LICENSE file anywhere in the tree; only a `NOTICE` that attributes the pruned docs and notes the upstream docs repo "does not ship a LICENSE file; content is provided as-is" and defers commercial-use questions to Mythic maintainers. Repo code is effectively all-rights-reserved.
- **Activity:** 10 commits total, all by `n0qword` (`gh api .../contributors` → `[{"login":"n0qword","contributions":10}]`). History: `inital commit` → `rename project` → `feat mythic_ornn: multi-llm support, tolerant build validation, neutral env defaults` (08-01) → `fix and update: added improved performance and validations` (08-24, latest).
- **0 issues, 0 PRs, 0 releases, 0 tags, no discussions** (`has_discussions:false`). No community breakage reports — but also no community validation and no packaged releases.

## 2. What the repo actually is (verified by reading the clone)

Language "MDX" is a red herring: the bulk is `mythic-doc/` — **88 `.mdx` files** (counted via `find ... | wc -l`), a pruned copy of the official Mythic docs (MythicMeta/Mintlify_Documentation, Mythic 3.3/3.4-era) used as the retrieval corpus. Around it:

- **`template/AGENT.md`** (156 lines, read in full) — the real product. A disciplined LLM system prompt: documentation-grounding hard rule ("If a symbol... appears nowhere in `mythic-doc/` or `examples/`, treat it as hallucinated"; §3), a task→doc-path lookup table (§4), a phased investigate→design→build→verify workflow (§5), context-budget rules (§6), and **pinned current library versions: Python `mythic-container==0.6.0`, Go `github.com/MythicMeta/MythicContainer@v1.5.0` (Mythic 3.4)** (§8.1). Tool-agnostic.
- **`template/README.md`** — wiring instructions for opencode (ships `.opencode/agent/mythic-agent-builder.md` adapter + `opencode.json` `@ref` references), Claude Code (drop into `CLAUDE.md` or `.claude/commands/`), Cursor (`.cursor/rules/`), or plain chat paste. Only requirement: the agent can read the repo tree. **No Docker, no install step, nothing to compile** for prompt mode.
- **`examples/`** — empty drop-dir by design (user drops complete Mythic bundles as structural references).
- **`skills/`** — empty convention dir (opt-in `SKILL.md` playbooks; cannot override the doc-grounding rule per `skills/README.md`).
- **`tests/coffee-mythic/`** — a complete sample Mythic bundle ("coffee" agent) that the author generated with the pipeline ("added ornn-agent test: that is fun" commit, 07-31). Its `coffee_agent.py` imports only `json, random, sys, time` — stdlib-only, as claimed.

### Build mode (`ornn-agent/`) — a real Mythic payload type that generates agents

- **Install (from `ornn-agent/README.md`):** `mythic-cli install folder <abs-path>/ornn-agent` into a running Mythic install; then set container env vars in the Mythic UI: `ORNN_LLM_MODEL` (required), `ORNN_LLM_BASE_URL` (default `https://api.openai.com/v1`; any OpenAI-compatible endpoint — README gives Ollama `http://172.17.0.1:11434/v1` and Gemini `generativelanguage.googleapis.com/v1beta/openai/` examples), `ORNN_LLM_API_KEY` (optional, for local servers), `ORNN_LLM_TIMEOUT`, `ORNN_LLM_TEMPERATURE`.
- **Packaging:** `ornn-agent/Payload_Type/mythic_ornn/Dockerfile` = `FROM itsafeaturemythic/mythic_python_base:latest` + `pip3 install mythic_container==0.6.0`. Standard Mythic container; runs inside Mythic's Docker stack.
- **Code is genuinely implemented, not vaporware:**
  - `builder.py` — a real `PayloadType` subclass (`name="mythic_ornn"`, `supported_os=[Linux, Windows, MacOS]`, `c2_profiles=["http"]`) with build parameters `agent_prompt`, `agent_name`, `deep_context`.
  - `generator/llm.py` — stdlib `urllib` OpenAI-compatible `/chat/completions` client with typed error handling (`llm.py:22-58`).
  - `generator/validate.py` — real AST validation: syntax parse, `CUSTOM_COMMANDS` dict-literal structure check, per-command param-type allowlist (`String/Number/Boolean/Array/ChooseOne`), handler-callable check, marker splice into the agent template, final re-parse (`validate.py:36-118`).
  - `generator/prompt.py` — byte-capped doc loader bundling the wire-format docs into the LLM context (`max_bytes_per_doc=12000, max_total=160000`).
  - `agent_template.py` + `c2_profiles/http.py` — generated agents run on **Python stdlib only** (`getpass/json/os/platform/random/socket/subprocess/sys/time`; http client: `base64/hashlib/hmac/json/ssl/urllib.request`) — nothing to drop on target, verified by grep of import lines.
- **Repo root has NO pyproject.toml / setup.py / package.json** — there is no package-manager artifact to install. The only package.json is `.opencode/package.json` pinning `@opencode-ai/plugin` 1.18.21 (adapter development only). README requirement section: "Docker + a Mythic install to build and run generated agents" + any coding agent.

## 3. Attribution claim — CORRECTION

The ask calls it "the open-source implementation of the SpecterOps 'disposable tooling' demo." That overstates it:

- The SpecterOps post is real and verified via Exa contents: **"Disposable Tooling: Building LLM-Generated Mythic Agents from Prompt to Deployment", Adam Chester (@xpn), Jun 24 2026** (specterops.io/blog/2026/06/24/...). 31k chars of text extracted.
- The post contains **zero GitHub links and zero mentions of "ornn"** (regex search over full text). Its own approach is Claude-driven iteration with a supporting build/debug harness and a QA sub-agent — a different architecture from this repo's prompt+docs corpus and payload-type generator.
- `gh api users/xpn/repos` shows **no companion repo** for the post (nearest: `xpn/mythic_mcp`, "A simple POC to expose Mythic as a MCP server", pushed 2025-03).
- The repo itself only claims inspiration: README "Thanks to Adam Chester(@xpn) of SpecterOps for the idea and his post".

**Corrected framing:** mythic_ornn is an *independent open-source implementation of the idea* from the post — as far as this dive found, the only one packaged for reuse. The blog shipped no code.

## 4. Independent mentions (activity signal)

- **Black Lantern Security — Crow's Nest weekly roundup, 2026-09-08** (crowsnest.blacklanternsecurity.com/posts/crows-nest-2026-09-08, fetched via Exa contents): lists "mythic_ornn: LLM-driven generator for Mythic Agents, Payload-Type, and C2 Profiles https://github.com/n0qword/mythic_ornn by Panos Gkatziroulis." — the strongest independent signal; BLS is a reputable security shop.
- **Kitploit tool page** (kitploit.com/en/tools/github/n0qword/mythic_ornn + KO mirror, mirrored on vulners.com): describes both modes accurately. Its counters (e.g. "54,369 stars") are garbage — actual is 54; treat Kitploit as a mention only, not for stats.
- **purpleshift.io 2026-08-25 "C2 agent factory"** — covers the same xpn-post topic but **does not mention ornn** (0 hits in fetched text).
- cybersecuritynews.com / cyberpress.org / vpncentral.com articles cover the **xpn blog**, not this repo (title-level check only).
- Not found: any blog post, talk, or GitHub issue from anyone other than BLS/Kitploit referencing the repo directly. Exa search for "mythic_ornn github Mythic agent generator" returned exactly the above.

## 5. Windows-native feasibility (this VM: win32, no Docker assumption)

- **Prompt mode: fully native, zero install.** `git clone` + point your coding agent at `template/AGENT.md` (copy to `CLAUDE.md`, `.cursor/rules/`, or the shipped opencode adapter). The corpus is static MDX; the workflow is read-files-and-write-code. Nothing needs Docker, Python, or a build step. This works on this Windows VM today.
- **Build mode: requires Mythic, which requires Docker** (Linux containers: `itsafeaturemythic/mythic_python_base` base image, `mythic-cli`). On this Windows VM that means Docker Desktop/WSL2 — not Windows-native. Note Mythic itself does not run natively on Windows.
- **Generated agents: Windows-native at runtime.** Stdlib-only Python; `builder.py` advertises `supported_os=[Linux, Windows, MacOS]` for outputs. The container that builds them is not.
- **Dependencies and Windows support:** `mythic_container==0.6.0` (pure-Python pip package; runs in the Linux container, only relevant to build mode), LLM endpoint = any OpenAI-compatible HTTP API (Ollama/OpenAI/Gemini). No compiled deps, no OS-specific code observed in the generator (`llm.py`/`validate.py`/`prompt.py` are stdlib-only).

## 6. Breakage / community signals

- 0 issues, 0 PRs, 0 discussions → **no reported breakage found anywhere** (nothing to read; issues API total = 0, run this session). Equally: no independent user reports of success. The only demonstrated end-to-end output is the author's own `tests/coffee-mythic/` fixture.
- No CI workflows in the tree (no `.github/`), no tests harness beyond the fixture, no releases/tags to pin.

## 7. Score

- **Not fake:** real, coherent, working-looking code; docs corpus is genuine Mythic 3.3/3.4-era content; sample output shipped.
- **Not dead:** 36 days quiet on a 2-month-old project with a lone maintainer — watch, don't rely.
- **Value: high** for the c2-agentic lane. It is the only open-source artifact found that packages "LLM-generated Mythic agents" with version-pinned grounding (the exact hallucination problem the xpn post documents — "First Attempts With Just Vibes" — and this repo hardens with its doc-grounding rule + AST validation). Prompt mode is immediately usable on this Windows VM with any coding agent. Closes a real capability gap (grounded Mythic agent dev without hand-re-reading docs).
- **Caveats to carry forward:** (1) no LICENSE — fine to use privately, don't redistribute as if open; (2) build mode needs Mythic+Docker/WSL2; (3) single-maintainer, zero community validation; (4) Kitploit star counts are bogus — real count 54.

## Verdict on the original claim, line by line

| Claim | Verdict |
| --- | --- |
| LLM-driven generator for Mythic Agents/Payload-Types/C2-Profiles | ✅ Verified (README; `builder.py`) |
| "the open-source implementation of the SpecterOps demo" | ⚠️ Corrected: independent implementation of the *idea*; the post shipped no repo, has zero links/mentions of ornn; repo only credits @xpn |
| pruned Mythic docs as RAG layer | ✅ (88 MDX files; path-based retrieval + byte-capped bundling, not vector-RAG) |
| AGENT.md prompt mode, any coding agent, no Docker, scaffold only | ✅ (`template/AGENT.md`, `template/README.md`; build/run of output still needs Docker+Mythic, as the repo's own Requirements state) |
| build mode generates runnable agents from the Mythic UI | ✅ (`ornn-agent/`, `mythic-cli install folder`, OpenAI-compatible env config, stdlib-only generated Python agents) |