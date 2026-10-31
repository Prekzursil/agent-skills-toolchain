---
permalink: memory://estate/ancestry-is-not-delete-auth
title: Commit ancestry is not delete authorization
tags: [teardown, worktree, ancestry, squash-merge, salvage]
valid_as_of: 2026-08-06
---

Commit ancestry is not delete authorization on this estate. A fully merged
squash-merge still reports AHEAD, so `git merge-base --is-ancestor` cannot
authorise teardown. Require merged-PR state or byte-level content comparison.
