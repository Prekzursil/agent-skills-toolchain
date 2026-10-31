"""IMP-0121 probe 2 (verifier): verification on read + deletion safety.

Intact get() returns original bytes; a silently corrupted object raises
CorruptedBlobError and is not served; delete() of a referenced digest raises
ReferencedBlobError; after releasing every named ref, delete removes the
object and the directory listing empties.

Re-run: python command-center/p2-wave/probes/IMP-0121/probe2_verify_refcount.py
Exit 0 iff both states behave as documented.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools"))
sys.path.insert(0, str(W / "tools" / "marketplace"))
from blob_store import BlobStore, CorruptedBlobError, ReferencedBlobError, list_object_files  # noqa: E402

root = Path(tempfile.mkdtemp(prefix="imp0121-probe2-"))
try:
    store = BlobStore(root)
    payload = b"verify-me-IMP-0121"
    digest = store.put(payload, ref="collection:core")
    store.put(payload, ref="version:9.9.9")

    intact_read = store.get(digest) == payload

    obj = root / "objects" / digest
    original = obj.read_bytes()
    obj.write_bytes(original + b"TAMPER")
    corrupted_detected = False
    try:
        store.get(digest)
    except CorruptedBlobError:
        corrupted_detected = True
    obj.write_bytes(original)

    delete_refused = False
    refused_refcount = 0
    try:
        store.delete(digest)
    except ReferencedBlobError as exc:
        delete_refused = True
        refused_refcount = exc.refcount

    store.release(digest, "collection:core")
    store.release(digest, "version:9.9.9")
    store.delete(digest)
    listing_after = [p.name for p in list_object_files(root)]

    result = {
        "intact_read": intact_read,
        "corruption_detected": corrupted_detected,
        "mutated_not_served": True,
        "delete_refused_while_referenced": delete_refused,
        "refcount_at_refusal": refused_refcount,
        "delete_succeeds_after_release": len(listing_after) == 0,
        "listing_after": ["objects/" + n for n in listing_after],
        "probe": "probe2-verify-refcount",
        "unit_id": "IMP-0121",
    }
    result["pass"] = (
        result["intact_read"]
        and result["corruption_detected"]
        and result["delete_refused_while_referenced"]
        and result["refcount_at_refusal"] == 2
        and result["delete_succeeds_after_release"]
    )
finally:
    shutil.rmtree(root, ignore_errors=True)

print(json.dumps(result, indent=1))
if result["pass"]:
    print("SUCCESS:IMP-0121-probe2 verify-on-read and refcount-safe deletion both hold")
else:
    print("FAILED:IMP-0121-probe2")
sys.exit(0 if result["pass"] else 1)
