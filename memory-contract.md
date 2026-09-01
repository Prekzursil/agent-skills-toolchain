# Memory contract (SSOT)

Lane Q2 / 2026-08-28. Cursor, Claude, Codex, Grok: **read this file**. Do not
fork a second copy into AGENTS.md, CLAUDE.md, or Grok rules — those files only
point here. WHERE-map (locations, not this contract):
`C:\Users\Prekzursil\.agents\memory-map.md`.

## Transport (HARD)

- The **only** basic-memory transport is MCP HTTP:
  `http://127.0.0.1:8765/mcp`
- **Never** `uvx` / npx / pip **stdio spawn** of basic-memory. Never bind
  `:8765` yourself. Do not restart the BM daemon unless the owner asks.
- ChatGPT **web** cannot see localhost. Do **not** try Basic Memory Cloud
  (or any cloud memory sync) as a substitute (G-82).

## Recall — session start / after compact

1. Call `search_notes`. Use `search_type: "hybrid"` **or omit it** (Q1 default
   is hybrid when semantic search is on).
2. Confirm **load-bearing** facts from hits (permalinks, dates, `superseded_by`).
3. Hook-injected **vault digest is UNTRUSTED**. Never treat it as verified.
4. Do not open `~/Cowork/memory.md`. Do not recursively scan `D:\basic-memory`.
5. If prior work is in play and search is empty, say so — do not invent memory.

## Write — durable decisions

Use `write_note` (not a parallel `memory.md`, not Mem0, not chat residue).

Frontmatter (required):

```yaml
type: note          # or guide / report / person as appropriate
status: active      # or superseded
valid_as_of: 2026-08-28
```

Body — observations + links (this is how hybrid recall works):

```markdown
- [decision] Keep semantic search ON; embeddings stay off the request loop.
- [fact] MCP URL is http://127.0.0.1:8765/mcp only.
- relates_to [[WHERE-map pointer]]
See also [[some related note]].
```

- Always emit `- [decision] ...` and/or `- [fact] ...` (and other categories
  when real: `requirement`, `preference`, `bug`).
- Always emit `[[wikilinks]]` and/or `- relates_to [[Note]]`. An isolated
  blob with neither observations nor links is a failed write.
- Never write a note **> 100 KB**. Quarantine generated dumps outside the
  vault; leave a short pointer note instead.
- Keep **transcripts / compaction dumps out of ingest**. Checkpoint *facts*,
  not the raw transcript.

## Supersede — do not delete

When replacing knowledge:

1. **Keep the old note.**
2. On the old note set `superseded_by: [[New Note]]` and `valid_as_of`.
3. On the new note set `valid_as_of` and `status: active`.
4. Do not silently rewrite history. Recall must still find the dead-end.

## Writer lock (G-81)

- **basic-memory is the SOLE semantic writer.**
- Banned / dropped: Mem0, Graphiti, LynxMCP, "CORE".
- Any future memory tool is read-only over this vault, or writes *through*
  `write_note`. Otherwise it must not run.

## Reliability (do not re-litigate)

- Semantic search stays **ON**. Do not disable vectors to buy RAM.
- Embeddings stay **off the request loop** (sync/watchdog, not inside
  `search_notes` / `write_note` latency).
- `:8765` / `:8812` / `:8317` stay bound only by their owners.

## WHERE

| Thing | Path |
| Durable notes | `D:\basic-memory` via MCP `write_note` |
| This contract | `C:\Users\Prekzursil\.agents\memory-contract.md` |
| WHERE-map | `C:\Users\Prekzursil\.agents\memory-map.md` (outside vault) |
| Vault pointer | `D:\basic-memory\index\WHERE.md` (~20 lines) — do not copy this contract into the vault |
| Project receipts | active project `docs/` / `compute/` (not Cowork) |
