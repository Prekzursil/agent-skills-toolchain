#!/usr/bin/env python3
"""golden journey 3: checksum the golden skill body."""
import hashlib, json, sys
from pathlib import Path
kit = Path(sys.argv[1]); out = Path(sys.argv[2])
raw = (kit / "skills" / "skill.golden" / "SKILL.md").read_bytes()
marker = b"GOLDEN-SKILL-BODY-CHECKSUM-TARGET"
lines = raw.decode("utf-8").splitlines()
out.write_text(json.dumps({"journey": "skill-checksum", "skill": "skill.golden", "kit": kit.name,
                           "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                           "line_count": len(lines), "front_matter_lines": 3,
                           "marker_present": marker in raw,
                           "marker_offset": raw.find(marker)}, indent=1), encoding="utf-8")
print("SKILL-CHECKSUM-WRITTEN")
