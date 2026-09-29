---
type: note
status: active
valid_as_of: 2026-09-29
---

- [fact] ROOT CAUSE of the 8.5 MB transfer truncation: HOME's `rclone serve` had been DEAD since 2026-09-23 23:01, killed by commit exhaustion - 113.2 GB committed against 31.6 GB of RAM. The mount side logged 337 and 305 could-not-connect errors, which is the signature of a dead listener, not of a killed client.
- [decision] The reaper is NOT the cause and must not be blamed for it. All five reapers were examined and cleared; their name and path filters cannot target an rclone process at all. A plausible suspect with means is not a suspect with evidence.
- [fact] Restart attempts stalled, so the outage persisted beyond its trigger: the process died from memory pressure but stayed dead because nothing successfully restarted it.
- [fact] HOME-to-VM parity is not achievable by copying: 56.8 GB against 4.4 GB. Attempting it is what generated the oversized transfers in the first place.
- [fact] Cost context for the VM lane over this window: about $1.40/hr, roughly $70 across 52.5 hours.
- relates_to [[VM harness backup vm-backup-2026-09-25]]
- relates_to [[Backfill provenance 2026-09-23 to 2026-09-29]]
<!-- backfill-id: L6-BF-06 src: .remember/today-2026-09-25.done.md 18:56, 19:18, 22:03, 22:13 sha256: f3327bcd5d73 -->
