---
name: offline-linux-disk-surgery
description: Use when a Linux guest disk must be inspected, grown, or repaired offline with qemu-nbd, guestfish, GPT tools, e2fsck, or resize2fs instead of booting a broken or risky guest.
---

# Offline Linux Disk Surgery

## Overview

Perform guest-disk work offline when booting the guest would add risk or hide the failure. Treat partition edits and filesystem growth as surgery: verify the device, preserve rollback, and make one bounded change at a time.

## Reference Map

- Read [references/growth-and-repair.md](references/growth-and-repair.md) for the standard resize flow.
- Read [references/stop-rules.md](references/stop-rules.md) before touching GPT, filesystems, or guest homes.

## Required Discovery

1. Identify the disk image format and current size.
2. Confirm partition layout before issuing any GPT or filesystem command.
3. Decide whether the goal is inspection, growth, fsck, or content restore.
4. Preserve the pre-change guest state, especially any existing home directory.

## Standard Flow

1. Attach the disk read-only first if feasible.
2. Inspect partition and filesystem state.
3. Expand the backing disk only if the target filesystem needs more space.
4. Resize partition, then grow the filesystem.
5. Mount and verify the expected paths before detaching.

## Stop Rules

- Do not run partition commands until the device path is verified twice.
- Do not skip `e2fsck` when the filesystem state is suspect.
- Do not overwrite an existing guest home when a rename-and-restore path is available.

## Common Mistakes

- Growing the virtual disk but forgetting the partition or filesystem.
- Editing the wrong block device after multiple attachments.
- Mixing inspection and restore work without a checkpoint.
