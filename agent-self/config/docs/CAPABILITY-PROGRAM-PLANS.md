# Capability Program — Gated Implementation Plans (2026-06-11)

Adversarially-reviewed (13-agent planning workflow `wf_60836737-3fc`). All 6 components REVISE→PASS;
fixes folded in. Companion to `CAPABILITY-ASSIMILATION-PROGRAM.md`. HackTricks scope refinement
(2026-06-11): corpus is a GENERAL knowledge base, domain-neutral skill description, "all info, all cases".

## Readiness
| Component | Verdict | Route (gate) | Wave | Status |
|---|---|---|---|---|
| video `reframe` | REVISE→PASS | T3 (light design gate on WSL-invoke boundary) | 1 | Wave-1 = verthor-only; engine-1 is net-new, not reuse |
| `hacktricks` (+`hacktricks-api`) | REVISE→PASS | T2-3 (plan gate) | 1 | Trim to hacktricks repo + /rag; fix sparse + /mnt/d path |
| `autoresearch` | REVISE→PASS | T2 (plan gate + overlap pass) | 2 | Fix commit-before-measure; 4-axis coverage |
| `context-sandbox` | REVISE (granularity) | T2 (skill-scout decides) | 2 | Default = section in context-budget |
| `memory-consolidation` (autodream) | REVISE→PASS | **T4 FULL 5-agent design gate** | 3 | Route mutations via basic-memory MCP; bound verifier |
| funclip | REVISE→PASS | T2 (plan skim) | 4 (cond) | Only on real Mandarin job; pin Pillow<10, drop g4f |

## video — `reframe` (Wave 1)
DoD: one 16:9 sample -> 9:16 1080x1920 H.264 audio-intact subject-tracked clip via verthor (engine-2),
own ffprobe checks + comparison summary; validator passes; no secrets.
Fixes: (1) Wave-1 = verthor ONLY (engine-1 claude-shorts deferred to Wave-2 — needs Remotion/ffmpeg
renderer + 2nd torch venv, net-new not reuse). (2) Own ffprobe acceptance (not upstream validate.sh).
(3) `sudo apt-get install ffmpeg jq` = user-run manual prereq behind `command -v ffmpeg` preflight
hard-stop (non-interactive wsl sudo deadlocks). Mandatory `--saliency-model handcrafted` (never
`deepgazemr` = torch.hub RCE); explicit `--video-encoder libx264` (NVENC auto-degrades). Pin both SHAs.
Layout: canon `skills/reframe/{SKILL.md,scripts/{setup_wsl.sh,reframe.sh,compare.sh},references/,tests/}`;
build root `~/.local/share/reframe/` (gitignored, cp-not-add). ~5GB. WSL2 Ubuntu 24.04, RTX 4050. TDD first.

## hacktricks — `hacktricks` (Layer A local) + `hacktricks-api` (Layer B) (Wave 1)
DoD: offline ripgrep of sparse local clone returns a known page, 0 network; /rag call caches, 2nd
identical call hits cache 0 quota; usage-guard refuses near-zero; key never in stdout/stderr/files.
Fixes: (1) non-cone sparse: `git clone --filter=blob:none --no-checkout <url> /mnt/d/knowledge/hacktricks/hacktricks`
-> `sparse-checkout init --no-cone` -> `set '/src/**' '!/src/images/**'` -> `checkout master`; assert
tree <40MB + no src/images; update = fetch --depth 1 + reset --hard + re-assert. (2) ONE canonical path
`/mnt/d/knowledge/hacktricks` (clone script uses /mnt/d form, never `D:/`); pick ONE search substrate.
(3) Wave-1 = hacktricks repo + /rag only (cloud + /chat -> Wave 1.1); stdlib urllib (zero-dep, TLS-verifies);
length-bound + JSON-encode input (drop bogus %-strip); test redaction on stdout+stderr+401 path.
Cache: SHA256(endpoint+canonical-json(body)) -> {hash}.json under .cache/; usage-guard GET /rag/usage
before spend, refuse if remaining<=floor(2). CC BY-NC (personal ref). No upstream scripts (sparse excludes scripts/).
GENERAL knowledge base — domain-neutral SKILL.md description.

