---
description: Start a bounded task with an explicit gate
argument-hint: [task]
allowed-tools: Read, Edit, Bash
---

1. Name the task, the owner, and the stop condition before any edit.
2. Inventory the files that will change and refuse unbounded scope.
3. Execute the smallest change that meets the stop condition.
4. Gate: do not claim done until the stop condition is observed on disk.
