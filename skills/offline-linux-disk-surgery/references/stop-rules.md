---
title: stop-rules
type: note
permalink: dqverify-repo-20261013/skills/offline-linux-disk-surgery/references/stop-rules
---

# Stop Rules

- Stop if the disk identity is ambiguous.
- Stop if the filesystem type is not what you expected.
- Stop if the only safe rollback copy is about to be modified.
- Stop if the mounted filesystem view does not match the intended guest root.