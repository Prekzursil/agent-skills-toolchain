---
name: battlecats-mitm-hgt-date-trigger
description: Full MITM proxy (and .dat cache-clear) corrupts BC's date sync → triggers
  HGT recovery + 99-day half-XP penalty; deliver event unlocks by in-place event_0.dat
  edit, never via MITM/cache-clear.
metadata:
  node_type: memory
  type: feedback
  originSessionId: c5980bb4-6564-4a44-a055-9721b0720cee
permalink: main/claude-memory/root/battlecats-mitm-hgt-date-trigger
---

Delivering Battle Cats event-schedule edits via a **full MITM proxy** (mitmproxy intercepting all of BC's HTTPS) **corrupts BC's perceived date**: it also proxies the server-time endpoints (`nyanko-backups.ponosgames.com/.../action_getTime`, `/v1/notices` clientTime), and proxying them skews the time BC computes. `sub_525AB0`'s drift check (>10 min behind / >1.5 days ahead of the save's reference timestamp) then reads it as time-travel → **HGT recovery mode** (events, Catclaw Dojo, capsules all blank — even normally-always-on Championships) **+ a 99-day half-XP time-travel penalty**. Force-stop + delete the `.dat` cache + force-redownload trips the same recalc path → same HGT.

Confirmed empirically (2026-05-25): killing the MITM restored the correct date and cleared the symptoms ("now it works okay"). The user diagnosed it ("the man in the middle is somehow fucking the date") — they were right.

The event **date-widening / num_slots=0 row injection itself is HGT-orthogonal** — it flows through `sub_819E20`/`sub_817020`, not the timestamp check. The data was never the problem; the **delivery** was.

**Why:** HGT/recovery is enforced client-side off the local save's timestamp vs `system_clock::now()` (see [[battlecats-calendar-unlock-stack]] and the repo's `docs/research/2026-05-24-hgt-recovery-mechanism.md`). Anything that disturbs the time BC sees trips it; a 99-day half-XP penalty is a real, account-affecting consequence.

**How to apply:** Deliver event unlocks by **patching `event_0.dat` (`002a4b18244f32d7833fd81bc833b97f.dat`) in place** on disk: decrypt → inject `num_slots=0` always-on rows (the proven shape that passes `sub_817020`: `start 0 end 0 minver maxver 0 0 map_count mapid`) → re-encrypt (AES-128-ECB, key=hex(MD5("battlecats")[:8]), PKCS7, + 32-byte ASCII-MD5 footer) → overwrite in `/data/data/jp.co.ponos.battlecatsen/files/`. **No proxy on the time/save endpoints, no `.dat` cache clear, no device-clock change, no SAVE_DATA write.** If BC re-downloads and overwrites, block ONLY the event-data path — never the time/save endpoints.