# P2-STATE — state of record copied from the live ~/.agents at capture time (02.09.2026 06:1x EEST)

- `P2-REPAIR-PROGRESS_2026-08-27.md` — the append-only P2 (G-1) repair ledger, including the 02.09
  02:28 strategy switch, the 893-fail overlay and the resume instructions.
- `HANDOFF-CLOUD-AGENT_2026-09-02.md` — the stage-0/stage-1 handoff written by the capture workers.

Stage 1 (capture) was completed by the owner-side session on 02.09.2026 with
`scripts/sync-from-live.ps1 -Only ast-integrate`; see `../CAPTURE-EXCLUSIONS.md` for what is and is
not in this tree. The cloud P2 worker appends its own ledger sections under this folder and commits
them with the repairs; the live files above are frozen and must not be edited from the cloud.