## autoresearch — `autoresearch` (Wave 2)
Lean single-file canon skill = git keep/discard auto-revert loop wired to .coverage-thresholds.json.
Fixes: (1) commit BEFORE measure (`git add -A && git commit` then Verify; discard = reset --hard HEAD~1;
discarded SHA reflog-only). (2) read total.{lines,branches,functions,statements}.pct from
`jest --coverage --json`, 4-axis compare, discard if ANY axis regresses. (3) PowerShell cleanup +
name canon->~/.agents/skills copy step. Vet ResearcherSkill for subprocess/http before absorb. Reuse
`fresh-context-verify`. Drop the 11 cmds + 9 hooks. <=230 lines. MIT attribution.

## context-sandbox (Wave 2, granularity OPEN)
Net-new after subtraction is thin: a "print only derived results" discipline + ~15-line basic-memory
write_note/search_notes routing recipe + sandbox-index/ tag. Drop SQLite/FTS5 (basic-memory does hybrid).
Before build: de-overclaim (markdown can't enforce/automate); TDD RED for index chunk boundaries;
frontmatter allowlist {name,description,license,allowed-tools,metadata} only; ELv2 clean-room. DEFAULT =
section in context-budget/strategic-compact; standalone only if skill-scout says it survives.

## memory-consolidation (autodream, Wave 3, GATED)
DoD: on-demand pass (diff-before-prune confirm + fresh-context verifier) over basic-memory + MEMORY.md;
native AutoDream OFF; --dry-run writes nothing; merge 3 dup checkpoints->1; MEMORY.md byte-identical
unless operator approves; rollback exact.
Fixes: (1) ALL vault mutations via basic-memory MCP (delete_note/move_note/edit_note/write_note), never
raw fs (live SQLite index); acceptance: search_notes reflects change. (2) bound verifier: skip exact dups,
near/stale only, <=8 subagents batched, per-cluster timeout -> missing verdict = KEEP-BOTH; reuse
fresh-context-verify. (3) concrete diff renderer (multi-file delete+create), `_dream.lock` + backup hash
manifest verified before first delete. MEMORY.md hard-protected from --yes; operator-invoked only (no hook).
MANDATORY full 5-agent design gate -> plan gate -> build.

## funclip (Wave 4, conditional)
Isolated app `D:\tools\funclip\.venv` (py3.10/3.11). Install only on real Mandarin job (English = claude-shorts).
Fixes: (1) stage-1-before-stage-2 same --output_dir (stage2 load_state); --start_ost/--end_ost = ms offsets.
(2) pin Pillow<10 (moviepy ANTIALIAS); torch+torchaudio together from CPU index via constraints. (3) drop g4f
(only launch.py imports it). MODELSCOPE_CACHE/HF_HOME on D:; never name script funasr.py; never launch.py --share.
Fork = clean upstream mirror HEAD 6ff40ba (MIT). Rollback = delete folder. No canon/MCP footprint.

## Waves
- Wave 1 (parallel, independent): video `reframe` (verthor-only) + hacktricks (Layer A + /rag).
- Wave 1.1: hacktricks-cloud + /chat (each gated/tested first).
- Wave 2: autoresearch + context-sandbox (after skill-scout granularity).
- Wave 3 (GATED): memory-consolidation (5-agent design gate first).
- Wave 4 (conditional): funclip.
- Wave 2 video follow-up: engine-1 (claude-shorts) + clipify engine-3 for side-by-side.

## Defaults applied unless overridden
- video encoder = libx264 (Open Decision #2; NVENC attempt only on request).
- context-sandbox = section in context-budget (Open Decision #4; Wave 2, skill-scout confirms).
