#!/usr/bin/env python3
"""Disposable schema+launcher corpus and numbered migrations for IMP-0477."""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA_REL = "schemas/widget.schema.json"
LAUNCHER_REL = "launchers/widget_launch.py"
NOTES_REL = "notes.txt"
FROZEN_RELS = [SCHEMA_REL, LAUNCHER_REL]
MIG_ID = "0001_add_description"

WIDGET_V1 = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "widget",
    "schema_version": 1,
    "type": "object",
    "required": ["id"],
    "properties": {"id": {"type": "string"}},
}

UP_PY = '''#!/usr/bin/env python3
"""0001 up: add description field and bump schema_version 1 -> 2."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    root = Path(ap.parse_args().root)
    schema_path = root / "schemas" / "widget.schema.json"
    doc = json.loads(schema_path.read_text(encoding="utf-8"))
    props = dict(doc.get("properties") or {})
    props["description"] = {"type": "string"}
    doc["properties"] = props
    doc["schema_version"] = 2
    schema_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\\n", encoding="utf-8"
    )
    launch = root / "launchers" / "widget_launch.py"
    launch.write_text(
        "#!/usr/bin/env python3\\nprint(\\"widget v2\\")\\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

DOWN_PY = '''#!/usr/bin/env python3
"""0001 down: restore widget schema/launcher to v1 bytes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    root = Path(ap.parse_args().root)
    schema_path = root / "schemas" / "widget.schema.json"
    doc = json.loads(schema_path.read_text(encoding="utf-8"))
    props = dict(doc.get("properties") or {})
    props.pop("description", None)
    doc["properties"] = props
    doc["schema_version"] = 1
    schema_path.write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\\n", encoding="utf-8"
    )
    launch = root / "launchers" / "widget_launch.py"
    launch.write_text(
        "#!/usr/bin/env python3\\nprint(\\"widget v1\\")\\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''

NOOP_DOWN_PY = '''#!/usr/bin/env python3
"""Broken down-step: does not restore original bytes."""
from __future__ import annotations

import argparse


def main() -> int:
    argparse.ArgumentParser().add_argument("--root", required=True).parse_args()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(root: Path) -> dict[str, str]:
    root = Path(root)
    schema_path = root / SCHEMA_REL
    _write(
        schema_path,
        json.dumps(WIDGET_V1, indent=2, sort_keys=True) + "\n",
    )
    _write(root / LAUNCHER_REL, "#!/usr/bin/env python3\nprint(\"widget v1\")\n")
    _write(root / NOTES_REL, "scratch notes; not in the freeze set\n")
    return {
        "schema": SCHEMA_REL,
        "launcher": LAUNCHER_REL,
        "notes": NOTES_REL,
    }


def write_migration(
    root: Path,
    *,
    mig_id: str = MIG_ID,
    include_down: bool = True,
    broken_down: bool = False,
) -> Path:
    mig_dir = Path(root) / "migrations" / mig_id
    mig_dir.mkdir(parents=True, exist_ok=True)
    number = int(mig_id.split("_", 1)[0])
    manifest: dict = {
        "id": mig_id,
        "number": number,
        "from_version": 1,
        "to_version": 2,
        "targets": [SCHEMA_REL, LAUNCHER_REL],
        "up": "up.py",
    }
    _write(mig_dir / "up.py", UP_PY)
    if include_down:
        manifest["down"] = "down.py"
        _write(mig_dir / "down.py", NOOP_DOWN_PY if broken_down else DOWN_PY)
    _write(mig_dir / "MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return mig_dir
