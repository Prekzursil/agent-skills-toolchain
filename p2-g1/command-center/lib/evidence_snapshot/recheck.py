import importlib.util as _ilu
import os as _os
import sys as _sys

_here = _os.path.dirname(_os.path.abspath(__file__))
try:
    from . import store
except ImportError:
    _spec = _ilu.spec_from_file_location("res0004_store", _os.path.join(_here, "store.py"))
    store = _ilu.module_from_spec(_spec)
    _sys.modules["res0004_store"] = store
    _spec.loader.exec_module(store)


def _anchor_present(entry, body):
    quote = entry.get("quote")
    if quote and quote not in body:
        return False
    for marker in entry.get("js_markers") or []:
        if marker not in body:
            return False
    return True


def classify(entry, current_body):
    p = store.blob_path(entry)
    stored = p.read_bytes()
    if store.sha_bytes(stored) != entry["sha256"]:
        return "SNAPSHOT-CORRUPT"
    if store.sha_bytes(current_body) != entry["sha256"]:
        return "SOURCE-CHANGED"
    if not _anchor_present(entry, current_body.decode("utf-8", "replace")):
        # distinguish a recorded claim from a snapshot with no anchors
        if entry.get("quote") or entry.get("js_markers"):
            return "CLAIM-WAS-WRONG"
        return "CLAIM-HOLDS"
    return "CLAIM-HOLDS"
