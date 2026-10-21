#!/usr/bin/env python3
"""Build the per-unit UNIT-ARTIFACT-MANIFEST.json for one ADV unit.

Pattern: command-center/p2-wave/probes/ADV-0033/UNIT-ARTIFACT-MANIFEST.json
(structural-condition-11 option 1, sanctioned by
command-center/p2-next/OWNER-DECISION-condition-11.md Option B and
command-center/STRUCTURAL-CONDITION-11.md: a purpose-built manifest naming the
artifact + sha256 satisfies condition 11).

Digests are sha256 over CRLF-to-LF-normalized bytes, matching what
completion_predicate._c11_manifest compares.

Usage: python make_manifest.py ADV-0022 [extra supporting files...]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / 'command-center/WORK-UNIT-CATALOG.json'


def lf_digest(p: Path) -> tuple[str, int]:
    data = p.read_bytes().replace(b'\r\n', b'\n')
    return hashlib.sha256(data).hexdigest(), len(data)


def main() -> int:
    unit_id = sys.argv[1]
    supporting = [Path(a) if Path(a).is_absolute() else REPO / a for a in sys.argv[2:]]
    units = json.loads(CATALOG.read_text(encoding='utf-8'))['work_units']
    unit = next(u for u in units if u['id'] == unit_id)
    out_path = unit['output_path']

    entries = []
    primary = REPO / out_path
    sha, n = lf_digest(primary)
    entries.append({
        'path': out_path, 'sha256': sha, 'bytes': n, 'present': True,
        'unit_id': unit_id,
        'receipt_path': str(Path(__file__).resolve().parent.relative_to(REPO) / 'UNIT-ARTIFACT-MANIFEST.json'),
        'role': 'primary',
    })
    for s in supporting:
        sha, n = lf_digest(s)
        entries.append({
            'path': str(s.relative_to(REPO)), 'sha256': sha, 'bytes': n,
            'present': True, 'unit_id': unit_id,
            'receipt_path': str(Path(__file__).resolve().parent.relative_to(REPO) / 'UNIT-ARTIFACT-MANIFEST.json'),
            'role': 'supporting',
        })

    doc = {
        'artifacts': entries,
        'contract': 'completion-predicate-condition-11-unit-artifact-registration',
        'derivation': 'per-unit (not tools/command-center/unit_manifest.py --write)',
        'expected': len(entries),
        'present': len(entries),
        'schema_version': 1,
        'unit_id': unit_id,
        'verified_on_disk': True,
    }
    dest = Path(__file__).resolve().parent / 'UNIT-ARTIFACT-MANIFEST.json'
    dest.write_text(json.dumps(doc, indent=2) + '\n', encoding='utf-8', newline='\n')
    print('wrote', dest, 'with', len(entries), 'entries')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
