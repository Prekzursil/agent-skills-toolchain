---
permalink: memory://estate/squash-merge-branch-reporting
title: Squash-merge makes a fully merged branch report as AHEAD
tags: [squash-merge, git, branch-inventory, merge-state, teardown]
valid_as_of: 2026-08-06
---

Measured on this estate: a squash-merged feature branch still reports AHEAD
against main when classified by commit ancestry. The three-dot range is not
a delete authorisation. Teardown and abandoned-work salvage must require a
merged-PR state or a byte-level content comparison. Ancestry-only detectors
are the known wrong instrument.
