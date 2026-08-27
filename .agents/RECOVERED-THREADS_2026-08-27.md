# Recovered threads — Grok CLI session recovery (27.08.2026)

*Phase 1 deliverable. Recovers three named Grok CLI sessions (~21 h before recovery), lists unfinished
work as checklists, records principles that must not be violated, and marks where each thread resumes.
No secrets/keys are reproduced — referenced by name only. Jailbreak/roleplay/uncensored content is
noted where it exists but not reproduced.*

---

## Where AI sessions live on this box (inventory)

| Runtime | Store | Format | Count / size |
|---|---|---|---|
| **Grok CLI** | `C:\Users\Prekzursil\.grok\sessions\` | `session_search.sqlite` index (table `session_docs`: `session_id`, `updated_at`, `title`) + per-session dirs keyed by URL-encoded cwd (`C%3A%5CUsers%5CPrekzursil\<UUID>\`) each holding `chat_history.jsonl` + `summary.json` | many; the picker's "8 external sessions hidden · f to show" = sessions whose cwd ≠ current dir |
| **Claude CLI** | `C:\Users\Prekzursil\.claude\projects\` | per-project dirs of `*.jsonl` transcripts | 34 project dirs · 16,936 files · ~9,346 MB |
| **Codex CLI** | `C:\Users\Prekzursil\.codex\sessions\` | `.zst` (compressed) + `.jsonl` | 2,752 files · ~2,287 MB |

To find a Grok session by name:
`sqlite3 .grok\sessions\session_search.sqlite "SELECT session_id, datetime(updated_at/1000,'unixepoch'), title FROM session_docs WHERE title LIKE '%<term>%';"`

Claude/Codex stores were **inventoried only** (location, format, count) — not deep-read, per scope.

---

## Session 1 — "MIRCEA"  (Paper A post-UWHAM extensive grill)

- **id** `01a019e0-38d7-7582-96de-7f70df6d28ec` · fork of the P2 2007 session · agent `grok-build-plan` · `grok-4.6` xhigh
- **State:** **LOCKED / CONVERGED.** `last_turn_summary`: *"Grill G-1–G-18 locked; spawn waits on 'go'."*
- **Converged decision log:** `D:\Research\projects\phenibut\docs\GRILL_POST_UWHAM_2026-08-26.md`
- **What it decided (G-1…G-18):** licensed **Schrödinger BPMD**; **α2δ WaterMap**; Polarizable FEP / OpenFE deferred to a later wave; **LAT1 deferred**; **dump the FEP+ CSV**; **mechanism-only** claims (no clinical/dosing language); **one Paper A** (do not fork into multiple papers).
- **Budget/infra recap:** Modal remaining tracked as **$42.50 minus metered usage** (not the $30 credit line); GPN/R​S accounts hopped onto `prekzursil` + `prekzursil1993`; standing `OVERRIDE_SAFECHECKPOINT` dropped; post-hop ETAs recomputed from cycles gained on this box.

**Unfinished — checklist**
- [ ] Write the **ECC protocol** (the next concrete artifact the session named).
- [ ] Spawn **t=0 CPU** run and the **licensed BPMD** run — *gated on an explicit user "go".*
- [ ] Execute the **next-wave spawn map** recorded at the tail of `GRILL_POST_UWHAM_2026-08-26.md` (G-18 + follow-ons).

**Resume at:** re-open `GRILL_POST_UWHAM_2026-08-26.md`; on user "go", write ECC protocol → spawn t=0 CPU + licensed BPMD. Do **not** self-start; the session deliberately paused on consent.

---

## Session 2 — "P2 2007 leftover harvest and G-1 remesure"

- Parent of the MIRCEA fork. Goal: drive the P2 harness to a verified **2007/2007 G-1 success**, then re-measure.
- **Workflow lineage:** `p2-g1-tranches` → `p2-g1-until-green` → `-2` → **`p2-g1-until-green-3`** (active; uncapped; **fail-closed** — only `complete()`s on 2007/2007 verified *twice*, otherwise `await_user`).
- **G-1 failure classes already addressed:** missing modules; probe assertion; missing probe scripts; schema `$ref` resolution.
- **Side results captured in this session:**
  - Local-LLM deep research (six dual-ranked reports — see Phase 2 input list below).
  - **Cursor Grok 4.6 xhigh** confirmed callable (`CURSOR_GROK46_XHIGH_OK`).
  - `Buletin.pdf` downloaded to `~\Downloads`.
- **Blocker seen:** gate agents died on **HTTP 402 "Grok Build usage balance exhausted."** User directive was to treat the exhaustion as a false-positive and re-run at max concurrency — but 402 is a real hard cap; see Principles.

**Unfinished — checklist**
- [ ] Confirm `p2-g1-until-green-3` reached **`2007/2007 G-1 SUCCESS: delivered locally`** — verified twice — before claiming green.
- [ ] If it paused on budget, resolve **Grok Build balance** (or route the gate to a non-metered runner) rather than looping into repeated 402s.
- [ ] Fold the leftover-harvest remesure result back into the P2 record once green.

**Resume at:** check `p2-g1-until-green-3` status; if paused, unblock the runner/budget, then let the fail-closed loop finish. Never mark green on an unverified or budget-aborted gate.

---

## Session 3 — "Bolt hosting, discount lists, skills PR"

- Two workstreams: (a) document the **Bolt / Bolt.Ro** estate knowledge; (b) **git hygiene** for `agent-skills-toolchain`.
- **Bolt docs written:** `D:\Research\projects\bolt\docs\bolt-estate-knowledge_2026-08-26.md` + companion `bolt-estate-grounding-ledger_2026-08-26.md` (grounds each claim against basic-memory / forensics / sessions / local dirs).
- **Hygiene outcome:** live↔repo drift driven to **literal zero** (0 divergent files) and **0 broken docs links**, via `sync-from-live.ps1` (drift exclusions for hook runtime state + live-only zips) and docs-link fixes (restored tracked `foundry create/` files, excluded fixture/vendor trees).

**Unfinished — checklist**
- [ ] **Commit decision** on the working tree: ~70 dirty paths (mostly `skills/microsoft-foundry/` plus new skills/hooks) staged-but-uncommitted, **awaiting the user's go** (no commit was made without approval).
- [ ] Follow up the **pending Bolt exploration paths** flagged in the grounding ledger (discount lists / hosting specifics not yet grounded).
- [ ] Open the "skills PR" once the commit decision lands.

**Resume at:** get the user's commit/PR decision on the ~70 dirty paths in `agent-skills-toolchain`, then commit + open the skills PR. Bolt research resumes from the grounding ledger's open items.

---

## Principles established across these sessions — do not violate

1. **Mechanism / hypothesis only** for phenibut and all comp-pharm work. No dosing, regimens, titration, sourcing, or personalized medical guidance.
2. **Schrödinger license-bypass route is permanently declined.** Use the licensed suite (Windows/Maestro CPU path) + Modal for GPU physics.
3. **Fail-closed gates.** A workflow may only report green on a success condition **verified twice**; a budget-aborted or unverified gate is **not** green. Do not convert HTTP 402 exhaustion into a fake pass.
4. **Never overwrite outputs** — always `_v2` / `_v3`. Save receipts in the active project folder, not `~\Cowork\`.
5. **No git commit without an explicit user decision** (the Bolt session held ~70 paths rather than self-committing).
6. **Provenance over assertion** — PMID / ChEMBL / run-log behind every claim; secrets never committed (refer by name only).
7. **Do not invent Ollama/HF tags.** Flag `UNVERIFIED`; probe live (`real=1`) before asserting a model exists or its size.
8. **One Paper A** — converge, don't sprawl into parallel papers.

**Jailbreak / uncensored content note (not reproduced):** these sessions touched a dropped `OVERRIDE_SAFECHECKPOINT` flag and researched abliterated / uncensored / offensive local models (WhiteRabbitNeo/DeepHat, dolphin, huihui abliterated). Existence noted for continuity; no prompts, payloads, or bypass text are copied here. Offensive-model use stays owner-ops estate-local only.

---

## Direct inputs handed to Phase 2 (local-models audit)

Six dual-ranked reports produced inside the P2 session, under
`C:\Users\Prekzursil\source\ast-integrate\docs\research\`:

1. `local-deep-research-unconstrained_2026-08-26.md`
2. `local-deep-research-this-box_2026-08-26.md`
3. `local-models-science-unconstrained_2026-08-26.md`
4. `local-models-science-this-box_2026-08-26.md`
5. `local-models-offensive-unconstrained_2026-08-26.md`
6. `local-models-offensive-this-box_2026-08-26.md`

Plus scope map `estate-research-science-scope_2026-08-26.md` and handoffs
`uncensored-local-llms-handoff_2026-08-26.md`, `ollama-llama33-abliterated-70b-size-handoff_2026-08-26.md`.
The hardware verdict throughout: **RTX 4050 Laptop 6141 MiB → GPU-full weights ≤ 5117 MiB → NO 14B+.**

---

## APPEND — independent re-recovery pass (27.08.2026, second agent)

A second recovery pass re-opened only the three named sessions (scope guard honoured; no other
Grok session read). It **confirms the sections above** and adds the following verified refinements.
No jailbreak/exploit-development text was encountered in the material read; the BOLT session does
contain the owner's own infra/secret forensics — those files are named, never reproduced.

**Session-store pointers (re-verified for the sibling's catalog):**

| Runtime | Store dir | Format | Rough count (this pass) |
|---|---|---|---|
| **Grok CLI** | `C:\Users\Prekzursil\.grok\sessions\` | per-session UUID dirs grouped by URL-encoded cwd (`chat_history.jsonl`, `summary.json`, `compaction\segment_*.md`, `events.jsonl`) + FTS index `session_search.sqlite` (table `session_docs`) | **45 sessions** in the index; **9** cwd groups (bulk under the `…\Prekzursil` home group) |
| **Claude CLI** | `C:\Users\Prekzursil\.claude\projects\` | per-project dirs of `*.jsonl` transcripts | ~34 project dirs / ~16,936 files (per prior pass; not re-walked — RAM) |
| **Codex CLI** | `C:\Users\Prekzursil\.codex\sessions\` | `.jsonl` + `.zst` rollouts | ~2,752 files (per prior pass; not re-walked — RAM) |

Fast Grok lookup by title:
`sqlite3 .grok\sessions\session_search.sqlite "SELECT session_id, datetime(updated_at/1000,'unixepoch'), title FROM session_docs WHERE title LIKE '%<term>%';"`

**Session identities confirmed (from each `summary.json`):**
- "P2 2007 leftover harvest and G-1 remesure" = `019fe1f3-4229-7eb1-b698-716130cd7669` (214 chat msgs; last active 26.08 04:56; `grok-4.6` xhigh).
- "MIRCEA" = `01a019e0-38d7-7582-96de-7f70df6d28ec` (manual title; **fork** of the P2 session; 83 chat msgs; last active 26.08 04:27; `grok-4.6` xhigh).
- "Bolt hosting, discount lists, skills PR" = `019ff1d3-a29a-7153-a949-01b2b7a2594c` (185 chat msgs; last active 26.08 04:06; `grok-4.5` high).

**BOLT — skills PR refinement (from `compaction/segment_002.md` + `segment_000.md`):**
- The "skills PR" is **already open as PR #292** (git-hygiene / academic-skills), branch
  `chore/hygiene-academic-skills-20260825 @ 6a47fb5d`, alongside local `_advver_M14` commits.
  The remaining action is therefore **not** "open a PR from scratch" but **commit the ~70 dirty
  paths** (mostly `skills/microsoft-foundry/`) and reconcile them with PR #292 — still gated on the
  user's explicit go. The final `summary.json` state is *"Hygiene literal zero: drift CLEAN, docs 0;
  commit pending"* — i.e. hygiene reached zero but the tree is **uncommitted**.
- **Discount-list finding (PM-level, benign):** the session concluded the live Bolt app is **not** in
  the Databricks SQL warehouse (that is an analytics replica) — inferred hosting is **AWS + Okta SSO
  + `admin-panel.bolt.eu` / internal `boltint.net`, TiDB+Kafka → lakehouse**. Promo/coupon production
  data exists (`main.ng_delivery.delivery_basket_campaign`, `…promo_code_enrollments`, pricing marts),
  but **no confirmed "email allowlist" table** was found; the email-add surface is likely admin-panel
  campaign tooling, not the warehouse. Secret-forensics files (e.g. the plaintext Databricks secrets
  dump, key-sweep reports) are **named only** in the session and **not** reproduced here.

**P2 — local-model research output confirmed on disk** at
`C:\Users\Prekzursil\source\ast-integrate\docs\research\` — all six dual-rank reports
(`local-deep-research-{unconstrained,this-box}`, `local-models-science-{…}`,
`local-models-offensive-{…}` all `_2026-08-26.md`), plus the uncensored trio
(`uncensored-local-llms{,-unconstrained,-this-box}_2026-08-26.md`), the science scope map, and
`estate-lens-handoff_2026-08-26.md`. These are the direct inputs to the Phase 2 audit.

**Local-models bridge fact for Phase 2:** the handoffs establish an **already-installed** Ollama
model (`qwen2.5:7b`, ~4.47 GiB on the 6141 MiB card) as the proven-fitting reference, and the hard
rule **NO 14B+ GPU-full on this box** (14B ≈ 9 GB > 5117 MiB weight cap). MIRCEA independently
records *"local RTX 4050 6 GB cannot FEP"* — heavy science stays on Modal/licensed suites, not local.

**Nothing in today's harness work should regress these:** don't re-open the P2 fail-closed gate as
"green" without the twice-verified 2007/2007 check; don't self-commit the BOLT `agent-skills-toolchain`
tree (PR #292 + ~70 paths await the user); don't self-start MIRCEA's ECC/BPMD spawn (waits on "go");
and Phase 2 must not stand up an always-on local daemon that duplicates the OpenRouter `:free` sidecar.
