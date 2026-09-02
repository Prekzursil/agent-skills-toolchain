---
description: Verify a claimed fix
---

1. Re-run the failing probe that motivated the change.
2. Run one adjacent probe that should still pass.
3. Gate: the original probe must go from fail to pass on disk.
