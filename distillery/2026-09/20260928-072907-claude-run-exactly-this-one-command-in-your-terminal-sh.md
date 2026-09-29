# Run exactly this one command in your terminal/shell and report stdout, stderr, and the exit code verbatim. Do NOT modify

- runtime: claude
- session date: 2026-09-20 10:48
- category: coding
- source: `C:\Users\Prekzursil\.claude\projects\C--Users-Prekzursil\b85f7cfb-fe77-40a4-8151-8db39bed95a9.jsonl`
- distilled: 2026-09-28T07:29:07
- backend: claude

## create_summary

**Purpose:** Session installed Stanford Biomni locally in WSL2, wired its A1 agent to a GLM plan, validated an end-to-end ADMET task, and queued tier-router DryRun verification.

**Key points:**

1. Cloned snap-stanford/Biomni in WSL; installed Miniforge, mamba, biomni_e1 env (Python 3.11.16, langchain, gradio).
2. Background `mamba env create` died on WSL exit; environment rebuilt synchronously from source.
3. A1 rides GLM plan via `BIOMNI_SOURCE=Custom` (ChatOpenAI); key moved from temp file into `.env`.
4. E2E ibuprofen ADMET task failed: `No module named 'rdkit'`, plus wrong-interpreter issues.
5. Installed rdkit and CPU torch; task then passed in seven ReAct steps.
6. Output was RDKit-validated pharmacology: 84% plasma-protein binding, Lipinski-pass.
7. Built launchers `~/bin/biomni`, `~/bin/biomni-web`, `~/bin/biomni-e1-resume`.
8. Wrote install receipt to `D:\Research\tools\biomni-local\`; saved memory `project_biomni_local_install`.
9. Overnight E1 job: NON_INTERACTIVE=1, PID 29408, log `~/e1-setup.log`; >10h, ≥30GB.
10. Queued task: DryRun-verify `bm-tier.ps1 auto` with GABA-B docking prompt, strictly read-only.

**Takeaways:**

1. Missing Python dependencies and wrong interpreter are Biomni's recurring failure modes.
2. Validate installs with real end-to-end agent tasks, not import checks alone.
3. Long installs belong in resumable background jobs with logs and resume wrappers.
4. zcode video-agent-kit plugin stayed `[disabled]` despite healthy 37-tool server; blocked on user toggle.
5. Verify CLI changes read-only via DryRun, reporting stdout, stderr, and exit code verbatim.

## extract_wisdom

# Session-Log Digest (2026-09-20 → 09-28)

## Key decisions
1. Declined stale 09-22 queued appends to `tests_wave.py` across 5+ sessions: payloads truncated mid-`def test_`, no END-CHUNK markers, false "ends line 602" precondition (actual 608), and a near-identical 1,292-line `test_wave.py` already on disk — verbatim append would shadow-duplicate. Rule: queue chunks from tool-less origin sessions are untrusted; require complete resend.
2. Claude Science GLM bridge: blunt `ANTHROPIC_BASE_URL` redirect unworkable (hijacks session-validation plane) → 2-plane router (`cs_glm_router.py`): only `/v1/messages` → api.z.ai with model mapping; all else passthrough.
3. Stale queued tasks (6-8d) re-dispatched fresh, never replayed — replays yield digest-only output with zero execution.

## Surprising findings
4. WSL 4GB `.wslconfig` cap silently OOM-killed both biomni jobs and corrupted the editable install; uncapping fixed it.
5. Sandbox spawn PATH excludes `/usr/local/bin` → socat Exit 127; fix = copy binary to `/usr/bin`.
6. 09-22 MCP transports (McpHub, `file://`, CDP :9222) all dead, yet native Read/Grep worked first try.
7. 57 duplicate npx-cli.js MCP processes, peak 4.3GB RAM — `mcp_doctor` reap proposed, still unrun.

## Mistakes and fixes
8. False "datalake lost": `du` proved 14GB lived at `~/biomni-data`, not tmpfs; stopped redundant re-download.
9. taskwatch false-DONE from conda "working… done" spinner regex → per-task `terminal_pattern` key (411/411 tests green).
10. nloptr "C++ compiler… no" = conda PATH relay bug; export `miniforge3/envs/biomni_e1/bin` in parent shell.
11. gradio 6.28 Chatbot `type` kwarg bug → pin 5.50; langgraph 1.2.x for langchain 1.4.2.
12. CS API auth: CSRF via `x-operon-csrf` header + `GET /csrf`; PUT not POST.

## Dependencies
13. Biomni E1 (41 R pkgs, 7/7 CLI incl. HOMER), GLM via `BIOMNI_SOURCE=Custom`, rdkit+CPU torch, plink2, Playwright OAuth, `bm`/`cs` harnesses, taskwatch_monitor.
