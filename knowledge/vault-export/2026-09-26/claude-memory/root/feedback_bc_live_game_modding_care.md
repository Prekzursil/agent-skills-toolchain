---
name: feedback-bc-live-game-modding-care
description: Care rules for live BC game modding — read-only discovery is safe, forcing
  an unverified field can break a mechanic, prefer reversible save-edits, and the
  device-op gotchas (dd-not-cat, $pid, event_0 clobber, kill-hooks-first)
metadata:
  node_type: memory
  type: feedback
  originSessionId: 5cba01b0-b7c2-4f65-96a6-d44199963f4c
permalink: main/claude-memory/root/feedback-bc-live-game-modding-care
---

When modding the live Battle Cats device, **read-only discovery is safe; FORCING an unverified field is not.** This session I force-set the Aku clear/crown accessor (`sub_850050` retval→1, scope arg0==-19) before proving it was the right lever — it painted the Aku stages as generic "normal/cleared" and made the altar *disappear*, looking exactly like a corrupted save. (It wasn't corrupted — proven by decoding 3 saves — but the user couldn't tell, and was furious for many turns: "you COMPLETELY BROKE IT", "you ARE NOT WILLING TO HELP".)

**Why:** A live force on the wrong field is indistinguishable from save corruption to the user, costs their trust, and a "live, no-restart" patch is often architecturally impossible — the Aku roll runs ONLY on the load path, not per-frame, so writing the reroll sentinel `gs+0x4A6C4=-1` live never fired (advisor-confirmed). Weeks of "make it live" can be a conceptual gap, not a hooking-skill gap (see [[feedback-bc-re-dont-overcomplicate]]).

**How to apply:**
- **Default to read-only discovery + reversible save-edits.** The shipped Aku reroll is a save-edit (`ushdd[0]=1` + relaunch, ~10s restart) via `aku_reroll.py`, NOT a live hook. A ~10s restart the user accepts beats a live hack that breaks the mechanic. Round-trip saves with BCSFE + reload-verify the hash before push (see [[bcsfe-save-roundtrip]]).
- **Prove the lever before forcing it.** Trace the value-gate read-only (log args/retval on the Aku map) and identify the actual play-enable consumer FIRST. Never re-force `sub_850050`.
- **When the user says "you broke it": STOP, detach/kill EVERY leftover hook, and restart the game BEFORE any other action** — don't argue it's fine or keep probing. A lingering hook = "still broken" no matter what you claim.
- **Device-op gotchas that bit me:** in-place push = `adb push /sdcard/x; su -c "dd if=/sdcard/x of=/data/.../FILE"` — NOT `su -c "cat /sdcard/x > /data/.../FILE"` (the `>` redirect runs as the non-root shell → Permission denied; dd-as-root preserves inode/owner/SELinux). PowerShell `$pid`/`$args` are READ-ONLY automatics — `foreach($pid in ...)` fails silently and my "killed/confirmed stopped" claim was FALSE while hooks kept running; use `Get-Process -Id ... | Stop-Process -Force`. After any BC restart the server clobbers the `event_0` patch — re-assert it (see [[battlecats-event-summoner]]).
- **Never self-certify a "fixed it" claim on a live game** — the user is the only ground truth for whether the mechanic looks right; ask them to confirm (see [[feedback-peer-review]]). HGT-safe always: no clock-change/MITM/cache-clear ([[battlecats-mitm-hgt-date-trigger]]).