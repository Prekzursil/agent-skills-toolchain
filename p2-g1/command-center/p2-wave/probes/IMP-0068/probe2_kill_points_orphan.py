#!/usr/bin/env python3
"""IMP-0068 probe2: kill-point campaign + orphan reviewer obligation.

Campaign uses a DIFFERENT seed and a fat index (independent of the unittest
file): an atomic index write interrupted at every seeded offset leaves the
destination a COMPLETE document (old or new, never a partial); the same
offsets against an in-place publisher leave a readable partial. The
reviewer obligation - rebuild against blobs missing an index entry - is
re-exercised with a second, differently-designed orphan.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "marketplace"))

from storage import RegistryStorage, indexes_semantically_equal  # noqa: E402

FAT = [
    {"name": "fat-%02d" % i, "version": "1.%d.0" % i,
     "summary": "fat package number %d with a longer summary line" % i}
    for i in range(40)
]


def in_place_publish(index_path: Path, doc: dict, kill: int) -> None:
    payload = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    with open(index_path, "wb") as fh:
        fh.write(payload[:kill])


def main() -> int:
    checks = {}
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        st = RegistryStorage(root)
        for i, p in enumerate(FAT):
            st.put_package(p, ("fatblob-%02d\n" % i).encode())
        original = st.read_index()
        new_doc = json.loads(json.dumps(original))
        new_doc["plugins"][0]["summary"] = "replaced-by-campaign"
        payload = json.dumps(new_doc, indent=2) + "\n"
        kill_offsets = sorted({len(payload) // 7, len(payload) // 4,
                               len(payload) // 2, 3 * len(payload) // 5,
                               len(payload) - 2, len(payload) + 5})
        real_write_text = pathlib.Path.write_text
        dest_was_partial = False
        for k in kill_offsets:
            st2 = RegistryStorage(root)

            def boom(self_, data, *a, **kw):
                if str(self_).endswith("index.json.tmp") and len(data) > k:
                    raise RuntimeError("kill at %d" % k)
                return real_write_text(self_, data, *a, **kw)

            pathlib.Path.write_text = boom  # type: ignore[attr-defined]
            try:
                try:
                    st2._write_index(new_doc)
                except RuntimeError:
                    pass
            finally:
                pathlib.Path.write_text = real_write_text  # type: ignore[attr-defined]
            try:
                parsed = json.loads(st2.index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                dest_was_partial = True
                break
            if parsed not in (original, new_doc):
                dest_was_partial = True
                break
        checks["atomic_dest_never_partial"] = not dest_was_partial
        in_place_partial = False
        for k in kill_offsets:
            in_place_publish(st.index_path, new_doc, k)
            try:
                json.loads(st.index_path.read_text(encoding="utf-8",
                                                   errors="replace"))
            except json.JSONDecodeError:
                in_place_partial = True
                break
        checks["inplace_counterexample_fires"] = in_place_partial
        st.rebuild_from_blobs()
        stem = "d" * 64
        (st.blob_dir / (stem + ".json")).write_text(
            json.dumps({"name": "reviewer-orphan-qkv", "version": "1.0.0"},
                       sort_keys=True) + "\n", encoding="utf-8")
        (st.blob_dir / (stem + ".bin")).write_bytes(b"reviewer-orphan\n")
        names_before = {p["name"] for p in st.read_index()["plugins"]}
        names_after = {p["name"] for p in st.rebuild_from_blobs()["plugins"]}
        checks["orphan_absent_before"] = "reviewer-orphan-qkv" not in names_before
        checks["orphan_recovered"] = "reviewer-orphan-qkv" in names_after
    verdict = "PASS" if all(checks.values()) else "FAIL"
    out = {
        "probe": "probe2-kill-points-orphan",
        "unit_id": "IMP-0068",
        "checks": checks,
        "reviewer": {
            "reviewer_id": "IMP-0068-probe2-kill-points-orphan",
            "obligation": "rebuild exercised against blobs missing an index entry",
            "verdict": verdict,
            "independent": True,
        },
        "pass": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not all(checks.values()):
        bad = [k for k, v in checks.items() if not v]
        print("FAILED:IMP-0068-probe2 %s" % bad)
        return 1
    print("SUCCESS:IMP-0068-probe2 kill-point campaign clean, orphan rebuild proven")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
