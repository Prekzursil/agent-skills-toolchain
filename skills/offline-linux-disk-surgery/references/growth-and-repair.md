---
title: growth-and-repair
type: note
permalink: dqverify-repo-20261013/skills/offline-linux-disk-surgery/references/growth-and-repair
---

# Growth And Repair

Typical ext4 growth sequence:

1. attach disk image
2. inspect layout with GPT-aware tooling
3. expand backing disk if required
4. resize target partition
5. run `e2fsck` when needed
6. run `resize2fs`
7. mount and verify paths
8. detach cleanly

Preserve evidence such as `lsblk`, partition tables, and filesystem UUIDs before changes.