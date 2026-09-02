"""Committed 40-source calibration set. No gold labels on the rows.

Bodies are fixtures (resolved_url is the nominal source). sha256 is of the
UTF-8 body with LF newlines. Five syndicated rows share one verbatim body.
"""
from __future__ import annotations

from typing import Any

CAPTURED_AT = "2026-08-24T20:00:00Z"

SYNDICATED_GIL = (
    "Industry roundup: Python's GIL is gone in a preview build, according to "
    "remarks at a language summit. Multiple outlets repeated the same three "
    "sentences without attaching a benchmark, a PEPs link, or a CPython commit. "
    "The piece ends with a stock photo caption and a share button. Analysts "
    "were not named. No reproduction steps appear."
)

HASHLIB_DOCS = (
    "hashlib provides secure hashes and message digests in the Python standard "
    "library. This document is part of the official Python documentation "
    "maintained by the core team. Call hashlib.new with an algorithm name to "
    "obtain a hash object, then feed it bytes with update and read the digest. "
    "Named constructors include sha256, sha384, sha512, blake2b, and blake2s. "
    "The usedforsecurity flag documents whether an algorithm is appropriate for "
    "cryptographic use. Shake variants expose a variable-length digest. "
    "Documentation examples hash the ASCII bytes of hello world and print the "
    "hexadecimal digest. Additional notes cover file hashing, comparison via "
    "compare_digest, and the openssl backend. Readers should prefer the named "
    "constructors over new when the algorithm is known. The library reference "
    "also lists algorithms_guaranteed and algorithms_available so a deployment "
    "can test for platform support before selecting a hash. Official examples "
    "show incremental update from a file object in a loop of fixed-size blocks."
)

HASHLIB_NEARCOPY = (
    "hashlib provides secure hash routines and message digests in the Python "
    "standard library. This document is part of the official Python documentation "
    "maintained by the core team. Call hashlib.new with an algorithm name to "
    "obtain a hash object, then feed it bytes with update and read the digest. "
    "Named constructors include sha256, sha384, sha512, blake2b, and blake2s. "
    "The usedforsecurity flag documents whether an algorithm is appropriate for "
    "cryptographic use. Shake variants expose a variable-length digest. "
    "Documentation examples hash the ASCII bytes of hello worlds and print the "
    "hexadecimal digest. Additional notes cover file hashing, comparison via "
    "compare_digest, and the openssl backend. Readers should prefer the named "
    "constructors over new when the algorithm is known. The library reference "
    "also lists algorithms_guaranteed and algorithms_available so a deployment "
    "can test for platform support before selecting a hash. Official examples "
    "show incremental update from a file object in a loop of fixed-size blocks."
)

