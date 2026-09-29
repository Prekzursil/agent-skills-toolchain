---
type: note
status: active
valid_as_of: 2026-09-29
---

## What this is

- [fact] This note indexes a 13-note backfill covering 2026-09-23 to 2026-09-29, authored from the `.remember` day spools because no `write_note` call was ever made for that window. The 13 notes are the ONLY new content; this note is the provenance record.

## Why the durable layer was empty

- [fact] The strong premise "2026-09-23 onward exists only as .remember and was never written to the vault" is REFUTED. A filesystem-mtime enumeration of the vault found 14 non-hash-directory `.md` files touched since 2026-09-23: 8 `sessions/` auto-capture notes and 6 real content notes (`harness/Harness reconcile offload-w2025 2026-09-23`, `harness/VM harness backup vm-backup-2026-09-25`, `research/Research coverage register register 5 of 5 built 2026-09-25`, `research/Claude Code UserPromptSubmit hook output schema measured in the installed binary 2026-09-25`, `projects/CV programme decisions G-1 G-2 G-18 2026-09-24`, `models/Model Routing Decision - GLM-5.3 default, Kimi K3 escalation`). Those 6 subjects were SKIPPED as already-present.
- [fact] The corrected gap is narrower: the 8 `sessions/` notes are 416-to-526-byte stubs whose body literally reads "this session mutated files and did not call write_note", with ZERO `- [decision]`/`- [fact]` observations and ZERO `[[wikilinks]]` - which `memory-contract.md:50` itself defines as a failed write. Their generator hard-codes that body, so the auto-capture pipeline is a LIVENESS RECEIPT, not a memory: a perfectly healthy daemon would still have captured nothing of substance.
- [fact] ROOT CAUSE, therefore: nothing ever authored the durable layer. The write-ahead spool at `~/.claude/memory-spool/` is genuinely empty (0 files), so "0 unflushed" is true but means "nothing was attempted", not "everything was delivered".
- [fact] 2026-09-27 has NO source in either independent carrier - absent from both `.remember/today-*.md` and `.remember/logs/memory-*.log` - so almost certainly no session ran that day. It is a gap in the record, not a gap in this backfill.

## The bm-spool carrier: corrected mechanism

- [fact] A SECOND carrier exists at `~/.agents/state/harness/bm-spool/`: 237 records of shape `{title, body, flushed, ts}`, 231 with `flushed=false` and 6 with `flushed=true`.
- [fact] The backlog is NOT undelivered. A title join against the vault found 224 of the 231 `flushed=false` records ALREADY present in `sessions/` by exact title; only 7 titles are absent, and 2 of those 7 are case-variants of each other, so at most 6 distinct files are genuinely missing on a case-insensitive filesystem. The records were delivered; the `flushed` write-back never persisted. The counter is lying, not the delivery.
- [bug] The refuted causal story - "basic-memory.exe was reinstalled 15 minutes after the last flush error, which is why 6 records flushed and the log stops" - is FALSE. The 6 `flushed=true` records carry mtimes 2026-09-03 13:24:41 to 13:26:02, twenty days BEFORE the 2026-09-23 22:24 reinstall. The reinstall produced zero flushes.
- [fact] No flush failure has been logged since 2026-09-23T22:09:55 while `flush-errors.log` sits at 74,217 B, far below its 200,000 B unlink cap - so the silence is not a log-rotation artifact.
- [fact] UNVERIFIED which of two candidate mechanisms holds: (a) the SessionStart drain never executes, or (b) it aborts after its FIRST record because the unguarded per-record `atomic_write_json` write-back raises inside the loop and the caller's bare `except Exception: pass` swallows it. Settling experiment: copy `bm-spool` to a scratch directory, point the harness state root at it, run the dispatcher for one SessionStart, and see whether exactly one record's mtime changes (abort-after-one) or none (never executes).
- [decision] REJECTED using `bm-spool` as the backfill vehicle. The reason is NOT a spawn tax - that claim rested on the refuted mechanism. The valid ground is that its records are 416-byte receipts that fail `memory-contract.md:50` outright, so routing real notes through it would queue durable knowledge behind worthless stubs.
- [decision] The routed fix is therefore "make the delivery receipt persist", not "cap the drain": guard the per-record write-back inside the loop so one failure cannot silently abort the drain, and reconcile the existing 231 records against the vault once so the counter stops lying. A newest-first cap would have permanently stranded the <=6 genuinely undelivered records while leaving the real defect unnamed. This file is outside the backfill kit's ownership and is flagged for routing, not edited here.

## Transport reading

- [decision] The `basic-memory` CLI's `tool write-note` is a CONTRACT-COMPLIANT transport, not a HARD-rule breach. `memory-contract.md:11` names MCP HTTP at `http://127.0.0.1:18765/mcp` as the only transport, and its explicit prohibitions are "never uvx/npx/pip stdio spawn" and "never bind :18765 yourself". The CLI does neither: it imports the MCP tool in-process and drives it over an in-process ASGI transport, binding no port and spawning no server. It also satisfies the G-81 writer lock, because it IS `write_note`.
- [fact] The estate's own production flusher already shells this exact CLI form from the hook path, so this backfill invents no new transport - it reuses the precedent.
- [fact] The CLI write form is known to work on this host: vault session notes produced by it landed on 09-24, three times on 09-25, on 09-28, and at 2026-09-29 05:51:55. UNVERIFIED by the reviewing pass whether a 14-note batch succeeds, because the CLI was deliberately not invoked during review.

## Index

- [fact] The 13 content notes: Horezu management document programme; Fusi VPCA psychometric standardization; Opus 5.5 classifier fallback is account state; MCP fleet process shape HOME 28 vs VM 88; Context and prompt cache audit; Home rclone serve outage root cause; Gem hunt 216 finding triage; Effort config fix unblocked sota synthesis; Personal records and CV corpus reorganization; OPEN-LOOPS register audit 30 items; Self removing retry task runaway; WebCoder momentstudio VPS deploy lane; CV design system round 3 selection.
- relates_to [[Harness reconcile offload-w2025 2026-09-23]]
- relates_to [[Research coverage register register 5 of 5 built 2026-09-25]]
See also [[VM harness backup vm-backup-2026-09-25]].
<!-- backfill-id: L6-BF-14 src: index note; sources = every .remember/today-*.md in the window plus the measured sha256: d503ac0354eb -->
