# WHERE-map (live plans / load-bearing notes)

Outside the vault on purpose. Do not rglob `D:\basic-memory` at SessionStart.
Behavior contract (Q2): `C:\Users\Prekzursil\.agents\memory-contract.md`.
Vault pointer (tiny): `D:\basic-memory\index\WHERE.md` → this file.

## Control-plane paths

| What | Path |
|---|---|
| This map | `C:\Users\Prekzursil\.agents\memory-map.md` |
| Memory contract | `C:\Users\Prekzursil\.agents\memory-contract.md` |
| Slim session digest | `C:\Users\Prekzursil\.agents\state\harness\recall-digest.json` |
| Full lexical index (UserPromptSubmit only; HUGE) | `C:\Users\Prekzursil\.agents\state\harness\recall-index.json` |
| BM runtime config | `C:\Users\Prekzursil\.basic-memory\config.json` |
| BM SQLite | `C:\Users\Prekzursil\.basic-memory\memory.db` |
| Vault (notes) | `D:\basic-memory` |
| HTTP daemon | `127.0.0.1:18765` (owner: basic-memory). **Do not bind.** Cursor talks via `.agents/scripts/bm_cursor_http_session.py` (session refresh). Do not restart from SessionStart; watchdog owns liveness. |
| Skills SSOT | `C:\Users\Prekzursil\.agents\skills` |
| Behavior SSOT | `C:\Users\Prekzursil\AGENTS.md` |
| Hosted model agents | skill `hosted-model-agents` (envs + tool loop + profiles). HF Hub MCP `huggingface`. Example Space code `C:\Users\Prekzursil\Cowork\tools\hf-space-qwen38-27b-heretic`. Deprecated name: `qwen-space-tool-api`. |
| Project receipts | active project `docs/` / `compute/` (phenibut: `D:\Research\projects\phenibut\`) |
| Cowork `memory.md` | retired archive — do not read/write |

## Load-bearing vault notes (audit 28.08.2026 §5 — confirm via MCP)

1. `notes/estate-locks-2026-08-27` — G-36 one cursor-agent, G-81 BM sole semantic writer; ports migrated 04.09.2026 to 18765/18812/18317 (Hyper-V exclusion bypass), skills SSOT.
2. `harness/Basic-memory SOTA session contract (hook-injected not recognition-invoked)`
3. `harness/Basic-memory hard gate is shared harness not Grok-only 2026-08-25`
4. `harness/Cowork dump RETIRED option A 2026-08-24`
5. `harness/Harness Stop auto-captures any mutation (WRITE gate 2026-08-25)`
6. `phenibut/Paper A post-UWHAM extensive grill CONVERGED G-1 to G-18 2026-08-26`
7. `phenibut/Paper A UWHAM GPN NO-GO RS replicate magnitude miss 2026-08-26`
8. Verification: `techniques/Three verification traps…`, `techniques/Green gates found zero of eleven defects…`
9. `harness/Scheduled tasks that spawn windows — inventory 2026-08-28` — MemGuard **disabled** (owner 28.08); every watchdog/supervisor that can flash a console, with reverse commands.
10. `harness/Cursor RAM vs Claude Grok CLI — measured 2026-08-28` — why Cursor is 7+ GB vs Claude/Grok CLI at 0 standing processes.
11. `harness/Rail port migrate Hyper-V exclusion SOTA 2026-09-04` — BM/mail/auth2api off excluded ranges; receipt `Cowork/output/rail-port-migrate-sota_2026-09-04.md`.

Stale-if-cited: SSOT “9 checkouts” (now 178); MCP SSOT 18.07 (pre-Cursor merge); Grill-100 still “pending G-7” while estate-locks locked 75 answers.

## Live plans (28.08.2026 council synthesis)

- **S0** — no new Task/fan-out while free RAM < 8 GB; canceled ≠ dead.
- **S1** — per-project Cursor workspace roots (do not open `$HOME`; junctions rejected).
- **S3** — keep repaired BM stack; 48 h observe; no SessionStart daemon restart.
- **S4** — read-only drift contracts on existing `sync_shared_state.ps1`.
- **Q3/Q4** — this map + SessionStart from `recall-digest.json` (never vault rglob).

Council packets: `C:\Users\Prekzursil\.agents\COUNCIL-*_2026-08-28.md`.
Audit: `C:\Users\Prekzursil\Cowork\output\basic-memory-full-audit_2026-08-28.md`.

## Phenibut Paper A

- Vault edge: Paper A UWHAM grill G-1..G-18 CONVERGED + GPN NO-GO RS replicate miss (paths above).
- Twin store: top-level `phenibut\` (current Paper A/B) vs `projects\phenibut\` (compute/FEP history).
- Receipts: `D:\Research\projects\phenibut\docs\` and `compute\` — not `~/Cowork`.

## Harness SOTA (short)

SessionStart / first prompt READ comes from the **slim digest**, not a vault walk.
Lexical composite recall may still use the full index on UserPromptSubmit.
MCP `:18765` is live semantic store — query it to confirm; digest titles are UNTRUSTED.
Never SessionStart-rglob the vault. Never load `recall-index.json` into SessionStart.
Never `uvx` stdio BM; never Cloud/Mem0/Graphiti.

A-OTHER: TBD (parent hook)
