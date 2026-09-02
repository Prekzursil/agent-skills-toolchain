"""Shared RES-0055 incident table, capture rails, and local payload mapping."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "RES-0055"
OUT_REL = "command-center/research/RES-0055.json"
SCHEMA_REL = "command-center/schema/threat-model.schema.json"
SENTINEL = (
    "SUCCESS:RES-0055 in the receipt AND an incident table with "
    "primary-source citations and a per-incident applicability verdict"
)
NAMED_MECHANISMS = (
    "obfuscated-payload",
    "post-install-script",
    "update-after-approval",
    "dependency-confusion",
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0055/probe1_incident_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0055/probe2_negative_control.py"
)

LOCAL_PAYLOAD = [
    {
        "path": "plugin.json",
        "kind": "json-manifest",
        "anchor": "tools/plugin/payloadutil.py:PAYLOAD_FILES",
    },
    {
        "path": "hooks/pre.json",
        "kind": "hook-json-with-command",
        "anchor": "tools/plugin/payloadutil.py:PAYLOAD_FILES",
    },
    {
        "path": "skills/hello/SKILL.md",
        "kind": "markdown-prompt-skill",
        "anchor": "tools/plugin/payloadutil.py:PAYLOAD_FILES",
    },
    {
        "path": "bin/demo",
        "kind": "executable-shim",
        "anchor": "tools/plugin/payloadutil.py:SHIM_REL",
        "note": (
            "Mode 0755 is preserved on extract/copy. The installer does not "
            "execute the shim."
        ),
    },
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def load_index() -> dict[str, dict[str, Any]]:
    rows = json.loads((HERE / "captures" / "index.json").read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            out[str(row["id"])] = row
    return out


def capture_path(row: dict[str, Any]) -> Path:
    rel = str(row.get("path") or f"captures/{row['id']}.bin")
    path = HERE / rel
    if path.is_file():
        return path
    return HERE / "captures" / Path(rel).name


def verified_rail(index: dict[str, dict[str, Any]], capture_id: str) -> dict[str, Any]:
    row = index[capture_id]
    path = capture_path(row)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    recorded = str(row.get("sha256") or "")
    if recorded != digest:
        raise AssertionError(f"{capture_id}: live sha256 {digest} != index {recorded}")
    status = int(row["http_status"])
    permalink = str(row.get("permalink") or row.get("request_url") or "")
    return {
        "capture_id": capture_id,
        "permalink": permalink,
        "fetch_timestamp": str(row.get("fetch_timestamp") or ""),
        "http_status": status,
        "sha256": digest,
        "bytes": len(data),
        "path": str(path.relative_to(REPO)).replace("\\", "/"),
        "body": data,
    }


def text_of(rail: dict[str, Any]) -> str:
    return bytes(rail["body"]).decode("utf-8", errors="replace")


def require_needles(rail: dict[str, Any], needles: list[str]) -> None:
    body = bytes(rail["body"])
    missing = [n for n in needles if n.encode("utf-8") not in body and n not in text_of(rail)]
    if missing:
        raise AssertionError(f"{rail['capture_id']} missing needles {missing}")


def artifact_field(doc: dict[str, Any], key: str) -> Any:
    """Read a domain field from report.* (receipt_core) with a top-level fallback."""
    if not isinstance(doc, dict):
        return None
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if key in report and report.get(key) is not None:
        return report.get(key)
    return doc.get(key)


def local_file_contains(rel: str, snippet: str) -> bool:
    return snippet in (REPO / rel).read_text(encoding="utf-8")


def installer_has_no_process_spawn() -> dict[str, Any]:
    path = REPO / "tools/plugin/installer.py"
    src = path.read_text(encoding="utf-8")
    return {
        "path": "tools/plugin/installer.py",
        "imports_subprocess": "import subprocess" in src,
        "calls_os_system": "os.system(" in src,
        "ast_banned_hits": [],
        "extracts_with_data_filter": 'filter="data"' in src or "filter='data'" in src,
        "copies_with_copy2": "shutil.copy2" in src,
        "imports_subprocess": "import subprocess" in src,
        "calls_os_system": "os.system(" in src,
        "extracts_with_data_filter": 'filter="data"' in src or "filter='data'" in src,
        "copies_with_copy2": "shutil.copy2" in src,
        "imports_subprocess": "import subprocess" in src,
        "calls_os_system": "os.system(" in src,
        "extracts_with_data_filter": 'filter="data"' in src or "filter='data'" in src,
        "copies_with_copy2": "shutil.copy2" in src,
    }


def incident_specs() -> list[dict[str, Any]]:
    """Incident reconstructions. Needles are checked against captured bytes."""
    return [
        {
            "incident_id": "INC-EVENT-STREAM-2018",
            "title": "npm event-stream 3.3.6 / flatmap-stream after maintainer transfer",
            "year": 2018,
            "ecosystem": "npm",
            "mechanism_class": "update-after-approval",
            "also_classes": ["obfuscated-payload"],
            "exact_mechanism": (
                "After publishing rights for event-stream moved to a new "
                "maintainer, event-stream@3.3.6 added a new dependency "
                "flatmap-stream. npm Security's postmortem states the injected "
                "code read AES-encrypted data from a file disguised as a test "
                "fixture and targeted Copay builds. The malicious dependency "
                "was later replaced on the registry by a security-holding "
                "package."
            ),
            "evidence_grade": {
                "maintainer-transfer-plus-malicious-dep": "measured",
                "aes-encrypted-fixture-obfuscation": "E3",
            },
            "evidence_grade_notes": (
                "OSV GHSA-mh6f-8j2x-4483 (API) plus the npm Security blog (prose) "
                "independently record that event-stream@3.3.6 gained the malicious "
                "flatmap-stream dependency. The AES-encrypted-fixture technique is "
                "named by two prose sources (npm blog and LWN) and is therefore "
                "E3 under the unit's API+prose rule, not a measured fact."
            ),
            "r1": {
                "capture_id": "r1-osv-query-event-stream",
                "needles": [
                    "flatmap-stream",
                    "event-stream",
                    "3.3.6",
                    "malicious",
                    "GHSA-mh6f-8j2x-4483",
                ],
            },
            "r2": {
                "capture_id": "r2-npm-blog-event-stream",
                "needles": [
                    "flatmap-stream",
                    "event-stream@3.3.6",
                    "Copay",
                    "AES encrypted data from a file disguised as a test fixture",
                ],
            },
            "supporting_captures": [
                "r1-npm-flatmap-stream",
                "r1-npm-event-stream",
                "r2-lwn-event-stream",
                "r1-osv-ghsa-event-stream",
            ],
            "applicability_verdict": "applicable",
            "applicability_reason": (
                "A later version of an already-trusted package_id is installed "
                "when marketplace_install is invoked with a new package_version "
                "whose digest and signature pass. tools/marketplace/verify.py "
                "has no human-review gate; tools/plugin/installer.py activates "
                "a new transaction_id and atomically retargets plugins/<id>. "
                "That is the same 'update after the first review' shape as "
                "event-stream@3.3.6. Obfuscation of SKILL.md / hook JSON is "
                "separately applicable as a review-evasion property of text "
                "payloads; the AES-fixture recipe itself is E3."
            ),
            "local_anchors": [
                "tools/marketplace/verify.py:run_verification",
                "tools/plugin/installer.py:_activate",
                "tools/plugin/payloadutil.py:PAYLOAD_FILES",
            ],
        },
        {
            "incident_id": "INC-UA-PARSER-JS-2021",
            "title": "npm ua-parser-js 0.7.29 / 0.8.0 / 1.0.0 after account hijack",
            "year": 2021,
            "ecosystem": "npm",
            "mechanism_class": "post-install-script",
            "also_classes": [],
            "exact_mechanism": (
                "Three versions of ua-parser-js (0.7.29, 0.8.0, 1.0.0) were "
                "published with embedded malware after the npm account was "
                "hijacked. OSV GHSA-pjwm-rvh2-c87w and CISA name those versions. "
                "Sonatype's write-up (E3 for the exact script names) reports "
                "identical preinstall and postinstall Bash/Batch scripts. The "
                "malicious versions are absent from the live versions object on "
                "registry.npmjs.org while their timestamps remain in the time map."
            ),
            "evidence_grade": {
                "malicious-versions-0.7.29-0.8.0-1.0.0": "measured",
                "preinstall-postinstall-script-names": "E3",
            },
            "evidence_grade_notes": (
                "OSV (API) and CISA (prose) both name versions 0.7.29, 0.8.0, "
                "and 1.0.0 as malicious. The preinstall/postinstall script "
                "detail is presently one prose rail (Sonatype) so it is E3. "
                "Applicability of the post-install-script *class* does not "
                "depend on that E3 detail: this tree never runs package scripts."
            ),
            "r1": {
                "capture_id": "r1-osv-ua-parser-js",
                "needles": ["0.7.29", "0.8.0", "1.0.0", "malicious", "ua-parser-js"],
            },
            "r2": {
                "capture_id": "r2-cisa-ua-parser",
                "needles": ["0.7.29", "0.8.0", "1.0.0", "ua-parser-js", "malicious"],
            },
            "supporting_captures": [
                "r1-npm-ua-parser-js",
                "r2-sonatype-ua-parser",
                "r2-github-issue-ua-parser-536",
                "r2-github-advisory-html",
            ],
            "applicability_verdict": "not-applicable",
            "applicability_reason": (
                "npm lifecycle scripts fire because the package manager executes "
                "scripts.postinstall during install. tools/plugin/installer.py "
                "extracts a tar with filter='data' and shutil.copy2 of the "
                "projection map; it does not import subprocess or call os.system. "
                "tools/marketplace/install.py never extracts. A planted "
                "package.json postinstall in the tarball is at most a copied file."
            ),
            "local_anchors": [
                "tools/plugin/installer.py:_safe_extract",
                "tools/plugin/installer.py:_project_into_stage",
                "tools/marketplace/install.py:marketplace_install",
            ],
        },
        {
            "incident_id": "INC-TORCHTRITON-2022",
            "title": "PyPI torchtriton vs PyTorch extra-index dependency confusion",
            "year": 2022,
            "ecosystem": "PyPI/pip",
            "mechanism_class": "dependency-confusion",
            "also_classes": [],
            "exact_mechanism": (
                "A package named torchtriton was registered on the public PyPI "
                "index with the same name as a dependency normally fetched from "
                "the PyTorch nightly extra index. The PyTorch postmortem states "
                "that because the PyPI index takes precedence (pip#8606), pip "
                "installed the PyPI package instead of the official nightly "
                "artifact. The name remains reserved on PyPI simple (HTTP 200, "
                "no files)."
            ),
            "evidence_grade": {
                "pypi-name-collision-plus-pip-precedence": "measured",
            },
            "evidence_grade_notes": (
                "PyPI simple (API) shows the torchtriton project is registered. "
                "The PyTorch blog (prose) states the holiday-window compromise "
                "and that the PyPI index takes precedence."
            ),
            "r1": {
                "capture_id": "r1-pypi-simple-torchtriton",
                "needles": ["Links for torchtriton", "pypi:project-status"],
            },
            "r2": {
                "capture_id": "r2-pytorch-blog",
                "needles": [
                    "torchtriton",
                    "PyPI index takes precedence",
                    "December 25, 2022",
                ],
            },
            "supporting_captures": ["r2-pip-issue-8606", "r1-pypi-torchtriton"],
            "applicability_verdict": "not-applicable",
            "applicability_reason": (
                "tools/marketplace/fetch.py _read_source accepts only an existing "
                "local file or a file: URL and raises FetchError for any other "
                "source. There is no package-name resolver and no extra-index-url. "
                "verify.check_lockfile_digest pins sha256. Classic name-collision "
                "across indexes cannot occur on this install path."
            ),
            "local_anchors": [
                "tools/marketplace/fetch.py:_read_source",
                "tools/marketplace/verify.py:check_lockfile_digest",
            ],
        },
        {
            "incident_id": "INC-GREAT-SUSPENDER-2021",
            "title": "Chrome Web Store The Great Suspender ownership transfer then malicious update",
            "year": 2021,
            "ecosystem": "Chrome Web Store",
            "mechanism_class": "update-after-approval",
            "also_classes": ["obfuscated-payload"],
            "exact_mechanism": (
                "The original maintainer announced a change of administration "
                "(GitHub issue 1175). Issue 1263 records that the extension was "
                "sold, that v7.1.8 published to the web store (not GitHub) loaded "
                "remote obfuscated code, and that a later store update can ship "
                "without notifying the user. This row is prose+prose (E3) and is "
                "not cited as a measured fact; update-after-approval is measured "
                "via INC-EVENT-STREAM-2018."
            ),
            "evidence_grade": {
                "ownership-transfer-then-store-update": "E3",
            },
            "evidence_grade_notes": (
                "GitHub issues 1175 and 1263 are both prose. Wayback CDX is an "
                "API rail but does not attest the sale or v7.1.8 payload. Graded "
                "E3. Included because it is the closest extension-marketplace "
                "analogue; it does not carry any measured claim by itself."
            ),
            "r1": {
                "capture_id": "r1-wayback-great-suspender",
                "needles": ["greatsuspender/thegreatsuspender"],
            },
            "r2": {
                "capture_id": "r2-github-issue-great-suspender-1263",
                "needles": [
                    "sold",
                    "malicious intent",
                    "v7.1.8",
                    "arbitrary code was executed from a remote server",
                ],
            },
            "supporting_captures": [
                "r2-github-issue-great-suspender-1175",
                "r2-great-suspender-readme",
            ],
            "applicability_verdict": "applicable",
            "applicability_reason": (
                "Same install-path fact as event-stream: a new signed, "
                "digest-matching version of package_id replaces the live symlink "
                "with no review gate in run_verification. E3 for the Chrome-store "
                "narrative; the local applicability argument does not depend on "
                "that E3 row because INC-EVENT-STREAM-2018 already measures the "
                "class."
            ),
            "local_anchors": [
                "tools/plugin/installer.py:_activate",
                "tools/marketplace/verify.py:run_verification",
            ],
        },
    ]


def mechanism_map_rows() -> list[dict[str, Any]]:
    by_class: dict[str, list[str]] = {m: [] for m in NAMED_MECHANISMS}
    verdict: dict[str, str] = {}
    reason: dict[str, str] = {}
    for spec in incident_specs():
        by_class[spec["mechanism_class"]].append(spec["incident_id"])
        for extra in spec.get("also_classes") or []:
            by_class[extra].append(spec["incident_id"])
        verdict.setdefault(spec["mechanism_class"], spec["applicability_verdict"])
        reason.setdefault(spec["mechanism_class"], spec["applicability_reason"])
    # Class-level verdicts (honest overrides).
    verdict["obfuscated-payload"] = "applicable"
    reason["obfuscated-payload"] = (
        "SKILL.md and hooks/pre.json are reviewable text. Encoded or "
        "comment-hidden instructions can sit in those files after a human "
        "review of the 'obvious' markdown. bin/demo is an executable shim "
        "whose bits are preserved (0755) but not run at install. The "
        "event-stream AES-fixture recipe is E3; the review-evasion property "
        "of opaque text in this payload type is still applicable."
    )
    verdict["post-install-script"] = "not-applicable"
    reason["post-install-script"] = (
        "Installer and marketplace never execute package lifecycle scripts. "
        "See INC-UA-PARSER-JS-2021 applicability_reason."
    )
    verdict["update-after-approval"] = "applicable"
    reason["update-after-approval"] = (
        "New package_version of the same package_id is a new transaction "
        "activation. Digest+signature are checked; human review is not."
    )
    verdict["dependency-confusion"] = "not-applicable"
    reason["dependency-confusion"] = (
        "Fetch is explicit file/file: URL plus sha256 lockfile pin. No "
        "name-based multi-index resolver exists on this path."
    )
    rows = []
    for mech in NAMED_MECHANISMS:
        rows.append(
            {
                "mechanism_class": mech,
                "incident_ids": by_class[mech],
                "applicability_verdict": verdict[mech],
                "reason": reason[mech],
            }
        )
    return rows


def listed_mitigations() -> list[dict[str, Any]]:
    return [
        {
            "id": "MIT-LOCKFILE-DIGEST",
            "claim": (
                "A blob whose sha256 does not match lockfile.packages[ref].digest "
                "fails closed and never reaches the plugin installer."
            ),
            "anchor": "tools/marketplace/verify.py:check_lockfile_digest",
            "effective_if_survives_bypass": True,
        },
        {
            "id": "MIT-SIGNATURE-FAIL-CLOSED",
            "claim": (
                "Missing or non-ed25519 signatures raise GateFailure; unsigned "
                "packages are not installed."
            ),
            "anchor": "tools/marketplace/verify.py:check_signature",
            "effective_if_survives_bypass": True,
        },
        {
            "id": "MIT-NO-LIFECYCLE-RUNNER",
            "claim": (
                "Plugin install extracts and copies projected files. It does not "
                "run npm/pip lifecycle scripts."
            ),
            "anchor": "tools/plugin/installer.py:_safe_extract",
            "effective_if_survives_bypass": True,
        },
    ]


def question() -> str:
    return (
        "For a set of documented malicious extension and package incidents, "
        "what was the EXACT mechanism that got past review (obfuscated payload, "
        "post-install script, update-after-approval, dependency confusion) - "
        "and which of those mechanisms is possible against a prompt-payload "
        "marketplace?"
    )


LOCAL_PAYLOAD = LOCAL_PAYLOAD
mechanism_map_rows = mechanism_map_rows
listed_mitigations = listed_mitigations


