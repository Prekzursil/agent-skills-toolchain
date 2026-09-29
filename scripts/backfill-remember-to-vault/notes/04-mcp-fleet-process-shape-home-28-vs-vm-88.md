---
type: note
status: active
valid_as_of: 2026-09-29
---

- [decision] HOME is the reference architecture for MCP process SHAPE, not the VM. HOME runs 28 servers via HTTP hubs plus direct stdio and no npx; the VM runs 88 servers where each npx entry fans out to about 6 processes, with duplicate supervisors and case-collision keys on top. The server COUNT is a symptom; the launch shape is the cause.
- [fact] Measured process pressure on the VM crossed the 150-process hygiene threshold repeatedly in one day: 354 MCP processes at one reading, 320 at another, and 90 npx processes traced as a single root cause.
- [fact] The RAM audit instrument was itself broken and was reporting 0 GB and 1 command line. Three bugs were fixed in `mcp_ram_audit.ps1` - the wrong process-memory property, a grouping-key truncation, and unhandled case-collision keys - after which the same fleet measured 20.5 GB across 91 command lines (commit d375dc0df). Every fleet number taken before that fix is unusable.
- [fact] The estate relationship is HOME subset-of VM with 60 VM-only servers, and an earlier "the estate is broken" finding was OVERTURNED to "the VM is broken, not the estate" once HOME was measured directly: 109 processes, 7.66 GB, 11 of 12 endpoints up.
- [decision] The npx-to-direct rewrite is the durable fix (7 servers rewritten, 9 found misplaced), and it is applied with race-condition protection rather than by hand-editing a live `.claude.json` while `claude.exe` instances hold it open.
- [fact] A cross-surface count of 88 Claude / 13 Codex / 8 Cursor entries exposed 2 wire contradictions between what a config declared and what was actually listening.
- relates_to [[Harness reconcile offload-w2025 2026-09-23]]
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
<!-- backfill-id: L6-BF-04 src: .remember/today-2026-09-25.done.md 14:22, 16:11, 16:23, 16:46, 18:26, 20:24, 20: sha256: 6ecb9f570e6a -->
