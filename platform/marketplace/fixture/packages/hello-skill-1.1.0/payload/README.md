# hello-skill 1.1.0 (beta)

Same package, newer version, `beta` channel.

Two things are proven with it:

1. **Channel filtering is a filter, not a fallback.** Resolving `hello-skill` on `stable` must
   return 1.0.0 even though 1.1.0 is newer. A resolver that "helpfully" fell through to beta would
   be the silent-widening defect this build refuses to reproduce.
2. **Update then rollback.** `mkt update` moves the site to 1.1.0 and records the previous version
   in the install receipt; `mkt rollback` returns to 1.0.0 by replaying that record — re-running
   every gate on the way back.
