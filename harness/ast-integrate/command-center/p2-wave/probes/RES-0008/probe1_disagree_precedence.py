#!/usr/bin/env python3
"""Probe 1: disagreeing versions — plugin.json is honoured; marketplace bump ignored.

Catalog test: construct a fixture where plugin.json and marketplace.json disagree
on version and observe which one the published waterfall honours.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capture import ensure_snapshots  # noqa: E402
from common import (  # noqa: E402
    MARKET_ONLY_BUMP,
    PINNED,
    PLUGIN_WINS_MARKERS,
    UID,
    contains_any,
    extract_marketplace_schema,
    load_fixture,
    load_json,
    snapshot_path,
    snapshot_text,
)


def main() -> int:
    ensure_snapshots(force=False)
    fx = load_fixture("disagree")
    v = fx["verdict"]
    schema = load_json(snapshot_path("claude-code-marketplace.schema.json"))
    extracted = extract_marketplace_schema(schema)
    docs = snapshot_text("plugin-marketplaces.md") + "\n" + snapshot_text(
        "plugins-reference.md"
    )
    issue = snapshot_text("github-54280.json")
    doc_hits = contains_any(docs, PLUGIN_WINS_MARKERS)
    issue_hits = contains_any(
        issue,
        (
            "plugin.json wins",
            "silently overrides marketplace.json version",
            "Customize panel shows",
        ),
    )

    from jsonschema import Draft7Validator

    market_errs = list(
        Draft7Validator(schema).iter_errors(fx["marketplace"])
    )
    missing_plugins = dict(fx["marketplace"])
    missing_plugins.pop("plugins", None)
    missing_errs = list(Draft7Validator(schema).iter_errors(missing_plugins))

    ok = (
        v["plugin_json_version"] == PINNED
        and v["marketplace_version"] == MARKET_ONLY_BUMP
        and v["honoured_version"] == PINNED
        and v["honoured_source"] == "plugin.json"
        and v["precedence_signal"] is True
        and v["identical"] is False
        and extracted["required"] == ["name", "owner", "plugins"]
        and extracted["plugin_entry_required"] == ["name", "source"]
        and not extracted["plugin_entry_version_mentions_plugin_json_priority"]
        and not market_errs
        and bool(missing_errs)
        and bool(doc_hits)
        and bool(issue_hits)
    )
    out = {
        "unit_id": UID,
        "probe": "probe1-disagree-precedence",
        "pass": ok,
        "honoured_version": v["honoured_version"],
        "honoured_source": v["honoured_source"],
        "plugin_json_version": v["plugin_json_version"],
        "marketplace_version": v["marketplace_version"],
        "precedence_signal": v["precedence_signal"],
        "schema_required": extracted["required"],
        "plugin_entry_required": extracted["plugin_entry_required"],
        "schema_encodes_precedence": extracted[
            "plugin_entry_version_mentions_plugin_json_priority"
        ],
        "marketplace_schema_errors": len(market_errs),
        "missing_plugins_rejected": bool(missing_errs),
        "doc_marker_hits": doc_hits,
        "issue_marker_hits": issue_hits,
        "observed_installed_version": v["honoured_version"],
    }
    print(json.dumps(out, sort_keys=True))
    if not ok:
        print("FAILED:RES-0008-probe1 disagree fixture did not yield plugin.json win")
        return 1
    print(
        "SUCCESS:RES-0008-probe1 disagree: plugin.json 0.2.0 honoured; "
        "marketplace 9.9.9 ignored; schema silent on precedence"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
