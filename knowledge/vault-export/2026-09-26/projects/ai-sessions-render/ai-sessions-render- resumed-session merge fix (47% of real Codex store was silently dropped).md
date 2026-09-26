---
title: 'ai-sessions-render: resumed-session merge fix (47% of real Codex store was
  silently dropped)'
type: decision
permalink: main/projects/ai-sessions-render/ai-sessions-render-resumed-session-merge-fix-47-of-real-codex-store-was-silently-dropped
tags:
- ai-sessions-render
- data-loss
- codex
- loaders
- defect
- measured
---

# Resumed Codex sessions silently destroyed ~half the corpus

`valid_as_of: 2026-08-08`

## The defect (CONFIRMED, reproduced with a passing control)

`codex_rollout._assemble` sets `Conversation.id = session_id` (`codex_rollout.py:296,314`).
A **resumed** Codex session writes a SECOND rollout file under the SAME `session_id`, so two
files yield two `Conversation` objects with an identical id. `loaders._admit` correctly
declined to call that a collision (same source) — but its docstring justified doing nothing
on the premise that "the conversation dedupes by id, exactly as before".

**That premise died** when `corpus.add_conversation` was changed to RE-INDEX rather than
early-return (`corpus.py:318-331`, the reindex fix). "Dedupes by id" became
**"OVERWRITES by id"**. `conversations.conversation_id` is UNIQUE, so the later leg simply
replaced the earlier one.

Symptom: **2 files in -> 1 row out, the older leg's turns unsearchable, `INGEST_ERRORS 0`,
exit 0.** Nothing anywhere reported it.

## Scale — MEASURED on the owner's live `~/.codex/sessions`, not estimated

| metric | value |
|---|---|
| rollout files | 2024 |
| distinct non-blank session ids | 1069 |
| ids spanning >1 file | 236 |
| files sitting in a shared id | 1189 |
| **files silently dropped** | **953 = 47.1% of the store** |
| **response_items lost** | **204,987 = 84.6% of shared-id volume** |
| shared ids where the survivor was a superset (harmless) | **0 of 236** |
| overlap shape | 156 fully disjoint, 78 partial, 2 no-ids |
| worst single id | **66 files** |

## The fix

