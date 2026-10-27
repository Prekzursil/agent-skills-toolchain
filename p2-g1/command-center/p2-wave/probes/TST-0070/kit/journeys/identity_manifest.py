#!/usr/bin/env python3
"""golden journey 2: identity manifest of every file in the kit."""
import hashlib, json, sys
from pathlib import Path
kit = Path(sys.argv[1]); out = Path(sys.argv[2])
rows = []
for f in sorted(kit.rglob("*")):
    if f.is_file():
        raw = f.read_bytes()
        rows.append({"path": f.relative_to(kit).as_posix(), "bytes": len(raw),
                     "sha256": hashlib.sha256(raw).hexdigest()})
out.write_text(json.dumps({"journey": "identity-manifest", "kit": kit.name, "files": rows,
                           "count": len(rows)}, indent=1), encoding="utf-8")
print("IDENTITY-MANIFEST-WRITTEN")
