---
title: Owner prefers MAXIMAL statusline visibility, not minimalism
type: feedback
permalink: main/feedback/owner-prefers-maximal-statusline-visibility-not-minimalism
tags:
- statusline
- feedback
- ux
- visibility
- preference
---

Durable preference, learned 2026-07-24 during the statusline rebuild.

## Observations

- [preference] The owner wants the statusline to SHOW quota/cost/identity info ALWAYS, at a glance — not hidden by "silent-until-threshold" gating. #maximal-visibility — In the grill I chose (and they accepted) a minimalist "silent-until-relevant" design (weekly gated to >70% used, cost cut, auth demoted to non-default-only). Using it live, they pushed back twice: "5h usage and weekly usage are no longer here, what else is not here?" then "i need auth cost weekly and 5 hours limit duration". Restored all always-on.

- [gotcha] A threshold-gate at a boundary the value HOVERS near reads as "broken/flickering", not "smart". #threshold-flicker — Weekly gated at >70% used while the owner sat at exactly 70% → it flickered in/out and looked gone. Gating hides exactly when the value is most interesting to watch.

- [decision] Statusline default: auth (always), model, session, goal on L1; ctx, $cost, session-duration, 5h (%left + countdown), weekly (%left), ag, mem, git on L2. Keep threshold COLOUR (amber/red when high) but ALWAYS display the number. #statusline-layout — Colour for alarm is good; hiding the datum is not. The grill's alarm-fatigue argument applies to COLOUR, not to whether the number is shown.

- [pattern] When a grill decision meets live use, the owner's lived reaction OVERRIDES the abstract argument. #human-review-wins — Same lesson as the ag:1⚠704m confusion: a design defensible in theory (minimalism, alarm-fatigue) was wrong for this operator's actual daily-driver taste. Ship, then let them see it, then adjust to what they say — don't defend the grill decision.

## Relations
- relates_to [[Statusline REBUILD 2026-07-24]]
- relates_to [[Statusline rebuild — process/meta learnings (2026-07-24)]]