`loaders._merge_resumed_leg` — a later rollout of an already-admitted thread MERGES into
the conversation it continues instead of overwriting it. Field policy:
turns appended in file order minus duplicates; **title/preview/created_at from the FIRST
leg** (a resumed leg's title is the resume prompt, not the subject); `updated_at` latest;
`tokens_used` max (Codex reports per-rollout cumulative — summing double-counts);
`rollout_path` latest (that is what `codex resume` continues), with **all** legs kept in
`meta["rollout_paths"]`.

Turn identity = `Turn.uuid` when present, else `(role, timestamp, block text)` —
~1/3 of real items carry no `payload["id"]` and `grok.py:311` never sets one, so a
uuid-only key re-appends the whole replayed prefix.

## Gotchas worth keeping

- **`.jsonl.zst`, not `.jsonl`.** The live store is 2024 `.zst` and ZERO plain `.jsonl`.
  A probe globbing `rollout-*.jsonl` scans **zero files and reports success** — that is a
  broken detector, not an empty store. The engine already handles both
  (`codex_rollout.py:417-418`); my first probe did not.
- **A test can pass throughout the entire life of the bug.** The existing
  `test_a_REPEATED_id_from_the_SAME_source_is_not_a_collision` asserted on errors, thread
  ids and edges — never on whether both legs' CONTENT survived. Green the whole time.
- **A stale comment masked it.** The false sentence was load-bearing: it told every later
  reader the case was handled. Comment drift is a data-loss vector here, which is why
  `tests/test_citation_anchors.py` exists.
- The dead `if node is None` fallback in the merge was caught by the 100% coverage gate and
  DELETED rather than pragma-ed — a silent fallback would have converted a broken invariant
  into the resumed leg quietly replacing the original's title.

Relates to [[ai-sessions-render]] and the coverage-honesty rule in
[[coverage-honesty-pragma-scope]].

## Two follow-on defects, both found by falsifying the fix itself

Shipped as three commits: `7dbb99a` (merge) -> `1afae7b` (divergent renderings) -> `affae65`
(id-less collision).

### 2. `Turn.uuid` marks where a turn STARTS, not how far it extends — `1afae7b`

The merge keyed turns on `Turn.uuid` and dropped repeats. But `codex_rollout.py:283` opens
an assistant turn with the first item id of a RUN and accumulates the rest into it, so a
resumed leg cutting the run differently arrives with the SAME id and a DIFFERENT body.

MEASURED: 3 such turns across the 236 merges, all in one 66-leg thread, all **DIVERGENT**
(neither body a prefix of the other) — one pair was 94 blocks/12,044 chars vs
35 blocks/**17,012** chars. Keeping whichever arrived first truncated by thousands of chars.

Fix: richer rendering wins, replaced in place. Weight measured in **characters, not blocks**
— the divergence with FEWER blocks carried MORE text. Union was rejected: legs chunk the
same prose differently, so unioning swaps silent loss for silent duplication.
Recorded in `meta["merge_divergent_turns"]`.

### 3. Two id-less sessions overwrite each other ON DISK — `affae65`

Commit `88a0226` made a blank thread id neither claim nor collide, so both id-less sessions
were ingested. **It got them into the corpus, never into the INDEX.** `Conversation.id = tid`
is blank in exactly that case and `conversations.conversation_id` is UNIQUE → 2 convs in
memory, 1 row on disk, first unsearchable, 0 errors.

Fix: fill the blank with `unidentified:<basename>`. **Basename, not full path** — Codex moves
finished sessions to `archived_sessions/`, and a path key reads the move as a new conversation
and grows the corpus every build. Thread id stays blank (no graph node invented).
Live store has ONE such file, so this closes a proven class, not a live loss.

## The transferable lesson — an in-memory assertion is NOT a disk assertion

**Three defects in a row shared one blind spot.** Every guarding test asserted on the returned
in-memory `Corpus` (conversation ids, thread ids, edges, errors) and never on what the SQLite
index actually held. All were green for the entire life of the bug. In this codebase the disk
IS the product — the cockpit never sees the returned object, it spawns a sidecar against the
index FILE.

**Rule:** any ingest test must assert `index.count(conn)` and a `corpus.search(conn, ...)` hit
for content from EVERY input, not just that the input was admitted.

Second lesson: **falsify your own fix against real data after the synthetic tests are green.**
Defects 2 and 3 were both invisible to synthetic fixtures and to the 100% coverage gate; only
running the merge over the real 2024-file store surfaced them.

## Session outcome 2026-08-08 — 12 commits, all four stacks green

Python 1342 passed @100% cov · cockpit TS 958 passed, tsc 0, **coverage 83.75% -> 100%
statements** · JS 418 passed · Rust 27 passed, clippy clean. Working tree clean. **Nothing
pushed, nothing published.**

Beyond the three resumed-session fixes above:
- **`27c9f8a`** TS to 100% + a 4th discoveryPanel defect: `emit()` cleared `needsAttention`
  on every patch, so clicking "+7 more" made the panel vanish, destroying the cockpit's only
  report of skipped files. RED-tested first.
- **`95c03f8`** UNC: the *spelling* class was already closed (13 spellings, 0 ms, controlled
  against a reachable `\\localhost\C$`); the open one is **resolution** — a `net use` `Z:\`
  and a directory symlink both accepted while canonicalizing to the same SMB path. Typed
  `Prefix` check; 6/6 mutants killed.
- **`d888fbc`** a *security* test flaking: `devServerFsAllow.test.ts` resolved the vite
  config 10× for one immutable answer and blew the 5000 ms default under parallel load.
  Memoised (cause) rather than timeout-raised (symptom); test phase 20.3s -> 6.25s.
- **`d546be6`** the mock IPC engine diverged from the sidecar on 6 `corpus.*` contracts;
  5 tests had pinned the fiction.
- **`7f2d119`** JS rail dropped a real export (3 holes) and could not exit 3.
- **`e748e94`** reindex tests branched on the FIXTURE NAME while `init_index` decides
  `contentless_delete` from the SQLite version — 2 tests red on any runner < 3.43.
- **`446fea8`** release path; a **5th** version (`__init__.py`, shipped in the wheel as
  `engine_version`) was outside the gate.

## The one lesson worth carrying — in-memory is not disk

**Three defects in a row, plus one I introduced, all shared it.** Every guarding test
asserted on the returned in-memory `Corpus` and never on the SQLite index. All were green
for the whole life of the bug. The cockpit never sees the returned object — it spawns a
sidecar against the index FILE.

**Rule:** an ingest test must assert `index.count(conn)` AND a `corpus.search(conn, ...)` hit
for content from EVERY input. Admission is not persistence.

**Corollary, learned the hard way:** falsify your own fix against REAL data after the
synthetic tests go green. Two of the four were invisible to synthetic fixtures *and* to the
100% coverage gate.

## Operational: the delivery channel is not reliable

**Reports do not route.** 11 of ~13 agents this session delivered idle notifications and
**zero report bodies**. Nothing is lost — every teammate writes
`…/<session>/subagents/agent-a<name>-<id>.jsonl`, and the terminal report is the last
assistant text block carrying `SUCCESS:`/`FAILED:`. **Read the transcript; do not trust the
channel.** Extractor kept at `.scratch/extract_agent_reports.py`.

Agents corrected me three times and were right each time: a proposed `^[A-Za-z]:\` UNC fix
that `Z:\` defeats; a salvage premise that reports were "lost"; and my own claim that two
timing measurements conflicted when they targeted different hosts.
