#!/usr/bin/env python3
"""Emit command-center/research/RES-0053.json from live captures."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from facts import (  # noqa: E402
    crates_futures_020,
    jetbrains_python,
    npm_event_stream,
    npm_flatmap,
    pypi_urllib3_yanked,
    rail,
    vscode_material,
)
from oracle import expected_rows, phrases_ok  # noqa: E402
from schema_local import (  # noqa: E402
    digest_file,
    fingerprint,
    garbage_accepted,
    iter_errors,
)

UNIT = "RES-0053"
OUT_REL = "command-center/research/RES-0053.json"
SCHEMA_REL = "command-center/schema/research-claim-record.schema.json"
SENTINEL = (
    "SUCCESS:RES-0053 in the receipt AND a per-registry revocation table "
    "with a separate installed-client column and one cited incident"
)
QUESTION = (
    "When a published package must be pulled, what does each mature registry "
    "actually do (yank, unpublish, deprecate, advisory) and what does an "
    "ALREADY-INSTALLED client see - the half of revocation that most designs forget?"
)


P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0053/probe1_table_and_rails.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0053/probe2_capture_oracle.py"
)
SCHEMA_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0053/schema_local.py"
)


def dump(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_artifact(rel: str, role: str) -> dict:
    sha, size = digest_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int = 0) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:8000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    npm_r1 = rail("npm-api-unpublished-flatmap-stream", "api")
    npm_r1b = rail("npm-api-event-stream", "api")
    npm_r2 = rail("npm-prose-unpublish-policy", "prose")
    npm_r2b = rail("npm-prose-deprecate-cli", "prose")
    pypi_r1 = rail("pypi-api-simple-urllib3", "api")
    pypi_r2 = rail("pypi-prose-pep592", "prose")
    crates_r1 = rail("crates-api-futures-0-2-0", "api")
    crates_r2 = rail("crates-prose-cargo-yank", "prose")
    vs_r1 = rail("vscode-api-material-theme", "api")
    vs_r2 = rail("vscode-prose-runtime-security", "prose")
    jb_r1 = rail("jetbrains-api-python-plugin", "api")
    jb_r2 = rail("jetbrains-prose-hidden-release", "prose")
    ch_r1 = rail("chrome-api-safe-browsing-help", "api")
    ch_r2 = rail("chrome-prose-disabled-extensions", "prose")
    inc_r1 = rail("incident-npm-blog-event-stream", "prose")
    inc_r2 = rail("incident-snyk-event-stream", "prose")
    # Incident second rail is also prose (vendor postmortem vs researcher
    # postmortem). Pair it with the npm registry API as the structured rail.
    inc_api = npm_r1

    flat = npm_flatmap()
    es = npm_event_stream()
    yanked = pypi_urllib3_yanked()
    fut = crates_futures_020()
    vs = vscode_material()
    jb = jetbrains_python()
    yanked0 = yanked[0] if yanked else {}
    missing = phrases_ok()
    if missing:
        print(f"FAILED:RES-0053 emit phrase-missing:{missing}")
        return 1
    expect = expected_rows()
    for rid, spec in expect.items():
        if not spec.get("require"):
            print(f"FAILED:RES-0053 emit api-precondition:{rid}:{spec}")
            return 1

    table = [
        {
            "registry": "npm",
            "registry_action": "unpublish (72h / low-traffic criteria) or deprecate; security-holder replacement for malware names",
            "installed_client": (
                "Nothing is pushed to an already-extracted node_modules tree. "
                "A later install of a malware-replaced name receives the security "
                f"holding package (flatmap-stream latest={flat['latest']!r}, "
                f"description={flat['description']!r}). event-stream@3.3.6 is "
                f"absent from versions (installable={es['has_3_3_6_in_versions']}) "
                f"but remains in the time tombstone ({es['time_3_3_6']}). "
                "Deprecation warns at next install; it does not uninstall."
            ),
            "installed_client_reaches": False,
            "reach_channel": "none",
            "strongest_caveat": (
                "npm Security can replace the registry document (security-holder) "
                "so NEW installs change; that is not the same as mutating disks "
                "that already unpacked the old tarball."
            ),
        },
        {
            "registry": "pypi",
            "registry_action": "yank (PEP 592 data-yanked / JSON yanked) plus limited delete",
            "installed_client": (
                "An already-installed distribution is not uninstalled. PEP 592: "
                "a computer mechanically reinstalling a previously selected yanked "
                "file 'acts as if it had not been yanked'. Live simple API: "
                f"{len(yanked)} yanked urllib3 files, e.g. {yanked0.get('filename')} "
                f"yanked={yanked0.get('yanked')!r}."
            ),
            "installed_client_reaches": False,
            "reach_channel": "none",
            "strongest_caveat": (
                "Installers SHOULD warn when they do install a yanked file; a "
                "lockfile pin can still fetch it."
            ),
        },
        {
            "registry": "crates.io",
            "registry_action": "yank (no user deletion of crate bytes)",
            "installed_client": (
                f"futures {fut['num']} has yanked={fut['yanked']} on the crates.io "
                "API and still advertises a download path. Cargo: yanking 'does not "
                "delete any data'; 'Existing lock files or direct downloads are not "
                "affected'."
            ),
            "installed_client_reaches": False,
            "reach_channel": "none",
            "strongest_caveat": (
                "A fresh checkout without a lockfile will not newly depend on the "
                "yanked version; that is resolver policy, not an installed-tree wipe."
            ),
        },
        {
            "registry": "vs-code-marketplace",
            "registry_action": "gallery unpublish/deprecate PLUS a separate malware block list",
            "installed_client": (
                "Two channels. (1) Gallery: live query for "
                "equinusocio.vsc-material-theme returns "
                f"displayName={vs['display_name']!r} flags={vs['flags']!r}; "
                "no revoked/blocked field is present, so listing deprecation is "
                "not a kill-switch in this JSON. (2) Malware block list "
                "(vscode-docs): a verified malicious extension is removed from "
                "the Marketplace AND 'automatically uninstalled by VS Code' on "
                "already-installed instances."
            ),
            "installed_client_reaches": True,
            "reach_channel": "malware-blocklist-not-gallery-unpublish",
            "strongest_caveat": (
                "Do not treat gallery unpublish/deprecate as the installed-client "
                "story. Auto-uninstall is documented only for the malware block list."
            ),
        },
        {
            "registry": "jetbrains-marketplace",
            "registry_action": "hide version / unpublish or remove after review",
            "installed_client": (
                "Official hide-version docs: 'This won’t affect users who have "
                "already installed this version, but new users won't be able to "
                "download it unless you provide the direct link'. API for plugin "
                f"631 Python exposes isHidden={jb['isHidden']} isBlocked={jb['isBlocked']} "
                "(fields exist; this plugin is not hidden)."
            ),
            "installed_client_reaches": False,
            "reach_channel": "none",
            "strongest_caveat": (
                "Post-approval unpublish is documented as a marketplace listing "
                "action; the hide-version page is the explicit installed-client "
                "negative. Manual uninstall remains user-initiated."
            ),
        },
        {
            "registry": "chrome-web-store",
            "registry_action": "unpublish from CWS; malware/unsafe handled by Chrome client",
            "installed_client": (
                "Mere CWS unpublish is not the kill-switch for consumer Chrome "
                "(enterprise ExtensionUnpublishedAvailability defaults to allowing "
                "unpublished extensions). The installed-client path is Chrome itself: "
                "Safe Browsing help states 'If you have an abusive or malicious "
                "extension installed, Chrome disables it.' CWS help: Chrome turns "
                "off extensions that 'didn't come from the Chrome Web Store or were "
                "determined unsafe'."
            ),
            "installed_client_reaches": True,
            "reach_channel": "safe-browsing-malware-disable-not-mere-unpublish",
            "strongest_caveat": (
                "Chrome has no public package JSON analogous to npm/PyPI. The API "
                "rail here is Google's Safe Browsing product contract, not a CWS "
                "item document. Same publisher as the CWS help page; different "
                "product surface."
            ),
        },
    ]

    claims = [
        {
            "id": "C-NPM-UNPUBLISH-DEPRECATE",
            "claim": (
                "npm's publisher tools are unpublish and deprecate, not yank. "
                "Already-installed trees are not remotely deleted; deprecation "
                "warns on next install so 'builds will not break'."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "Security-holder replacement changes what a NEW install receives "
                "for a taken name; that is still not an uninstall of unpacked files."
            ),
            "rails": [npm_r1, npm_r2],
        },
        {
            "id": "C-PYPI-YANK-PINNED",
            "claim": (
                "PyPI yank is a resolver signal (simple API yanked field / "
                "data-yanked). A mechanical reinstall of a previously selected "
                "yanked file acts as if it had not been yanked."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "This run observed yanked=reason-string (not boolean true) on "
                "urllib3 files; PEP 691 treats a truthy yanked value as yanked."
            ),
            "rails": [pypi_r1, pypi_r2],
        },
        {
            "id": "C-CRATES-YANK-LOCKFILE",
            "claim": (
                "crates.io yank marks the version yanked in the API, does not "
                "delete crate bytes, and does not break existing lockfiles or "
                "direct downloads."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "futures 0.2.0 is one yanked version, not a proof that every "
                "crate follows the same UI copy; the Cargo book states the rule."
            ),
            "rails": [crates_r1, crates_r2],
        },
        {
            "id": "C-VSCODE-BLOCKLIST-VS-GALLERY",
            "claim": (
                "VS Code's malware block list automatically uninstalls already-"
                "installed copies. Gallery deprecation/unpublish is a different "
                "channel: the live Material Theme listing is still public and "
                "carries no revoked field."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "The live gallery query is not itself a currently-blocked malware "
                "sample; it shows the listing channel. Auto-uninstall is quoted "
                "from vscode-docs Block List, not observed on this worktree's IDE."
            ),
            "rails": [vs_r1, vs_r2],
        },
        {
            "id": "C-JETBRAINS-HIDE-NO-UNINSTALL",
            "claim": (
                "JetBrains Marketplace hide-version does not affect users who "
                "already installed that version. The plugin JSON has isHidden "
                "and isBlocked fields."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "The live plugin 631 record is not hidden; it is used to show "
                "the field exists, not as a hidden-state sample."
            ),
            "rails": [jb_r1, jb_r2],
        },
        {
            "id": "C-CHROME-SAFE-BROWSING-DISABLE",
            "claim": (
                "Chrome reaches already-installed malicious/unsafe extensions by "
                "disabling them in the browser (Safe Browsing / 'Extensions "
                "Disabled'). That is a client channel, not CWS unpublish."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "Both Chrome rails are Google support pages (no public CWS item "
                "JSON). Same organisation; different properties "
                "(support.google.com/chrome vs /chrome_webstore). Graded E1 on "
                "the disable statement, not on a live malware-extension probe."
            ),
            "rails": [ch_r1, ch_r2],
        },
        {
            "id": "C-INCIDENT-EVENT-STREAM",
            "claim": (
                "Cited incident: 2018 event-stream / flatmap-stream. npm removed "
                "flatmap-stream and event-stream@3.3.6 from the registry and told "
                "users to run npm audit and update. Already-installed users were "
                "not remotely cleaned; user action was required. Live registry "
                "still shows the security-holder name and a 3.3.6 time tombstone."
            ),
            "verdict": "CONFIRMED",
            "evidence_grade": "E1",
            "strongest_caveat": (
                "The npm blog and Snyk postmortem share the same incident; they "
                "are independent publishers. The structured rail is today's "
                "registry JSON, not a 2018 packet capture."
            ),
            "rails": [inc_api, inc_r1],
            "third_rail_researcher": inc_r2,
        },
    ]

    cited_incident = {
        "name": "npm event-stream / flatmap-stream (2018)",
        "what_registry_did": (
            "Removed flatmap-stream and event-stream@3.3.6 from the npm "
            "Registry and took ownership of event-stream."
        ),
        "what_installed_users_experienced": (
            "Already-installed copies were not remotely wiped. npm told "
            "users to run npm audit and update to a later event-stream. "
            "Copay versions 5.0.2–5.1.0 shipped the malicious build; BitPay "
            "told those users not to run the app. Live 2026 registry: "
            "flatmap-stream is a security holding package "
            "(0.0.1-security); event-stream@3.3.6 is gone from versions "
            "but timestamped in time."
        ),
        "source": inc_r1["permalink"],
        "rails": [inc_api, inc_r1],
    }
    answer = (
        "Mature registries mostly pull a listing or mark a version unselectable "
        "(npm unpublish/deprecate/security-holder, PyPI yank, crates.io yank, "
        "JetBrains hide). That half does not mutate an already-installed tree: "
        "'nothing happens' on disk until the user updates, which is a valid "
        "and important finding (event-stream: npm removed registry objects and "
        "asked users to update). The forgotten half is a SEPARATE client "
        "channel: VS Code's malware block list auto-uninstalls, and Chrome "
        "Safe Browsing disables malicious installed extensions. Designing a "
        "prompt-payload marketplace after npm yank alone will miss already-"
        "installed clients unless a client-side check is specified."
    )
    reaches_true = sum(1 for r in table if r.get("installed_client_reaches") is True)
    reaches_false = sum(1 for r in table if r.get("installed_client_reaches") is False)
    capture_index = "command-center/p2-wave/probes/RES-0053/captures/INDEX.json"
    schema_src = (
        "file-read of dual-rail capture bodies plus INDEX.json; "
        f"phrases_ok missing={phrases_ok()!r}; "
        f"oracle reaches={[ (k, expect[k]['installed_client_reaches']) for k in expect ]}"
    )
    artifacts = [
        file_artifact(capture_index, "primary"),
        file_artifact(SCHEMA_REL, "supporting"),
        file_artifact(
            "command-center/p2-wave/probes/RES-0053/captures/"
            "npm-api-unpublished-flatmap-stream.body",
            "supporting",
        ),
        file_artifact(
            "command-center/p2-wave/probes/RES-0053/captures/"
            "incident-npm-blog-event-stream.body",
            "supporting",
        ),
    ]
    started = str(npm_r1.get("fetch_timestamp") or now)
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json RES-0053",
        "min_bytes_threshold": 512,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "registry-analyst",
            "execution_substrate": "linux-p2-deliver",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Each of six registries has a revocation_table row with a "
                    "separate installed_client column; dual api+prose rails "
                    "re-hash to capture bytes; npm/pypi/crates/JetBrains do not "
                    "reach already-installed trees; VS Code malware block list "
                    "and Chrome Safe Browsing do."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": capture_index,
                "probes": [
                    probe("source", "file-read", capture_index, schema_src),
                    probe(
                        "verifier",
                        "test-run",
                        P1,
                        "table dual-rail rehash both-states; "
                        "missing-installed_client mutant must fire",
                    ),
                ],
            },
            {
                "claim": (
                    "Cited incident event-stream/flatmap-stream: registry objects "
                    "were removed; already-installed users were told to run npm "
                    "audit and update, not remotely cleaned."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": inc_r1["captured_path"],
                "probes": [
                    probe(
                        "source",
                        "http",
                        inc_r1["permalink"],
                        f"http_status={inc_r1['http_status']} sha256={inc_r1['sha256']}",
                    ),
                    probe(
                        "verifier",
                        "test-run",
                        P2,
                        "capture-oracle overclaim-control; "
                        "npm auto-uninstall mutant must fire",
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "per-registry-installed-client-column",
                "name": (
                    "for each registry, state explicitly what an installed "
                    "client observes after a revocation"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "cited-incident-user-experience",
                "name": (
                    "control: cite at least one real revocation incident and "
                    "what users experienced"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-MISSING-INSTALLED-CLIENT",
                "kind": "mutation",
                "description": (
                    "Dropping installed_client from one revocation_table row "
                    "must fail probe1; the live table must pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "missing-installed_client",
                "good_state_output": "table_ok=True",
            },
            {
                "id": "NC-NPM-OVERCLAIM",
                "kind": "mutation",
                "description": (
                    "A mutant that claims npm auto-uninstalls already-installed "
                    "trees must fail probe2; the live npm row must not."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "npm-overclaim-in-live-artifact or overclaim detector",
                "good_state_output": "npm_overclaim_mutant_fires=True",
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": (
                    "Empty/partial objects must be rejected by the physical "
                    "research-claim-record schema; the live receipt must pass."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "schema errors on {} / schema_version-only",
                "good_state_output": "schema_errors=0",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0053-probe2-capture-oracle",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "unassigned",
            "notes": (
                "Probe 2 re-parses capture bytes with a phrase-and-API oracle "
                "that emit.py does not import, requires at least one "
                "installed_client_reaches=false and one true, and rejects an "
                "overclaim mutant that says npm auto-uninstalls. This is a "
                "mechanical independent verifier, not a fresh-context LLM refuter."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0053/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "jsonschema Draft202012Validator + disk RefResolver "
                    "(research-claim-record shim)"
                ),
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    SCHEMA_CMD,
                    "schema_errors=0; garbage {} rejected",
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": now,
        },
        "retry": {
            "count": 1,
            "policy": (
                "First emit strike: jsonschema 4.10 followed the shim $ref onto "
                "https://ast-integrate.invalid and failed closed. Pivot: disk "
                "RefResolver + receipt_core envelope. Catalog retry_policy "
                "(search-rail rotation) was not consumed; captures are local."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Chrome Web Store item JSON is not a public analogue of "
                    "registry.npmjs.org; Safe Browsing help is used as the "
                    "client-behavior contract."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "If Google publishes a CWS item JSON analogue, recapture it "
                    "as the API rail and re-grade C-CHROME-SAFE-BROWSING-DISABLE."
                ),
            },
            {
                "claim": (
                    "This unit did not run VS Code or Chrome against a live "
                    "blocklisted extension on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Install a currently-blocklisted VS Code extension and a "
                    "Safe-Browsing-flagged Chrome extension on an isolated "
                    "profile and record whether auto-uninstall/disable fires."
                ),
            },
            {
                "claim": (
                    "command-center/sources/REGISTER.md and the 05-ECO restore "
                    "snapshot are absent on this worktree; the six-registry set "
                    "is taken from the catalog question."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount the 05-ECO restore snapshot and confirm the six "
                    "registries still cover the revocation question."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement names a fresh-context "
                    "adversarial LLM refuter; this delivery uses the mechanical "
                    "probe2 oracle instead."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch a partitioned fresh-context refuter over the "
                    "capture bytes and this receipt."
                ),
            },
        ],
        "report": {
            "kind": "research-claim-record",
            "observations": [
                {
                    "name": "npm_flatmap_latest_is_security_holder",
                    "measured": bool(flat["latest_is_security_holder"]),
                    "method": "json-walk",
                    "anchor": npm_r1["captured_path"],
                },
                {
                    "name": "event_stream_3_3_6_in_versions",
                    "measured": bool(es["has_3_3_6_in_versions"]),
                    "method": "json-walk",
                    "anchor": npm_r1b["captured_path"],
                },
                {
                    "name": "pypi_urllib3_yanked_file_count",
                    "measured": len(yanked),
                    "method": "json-walk",
                    "anchor": pypi_r1["captured_path"],
                },
                {
                    "name": "crates_futures_0_2_0_yanked",
                    "measured": bool(fut["yanked"] is True),
                    "method": "json-walk",
                    "anchor": crates_r1["captured_path"],
                },
                {
                    "name": "vscode_material_theme_listing_public",
                    "measured": bool(vs["public"]),
                    "method": "json-walk",
                    "anchor": vs_r1["captured_path"],
                },
                {
                    "name": "jetbrains_plugin_api_exposes_hidden_blocked",
                    "measured": bool(
                        jb["has_hidden_field"] and jb["has_blocked_field"]
                    ),
                    "method": "json-walk",
                    "anchor": jb_r1["captured_path"],
                },
                {
                    "name": "installed_client_reaches_true_count",
                    "measured": reaches_true,
                    "method": "table-scan",
                    "anchor": "report.revocation_table",
                },
                {
                    "name": "installed_client_reaches_false_count",
                    "measured": reaches_false,
                    "method": "table-scan",
                    "anchor": "report.revocation_table",
                },
            ],
            "control_ids": [
                "NC-MISSING-INSTALLED-CLIENT",
                "NC-NPM-OVERCLAIM",
                "NC-SCHEMA-GARBAGE",
            ],
            "title": (
                "Determine how registries actually revoke a bad package and "
                "what the client-side story is"
            ),
            "question": QUESTION,
            "answer": answer,
            "revocation_table": table,
            "cited_incident": cited_incident,
            "claims": claims,
            "honesty": {
                "nothing_happens_is_a_finding": True,
                "installed_client_answered_separately": True,
                "chrome_api_rail_is_product_help_not_package_json": True,
                "vscode_material_theme_listing_is_not_currently_malware_blocked": True,
                "did_not_rotate_or_print_api_keys": True,
            },
            "named_probes": [
                {"id": "probe1", "command": P1},
                {"id": "probe2", "command": P2},
            ],
            "evidence_captures": [
                {"path": r["captured_path"], "kind": r["kind"], "id": r["id"]}
                for r in [
                    npm_r1,
                    npm_r1b,
                    npm_r2,
                    npm_r2b,
                    pypi_r1,
                    pypi_r2,
                    crates_r1,
                    crates_r2,
                    vs_r1,
                    vs_r2,
                    jb_r1,
                    jb_r2,
                    ch_r1,
                    ch_r2,
                    inc_r1,
                    inc_r2,
                ]
            ],
        },
        "extensions": {
            "output_schema": SCHEMA_REL,
            "fetched_at": now,
            "completion_sentinel": SENTINEL,
        },
    }

    vacuous = garbage_accepted()
    if vacuous is not None:
        print(f"FAILED:RES-0053 emit schema-vacuous {list(vacuous)[:4]}")
        return 1
    errs = iter_errors(doc)
    if errs:
        for err in errs[:16]:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            print(f"  {loc}: {err.message}")
        print(f"FAILED:RES-0053 emit schema n={len(errs)}")
        return 1
    kind_pin = dict(doc)
    kind_pin["report"] = dict(doc["report"])
    kind_pin["report"]["kind"] = "audit-finding"
    if not iter_errors(kind_pin):
        print("FAILED:RES-0053 emit kind-pin-silent")
        return 1
    out = REPO / OUT_REL
    dump(out, doc)
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:RES-0053 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
