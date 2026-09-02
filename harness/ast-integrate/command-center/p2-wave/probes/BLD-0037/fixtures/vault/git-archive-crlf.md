---
permalink: memory://estate/git-archive-crlf-trap
title: git archive returns CRLF worktree bytes, not the LF blob
tags: [git-archive, CRLF, cat-file, provenance, windows]
valid_as_of: 2026-08-06
---

On this box, `git archive | tar -x` returns CRLF worktree bytes (measured
3,837 bytes / 100 CRLF) while `git cat-file -p <rev>:<path>` and `git show`
return the stored LF blob (3,737 bytes / 0 CRLF). Any recipe that verifies
formatting or hashes via git archive manufactures false confidence. Compare
against the committed blob via git cat-file, never via git archive.
