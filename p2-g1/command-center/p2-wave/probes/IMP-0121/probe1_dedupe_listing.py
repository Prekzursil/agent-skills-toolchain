"""IMP-0121 probe 1 (source): two puts of identical bytes with distinct refs
yield ONE on-disk object and refcount 2; a distinct payload adds a second object.

Re-run: python command-center/p2-wave/probes/IMP-0121/probe1_dedupe_listing.py
Exit 0 iff dedupe, listing and refcounts hold.
"""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
sys.path.insert(0, str(W / "tools" / "marketplace"))
from blob_store import BlobStore, list_object_files, load_index_file, refcount_from_index  # noqa: E402

root = Path(tempfile.mkdtemp(prefix="imp0121-probe1-"))
try:
    store = BlobStore(root)
    payload_a = b"identical-payload-IMP-0121"
    payload_b = b"distinct-payload-IMP-0121"
    d1 = store.put(payload_a, ref="collection:core")
    d2 = store.put(payload_a, ref="version:1.0.0")
    listing = [p.name for p in list_object_files(root)]
    index = load_index_file(root)
    rc = refcount_from_index(index, d1)
    store.put(payload_b, ref="version:2.0.0")
    listing2 = [p.name for p in list_object_files(root)]
    refs = sorted(index["objects"][d1]["refs"].keys())
    result = {
        "put_twice_same_digest": d1 == d2,
        "digest": d1,
        "directory_listing": ["objects/" + n for n in listing],
        "object_file_count": len(listing),
        "index_refcount": rc,
        "index_refs": refs,
        "object_file_count_after_distinct": len(listing2),
        "other_digest": hashlib.sha256(payload_b).hexdigest(),
        "unit_id": "IMP-0121",
    }
    result["pass"] = (
        result["put_twice_same_digest"]
        and result["object_file_count"] == 1
        and rc == 2
        and result["object_file_count_after_distinct"] == 2
    )
finally:
    shutil.rmtree(root, ignore_errors=True)

print(json.dumps(result, indent=1))
print("listing=%s files=%d refs=%s refcount=%d" % (
    result["directory_listing"], result["object_file_count"],
    result["index_refs"], result["index_refcount"]))
if result["pass"]:
    print("SUCCESS:IMP-0121-probe1 one on-disk object for two puts of identical bytes")
else:
    print("FAILED:IMP-0121-probe1")
sys.exit(0 if result["pass"] else 1)
