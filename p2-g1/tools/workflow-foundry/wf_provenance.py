"""IMP-0155 deliverable: provenance records sufficient for independent re-fetch.

Every candidate carries a provenance record with enough information for a
SECOND agent (a fresh process that receives only the record, the workspace
root, and nothing else) to re-fetch the identical bytes. Acceptance is an
actual re-fetch whose hash reproduces the recorded hash - not an assertion
that the fields are present.

Re-fetch method is 'file-read' against the declared root: this lane re-fetches
in-repo candidates. A network fetch variant exists (fetch_file) for
http-declared records and is exercised by the mutated-ref detector.

Re-run: python tools/workflow-foundry/wf_provenance.py <record.json> <root>
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from pathlib import Path


def make_record(path: str, root: Path, note: str = "") -> dict:
    """Build a provenance record for an in-repo file, measuring bytes off disk."""
    p = Path(root) / path
    data = p.read_bytes()
    return {
        "path": path,
        "fetch": {"method": "file-read", "root": str(root)},
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "note": note,
    }


def refetch(record: dict, expected_sha: str | None = None) -> dict:
    """Re-fetch from the record ALONE and compare to the recorded hash.

    This is the second agent's move: it never sees the original file handle,
    only the record. Returns a verdict dict; 'ok' is True only when the bytes
    came back and hashed to the recorded value.
    """
    method = record["fetch"]["method"]
    try:
        if method == "file-read":
            data = (Path(record["fetch"]["root"]) / record["path"]).read_bytes()
        elif method == "http":
            with urllib.request.urlopen(record["fetch"]["url"], timeout=30) as r:
                data = r.read()
        else:
            return {"ok": False, "detail": f"unknown fetch method {method!r}"}
    except Exception as e:  # noqa: BLE001 - the failure IS the signal
        return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
    actual = hashlib.sha256(data).hexdigest()
    want = expected_sha if expected_sha is not None else record.get("sha256")
    ok = actual == want and len(data) == record.get("bytes", len(data))
    return {
        "ok": ok,
        "path": record["path"],
        "bytes": len(data),
        "sha256": actual,
        "recorded_sha256": want,
        "detail": "identical bytes re-fetched" if ok else "RE-FETCH MISMATCH",
    }


def refetch_many(records: list) -> dict:
    results = [refetch(r) for r in records]
    good = sum(1 for r in results if r["ok"])
    return {
        "sampled": len(results),
        "reproduced": good,
        "all_reproduced": good == len(results),
        "results": results,
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    records = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(refetch_many(records), indent=1))
