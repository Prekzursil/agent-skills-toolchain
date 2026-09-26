---
name: feedback-bc-re-dont-overcomplicate
description: When BC (or similar) RE stalls for weeks, suspect a conceptual gap (full
  data dependency) before reaching for more elaborate hooks — single-gate hooks are
  reliable here
metadata:
  node_type: memory
  type: feedback
  originSessionId: 5cba01b0-b7c2-4f65-96a6-d44199963f4c
permalink: main/claude-memory/root/feedback-bc-re-dont-overcomplicate
---

When a Battle Cats RE goal resists for weeks despite a working trainer, the bottleneck is almost always a **conceptual miss about the full data dependency**, not a hooking-skill gap. The user has stated this directly: "it feels like this is very easy but we are overcomplicating it very much" and "we managed the trainer and so" — i.e. they CAN do hard single-function RE; the failures were from attacking the wrong layer.

**Why:** The event/special-stage saga proved it. Weeks were lost forcing the render/display gate (`sub_817020`) and patching always-on sale.tsv rows — each addressing only HALF the requirement. The actual model is a **dual dependency**: a tile renders only with BOTH tree-admission (`sub_819E20`→tree `sub_5F8AC0`, built at launch by `sub_525AB0`) AND a valid schedule row. Once that was understood, the lever became a single scoped hook — exactly the kind the existing trainer already does reliably (e.g. `sub_8A3350`→0 / `sub_8A3520`→1). See [[battlecats-event-summoner]].

**How to apply:** Before building elaborate multi-hook machinery for a BC RE goal, (1) map the FULL dependency chain (what data + what gate + when populated) — render pipeline `sub_527270 → sub_525AB0 → sub_7F52D0`; (2) prefer ONE scoped single-function hook over blanket forces (blanket `0x5292e4` CRASHED); (3) treat naive time-travel as a trap (BC 15.3 Recovery/HGT — see [[battlecats_mitm_hgt_date_trigger]]); (4) validate read-only (probe) before mutating. Don't reach for a bigger hammer when the model is incomplete.