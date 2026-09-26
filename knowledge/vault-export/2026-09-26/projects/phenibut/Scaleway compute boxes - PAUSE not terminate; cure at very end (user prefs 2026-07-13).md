---
title: Scaleway compute boxes - PAUSE not terminate; cure at very end (user prefs
  2026-07-13)
type: note
permalink: main/projects/phenibut/scaleway-compute-boxes-pause-not-terminate-cure-at-very-end-user-prefs-2026-07-13
tags:
- phenibut
- scaleway
- workflow
- user-preference
- schrodinger-install
---

# Scaleway compute boxes: PAUSE (stop), don't TERMINATE; apply cure at the very end

**User preference (2026-07-13, feedback):** for the phenibut Scaleway compute boxes, **PAUSE (stop) the instance instead of terminating it** when a campaign finishes.
**Why:** terminating destroys the Schrodinger install (14 GB installer upload + ~1 h INSTALL + license cure); pausing keeps the root volume + install so the next campaign just resumes — "its easier than reconfiguring a new instance everytime."
**How to apply:** after a compute campaign, run `scw instance server stop <id> zone=fr-par-2` (NOT `terminate`). Compute billing stops; block-storage billing continues (the root volume persists). Resume with `scw instance server start <id>`. Caveat: a stopped GPU instance may fail to restart if GPU capacity is unavailable at start (4xH100 is the only available tier; H100-SXM-8-80G is quota-blocked 0/0). This SUPERSEDES the earlier "always teardown/terminate after extracting results" rule for these research boxes.

**Second preference (2026-07-13):** apply the **license cure (patched libmmfileshared.so md5 a34a793bd05237c30f8cdc4ac750d290 + 26-2.lic) at the VERY END, after the full INSTALL completes** — never mid-install (the installer could overwrite the patched .so). Sequence: unzip -> INSTALL -b all products -> verify complete -> THEN cure.sh. Relates to [[N4 WaterMap result - Cl-over-H GABA-B gap is ELECTRONIC not desolvation]] (the fresh-install recipe).