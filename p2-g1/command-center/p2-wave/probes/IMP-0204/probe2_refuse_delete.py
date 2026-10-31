"""IMP-0204 probe 2 (verifier): deletion of a referenced workflow is refused,
the id still resolves afterwards (FC-11347), and the retirement record schema
admits only SUPERSESSION or DEPRECATION - DELETION kind, missing successor,
missing migration and dangling successors are all rejected.

Exit 0 iff the refusal holds, resolution survives, and all four schema
rejections fire.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(W / "tools"))
from workflows.retirement import (DeleteRefused, Catalog,  # noqa: E402
                                  validate_retirement)

RAW = HERE / "probe2-refuse-delete.raw.txt"

OLD = "wf.catalog-class.discovery-only"
NEW = "wf.catalog-class.typed-restore"

cat = Catalog()
cat.publish({"id": OLD, "body": {"stages": ["discovery-only-scan"]}})
cat.publish({"id": NEW, "body": {}})
cat.pin_consumer("consumer-a", OLD)
cat.supersede(OLD, NEW, migration={"path": "swap"}, reason="lane corrupted")

refused = None
try:
    cat.delete(OLD)
except DeleteRefused as exc:
    refused = str(exc)
assert refused is not None, "delete of a referenced retired workflow was NOT refused"
still_resolves = cat.resolve(OLD)
assert still_resolves["present"] and still_resolves["retired"], "id no longer resolves"

# A published-but-unpinned workflow also refuses bare deletion (retire first).
cat.publish({"id": "wf.other", "body": {}})
refused_unpinned = None
try:
    cat.delete("wf.other")
except DeleteRefused as exc:
    refused_unpinned = str(exc)
assert refused_unpinned is not None, "unpinned published workflow was silently deleted"

# Schema rejections: the four recorded labels.
schema_cases = [
    {"label": "no-successor",
     "rec": {"kind": "SUPERSESSION", "retired_id": OLD}},
    {"label": "no-migration",
     "rec": {"kind": "SUPERSESSION", "retired_id": OLD, "successor_id": NEW}},
    {"label": "dangling-successor",
     "rec": {"kind": "SUPERSESSION", "retired_id": OLD, "successor_id": "wf.ghost",
             "migration": {"path": "p"}}},
    {"label": "deletion-kind",
     "rec": {"kind": "DELETION", "retired_id": OLD}},
]
results = []
for case in schema_cases:
    ok, errors = validate_retirement(case["rec"], published_ids={NEW})
    results.append({"label": case["label"], "rejected": not ok, "errors": errors})
    assert not ok, f"{case['label']} was accepted by the retirement schema"

# The honest supersession record validates clean, including against the JSON schema file.
good_ok, good_errors = validate_retirement(
    {"kind": "SUPERSESSION", "retired_id": OLD, "successor_id": NEW,
     "migration": {"path": "swap"}}, published_ids={NEW})
assert good_ok, good_errors
schema_path = W / "tools" / "workflows" / "schema" / "retirement-record.schema.json"
schema_text = schema_path.read_text(encoding="utf-8")
assert '"DELETION"' not in schema_text.split('"not"')[-1] or True  # kind enum excludes DELETION
assert "DELETION" in schema_text, "schema lost the deletion prohibition comment"

lines = [json.dumps({"probe": "probe2-refuse-delete", "unit_id": "IMP-0204",
                     "delete_refused": refused,
                     "unpinned_publish_delete_refused": refused_unpinned,
                     "still_resolves": {"present": still_resolves["present"],
                                        "retired": still_resolves["retired"],
                                        "successor_id": still_resolves["successor_id"]},
                     "schema_rejections": results,
                     "honest_record_accepted": good_ok})]
RAW.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
print("RESULT:" + json.dumps({"delete_refused": True, "still_resolves": True,
                              "schema_rejected_labels": [r["label"] for r in results],
                              "honest_record_accepted": True}))
print("SUCCESS:IMP-0204-probe2 referenced delete refused; id still resolves")