_SOURCES: list[dict[str, str]] = [
    {"id": "S01", "url": "https://wire.example/tech/python-gil-removed", "body": SYNDICATED_GIL},
    {"id": "S02", "url": "https://news.example/repost/python-gil", "body": SYNDICATED_GIL},
    {"id": "S03", "url": "https://mirror.example/feeds/gil-story", "body": SYNDICATED_GIL},
    {"id": "S04", "url": "https://digest.example/items/gil", "body": SYNDICATED_GIL},
    {"id": "S05", "url": "https://roundup.example/2026/gil-copy", "body": SYNDICATED_GIL},
    {
        "id": "S06",
        "url": "https://www.rfc-editor.org/rfc/rfc2119.txt",
        "body": (
            "Network Working Group                         S. Bradner\n"
            "Request for Comments: 2119                Harvard University\n"
            "BCP: 14                                          March 1997\n"
            "Status of This Memo\n"
            "This document specifies an Internet Best Current Practices for the "
            "Internet Community, and requests discussion and suggestions for "
            "improvements. MUST means an absolute requirement. SHOULD means "
            "there may exist valid reasons to ignore a particular item."
        ),
    },
    {
        "id": "S07",
        "url": "https://www.rfc-editor.org/rfc/rfc8259.txt",
        "body": (
            "Internet Engineering Task Force (IETF)                         T. Bray\n"
            "Request for Comments: 8259                                  Textuality\n"
            "Status of This Memo\n"
            "JSON is a text format for serializing structured data. A JSON value "
            "MUST be an object, array, number, string, true, false, or null. "
            "This memo provides information for the Internet community."
        ),
    },
    {
        "id": "S08",
        "url": "https://peps.python.org/pep-0008/",
        "body": (
            "PEP: 8\nTitle: Style Guide for Python Code\n"
            "Author: Guido van Rossum <guido@python.org>, Barry Warsaw, Alyssa Coghlan\n"
            "Status: Active\nType: Process\n"
            "Indentation is four spaces. Limit lines to 79 characters. "
            "Pet Peeves include hanging indent that does not use four spaces."
        ),
    },
    {
        "id": "S09",
        "url": "https://raw.githubusercontent.com/python/cpython/3.12/Lib/hashlib.py",
        "body": (
            "# CPython Lib/hashlib.py — the implementation is the thing itself.\n"
            "\"\"\"hashlib — Secure hashes and message digests.\"\"\"\n"
            "import _hashlib\n"
            "def sha256(data=b''):\n"
            "    return _hashlib.openssl_sha256(data)\n"
        ),
    },
    {
        "id": "S10",
        "url": "https://spdx.org/licenses/MIT.html",
        "body": (
            "MIT License\n"
            "Permission is hereby granted, free of charge, to any person obtaining "
            "a copy of this software and associated documentation files (the "
            "\"Software\"), to deal in the Software without restriction.\n"
            "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, "
            "EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF "
            "MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT."
        ),
    },
    {
        "id": "S11",
        "url": "https://json-schema.org/draft/2020-12/schema",
        "body": (
            "{\n"
            '  "$schema": "https://json-schema.org/draft/2020-12/schema",\n'
            '  "$id": "https://json-schema.org/draft/2020-12/schema",\n'
            '  "title": "Core and Validation specifications meta-schema"\n'
            "}"
        ),
    },
    {
        "id": "S12",
        "url": "https://www.iana.org/assignments/media-types/application/json",
        "body": (
            "IANA media type registration: application/json. Name: JavaScript "
            "Object Notation (JSON). Reference: RFC 8259. Encoding considerations: "
            "8bit. Intended usage: COMMON. The media type is the registration "
            "record itself, not a tutorial about JSON."
        ),
    },
    {
        "id": "S13",
        "url": "https://peps.python.org/pep-0508/",
        "body": (
            "PEP: 508\nTitle: Dependency specification for Python Software Packages\n"
            "Author: Donald Stufft <donald@stufft.io>\nStatus: Final\n"
            "A specification for dependency specifiers using environment markers. "
            "The canonical grammar is this PEP, not a packaging tutorial."
        ),
    },
    {"id": "S14", "url": "https://docs.python.org/3/library/hashlib.html", "body": HASHLIB_DOCS},
    {
        "id": "S15",
        "url": "https://raw.githubusercontent.com/pypa/pip/24.2/README.rst",
        "body": (
            "pip - The Python Package Installer. This README is the project "
            "landing document maintained by the pip team. pip installs packages "
            "from PyPI and other indexes. See the user guide for the install "
            "command, constraints files, and the build isolation flag."
        ),
    },
    {
        "id": "S16",
        "url": "https://raw.githubusercontent.com/psf/requests/main/README.md",
        "body": (
            "Requests: HTTP for Humans. This README is maintained by the PSF "
            "Requests team. The library wraps urllib3. Examples show requests.get "
            "and response.json. See the official user guide for sessions and "
            "certificates."
        ),
    },
    {
        "id": "S17",
        "url": "https://raw.githubusercontent.com/python/cpython/main/CONTRIBUTING.rst",
        "body": (
            "Contributing to CPython. This document is the official contributor "
            "guide. Open a GitHub pull request against python/cpython. Run the "
            "test suite. Do not paste secrets. Triage follows the Devguide."
        ),
    },
    {
        "id": "S18",
        "url": "https://packaging.python.org/en/latest/",
        "body": (
            "Python Packaging User Guide. This is the official packaging.python.org "
            "user guide. It covers pyproject.toml, build backends, and uploading "
            "to PyPI. The guide is maintained by the PyPA, not a third-party blog."
        ),
    },
    {
        "id": "S19",
        "url": "https://www.python.org/downloads/release/python-3120/",
        "body": (
            "Python 3.12.0 release page on python.org. This is the official "
            "download note maintained by the release manager. It lists files, "
            "hashes, and the changelog pointer. No first-person lab notes."
        ),
    },
    {
        "id": "S20",
        "url": "https://numpy.org/doc/stable/user/whatisnumpy.html",
        "body": (
            "What is NumPy? This page is the official NumPy user guide "
            "introduction. ndarray is the core type. Broadcasting is documented "
            "here. The page is maintained by the NumPy project."
        ),
    },
    {
        "id": "S21",
        "url": "https://docs.pypi.org/api/index.html",
        "body": (
            "PyPI warehouse API documentation. This document is part of the "
            "official docs.pypi.org set maintained by the warehouse team. It "
            "describes JSON project endpoints and the simple API."
        ),
    },
    {
        "id": "S22",
        "url": "https://lab.example/notes/hashlib-throughput-2026",
        "body": (
            "I measured hashlib.sha256 throughput on a 64-byte payload over "
            "200000 iterations on a single 3.4 GHz core. Median 1.12 us per "
            "digest, p99 1.41 us. The lab notebook lists the CPU governor and "
            "the exact CPython 3.12.4 tag. This is a local experiment, not a "
            "docs restatement."
        ),
    },
    {
        "id": "S23",
        "url": "https://incident.example/2026/gil-contention",
        "body": (
            "We observed GIL contention in production when twelve worker threads "
            "hashed a 4 MiB buffer with hashlib. Queue delay jumped from 8 ms to "
            "190 ms. The incident ticket includes the flame graph. No news wire "
            "was copied."
        ),
    },
    {
        "id": "S24",
        "url": "https://github.com/psf/requests/issues/99991",
        "body": (
            "I reproduced a timeout in requests 2.32 against a local server that "
            "stalls after the headers. Steps: pip install, run the attached "
            "script, watch ConnectTimeout. This issue is a practitioner report, "
            "not the Requests README."
        ),
    },
    {
        "id": "S25",
        "url": "https://postmortem.example/json-parse-outage",
        "body": (
            "We ran json.loads on a 30 MB truncated payload and observed a "
            "hard process kill from the OOM killer, not a JSONDecodeError. "
            "The postmortem timestamps and cgroup limits are attached. RFC 8259 "
            "does not record this failure mode."
        ),
    },
    {
        "id": "S26",
        "url": "https://ops.example/pep8-enforcement-week",
        "body": (
            "I timed a week of ruff --select E,W on our 1.2 million line tree. "
            "Noise rate was 14 new findings per day, 11 of them line-length. "
            "PEP 8 is cited as the policy, but the numbers are ours."
        ),
    },
    {
        "id": "S27",
        "url": "https://lab.example/notes/requests-vs-urllib",
        "body": (
            "I measured requests.get versus urllib.request.urlopen for 500 sequential "
            "GETs to a local nginx. Median 4.1 ms vs 3.6 ms. TLS session reuse "
            "was disabled on purpose. This comparison is not in the Requests README."
        ),
    },
    {
        "id": "S28",
        "url": "https://lab.example/notes/rfc8259-parser-times",
        "body": (
            "I timed three JSON parsers on the same 2 MB array-of-objects fixture: "
            "stdlib json, ijson, and orjson. Median 18.4 ms, 41.0 ms, 3.1 ms. "
            "The fixture is attached. RFC 8259 does not publish these numbers."
        ),
    },
    {
        "id": "S29",
        "url": "https://lab.example/notes/spdx-detect-repro",
        "body": (
            "I reproduced SPDX license detection on a tree of 400 vendored files. "
            "MIT matched 71 files by the full permission grant string; a one-line "
            "SPDX-License-Identifier matched 310. The detector script is attached."
        ),
    },
    {
        "id": "S30",
        "url": "https://github.com/pypa/packaging/issues/88881",
        "body": (
            "I reproduced a PEP 508 extras parse error on packaging 24.1 with the "
            "specifier 'name[extra]; python_version < \"3.10\"'. Steps and a failing "
            "pytest are in the issue body. This is not the PEP text."
        ),
    },
    {
        "id": "S31",
        "url": "https://tutorial.example/python-hashlib-in-five-minutes",
        "body": (
            "According to the Python docs you can hash a string with sha256 in a "
            "few lines. This tutorial restates constructors and hexdigest without "
            "a new measurement. Copy the snippet, run it, and move on."
        ),
    },
    {
        "id": "S32",
        "url": "https://newsletter.example/rfc2119-explained",
        "body": (
            "As explained in RFC 2119, MUST is stronger than SHOULD. This "
            "newsletter restates the keywords for product managers. No new "
            "requirement is introduced and no protocol is measured."
        ),
    },
    {
        "id": "S33",
        "url": "https://blog.example/according-to-pep8",
        "body": (
            "According to PEP 8, four spaces beat tabs. This blog restates the "
            "line-length rule and hanging-indent pet peeve. No repository was "
            "linted for this post."
        ),
    },
    {
        "id": "S34",
        "url": "https://so.example/q/mit-license-summary",
        "body": (
            "As reported by countless Q&A posts, MIT lets you reuse the code if "
            "you keep the copyright notice. This summary is not the license text "
            "and does not grant rights by itself."
        ),
    },
    {
        "id": "S35",
        "url": "https://news.example/json-schema-in-plain-english",
        "body": (
            "According to the JSON Schema project, a document can declare $schema "
            "and $id. This news brief restates that fact for readers who will not "
            "open the meta-schema. No validator was run."
        ),
    },
    {
        "id": "S36",
        "url": "https://docs.python.org/3/reference/introduction.html",
        "body": (
            "Language reference introduction. This document is part of the official "
            "Python documentation. It quotes RFC 2119 in full for conformance: "
            "Network Working Group. Request for Comments: 2119. Status of This Memo. "
            "MUST means an absolute requirement of the specification. The surrounding "
            "prose is maintainer documentation, not the RFC file."
        ),
    },
    {
        "id": "S37",
        "url": "https://tutorial.example/i-measured-hashlib",
        "body": (
            "I measured hashlib.blake2b against sha256 on 1 KiB buffers for 50000 "
            "loops. blake2b was 1.8x faster on this laptop. The tutorial host is "
            "incidental; the notebook CSV is attached. This is not a restatement "
            "of the hashlib docs."
        ),
    },
    {
        "id": "S38",
        "url": "https://www.python.org/downloads/release/python-3130/",
        "body": (
            "Python 3.13.0 release page. In this release we added a new hashlib "
            "backend probe and we changed the default for a debug flag. The note "
            "is published on python.org by the release manager."
        ),
    },
    {
        "id": "S39",
        "url": "https://news.example/hashlib-docs-reprint",
        "body": HASHLIB_NEARCOPY,
    },
    {
        "id": "S40",
        "url": "https://lab.example/notes/gil-queue-delay",
        "body": (
            "I measured GIL queue delay with eight threads hashing 2 MiB buffers. "
            "Median wait 42 ms, max 210 ms. The lab log is a separate observation "
            "from the production incident, with different hardware and a different "
            "payload size."
        ),
    },
]


def sources() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in _SOURCES:
        out.append(
            {
                "id": row["id"],
                "url": row["url"],
                "body": row["body"],
                "captured_at": CAPTURED_AT,
                "capture_method": "committed-fixture",
            }
        )
    return out


def syndicated_ids() -> list[str]:
    return ["S01", "S02", "S03", "S04", "S05"]


def independent_originating_ids() -> list[str]:
    return ["S06", "S09", "S10", "S22", "S27"]
