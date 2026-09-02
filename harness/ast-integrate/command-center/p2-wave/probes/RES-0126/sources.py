"""Version-pinned public dual-use/export-control quotes (local FR HTML snapshots)."""
from __future__ import annotations

from typing import Any

from lib import HERE, sha256_path

FETCH_TS = "2026-08-24T18:48:01Z"
CAP = HERE / "captures"

# Distinctive spans copied from the local HTML (including GPO line breaks)
# so probes can assert exact substring membership.
QUOTES: dict[str, dict[str, str]] = {
    "FR-2020-772.1-intrusion-software": {
        "capture": "FR-2020-10-05-2020-18334.html",
        "url": "https://www.govinfo.gov/content/pkg/FR-2020-10-05/html/2020-18334.htm",
        "citation": "85 FR 62583, FR Doc. 2020-18334 (2020-10-05)",
        "span": (
            "Intrusion software. (5P2) ``Software'' specially designed or \n"
            "modified to avoid detection by `monitoring tools', or to defeat \n"
            "`protective countermeasures', of a computer or network-capable device, \n"
            "and performing any of the following:"
        ),
    },
    "FR-2020-772.1-note1-sre": {
        "capture": "FR-2020-10-05-2020-18334.html",
        "url": "https://www.govinfo.gov/content/pkg/FR-2020-10-05/html/2020-18334.htm",
        "citation": "85 FR 62583, FR Doc. 2020-18334 (2020-10-05)",
        "span": (
            "Note 1 to ``Intrusion software'' definition: ``Intrusion \n"
            "software'' does not include any of the following: Hypervisors, \n"
            "debuggers or Software Reverse Engineering (SRE) tools;"
        ),
    },
    "FR-2021-4A005": {
        "capture": "FR-2021-10-21-2021-22774.html",
        "url": "https://www.govinfo.gov/content/pkg/FR-2021-10-21/html/2021-22774.htm",
        "citation": "86 FR 58205, FR Doc. 2021-22774 (published 2021-10-21, effective 2022-01-19)",
        "span": (
            "4A005 ``Systems,'' ``equipment,'' and ``components'' therefor, \n"
            "``specially designed'' or modified for the generation, command and \n"
            "control, or delivery of ``intrusion software''."
        ),
    },
    "FR-2021-4D004": {
        "capture": "FR-2021-10-21-2021-22774.html",
        "url": "https://www.govinfo.gov/content/pkg/FR-2021-10-21/html/2021-22774.htm",
        "citation": "86 FR 58205, FR Doc. 2021-22774 (published 2021-10-21, effective 2022-01-19)",
        "span": (
            "4D004 ``Software'' ``specially designed'' or modified for the \n"
            "generation, command and control, or delivery of ``intrusion \n"
            "software.''"
        ),
    },
    "FR-2021-4E001-note1": {
        "capture": "FR-2021-10-21-2021-22774.html",
        "url": "https://www.govinfo.gov/content/pkg/FR-2021-10-21/html/2021-22774.htm",
        "citation": "86 FR 58205, FR Doc. 2021-22774 (published 2021-10-21, effective 2022-01-19)",
        "span": (
            "4E001.a and 4E001.c do not apply to ``vulnerability \n"
            "disclosure'' or ``cyber incident response''."
        ),
    },
    "FR-2021-772.1-vulnerability-disclosure": {
        "capture": "FR-2021-10-21-2021-22774.html",
        "url": "https://www.govinfo.gov/content/pkg/FR-2021-10-21/html/2021-22774.htm",
        "citation": "86 FR 58205, FR Doc. 2021-22774 (published 2021-10-21, effective 2022-01-19)",
        "span": (
            "Vulnerability disclosure. (Sec.  740.22, Cat 4) means the process \n"
            "of identifying, reporting, or communicating a vulnerability to, or \n"
            "analyzing a vulnerability with, individuals or organizations \n"
            "responsible for conducting or coordinating remediation for the purpose \n"
            "of resolving the vulnerability."
        ),
    },
    "FR-2021-ACE-purpose": {
        "capture": "FR-2021-10-21-2021-22774.html",
        "url": "https://www.govinfo.gov/content/pkg/FR-2021-10-21/html/2021-22774.htm",
        "citation": "86 FR 58205, FR Doc. 2021-22774 (published 2021-10-21, effective 2022-01-19)",
        "span": (
            "This license exception, will appear in new \n"
            "Sec.  740.22 of the EAR, is necessary to avoid impeding legitimate \n"
            "cybersecurity research and incident response activities."
        ),
    },
    "FR-2022-ACE-final": {
        "capture": "FR-2022-05-26-2022-11282.html",
        "url": "https://www.govinfo.gov/content/pkg/FR-2022-05-26/html/2022-11282.htm",
        "citation": "87 FR 31950, FR Doc. 2022-11282 (2022-05-26)",
        "span": (
            "That rule established a new control on \n"
            "certain cybersecurity items for National Security (NS) and Anti-\n"
            "terrorism (AT) reasons, as well as adding a new License Exception \n"
            "Authorized Cybersecurity Exports (ACE) that authorizes exports of these \n"
            "items to most destinations except in certain circumstances."
        ),
    },
}


def capture_records() -> list[dict[str, Any]]:
    rows = []
    seen: set[str] = set()
    for q in QUOTES.values():
        name = q["capture"]
        if name in seen:
            continue
        seen.add(name)
        path = CAP / name
        digest, nbytes = sha256_path(path)
        rows.append(
            {
                "bytes": nbytes,
                "fetch_timestamp": FETCH_TS,
                "path": f"command-center/p2-wave/probes/RES-0126/captures/{name}",
                "sha256": digest,
                "url": q["url"],
                "version_pin": next(
                    v["citation"] for v in QUOTES.values() if v["capture"] == name
                ),
            }
        )
    return rows


def assert_quotes_in_captures() -> list[str]:
    missing: list[str] = []
    for qid, q in QUOTES.items():
        text = (CAP / q["capture"]).read_text(encoding="utf-8")
        if q["span"] not in text:
            missing.append(qid)
    return missing
