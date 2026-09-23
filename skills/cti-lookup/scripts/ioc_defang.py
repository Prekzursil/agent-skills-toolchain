#!/usr/bin/env python3
"""ioc_defang: defang / refang indicators and extract IOCs from text — offline.

Borrowed *technique* only (defang/refang + IOC extraction), not a 67-command
orchestrator. Stdlib only. No network calls: this operates purely on the text
you pass in, so it is safe to run over untrusted report bodies, pasted emails,
or tool output before that text is ever forwarded to an enrichment provider.

- ``defang(text)``  makes IOCs safe to paste/share (``http`` -> ``hxxp``,
  ``.`` -> ``[.]``, ``@`` -> ``[@]``).
- ``refang(text)`` reverses common obfuscation (``[.]``/``(.)``/``[dot]`` ->
  ``.``, ``hxxp`` -> ``http``, ``[at]`` -> ``@``, ``\\.`` -> ``.``).
- ``extract_iocs(text)`` refangs first, then pulls IPv4, URLs, emails, domains,
  MD5/SHA-1/SHA-256 hashes, and CVE IDs into sorted, de-duplicated lists.

Usage:
    python3 ioc_defang.py defang  "https://evil.com/a.php"
    python3 ioc_defang.py refang  "hxxps://evil[.]com"
    python3 ioc_defang.py extract "beacon to bad[.]example[.]com" --json
    echo "report text" | python3 ioc_defang.py extract --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# --------------------------------------------------------------------------- #
# defang / refang
# --------------------------------------------------------------------------- #
_DEFANG_SCHEMES = (("https", "hxxps"), ("http", "hxxp"), ("ftp", "fxp"))

# (compiled pattern, replacement) applied in order for refang.
_REFANG_SUBS = (
    (re.compile(r"[hH][xX]{2}[pP]"), "http"),  # hxxp(s) -> http(s)
    (re.compile(r"[fF][xX][pP]"), "ftp"),
    (re.compile(r"[\[\(\{]\s*://\s*[\]\)\}]"), "://"),
    (re.compile(r"[\[\(\{]\s*\.\s*[\]\)\}]"), "."),  # [.] (.) {.}
    (re.compile(r"[\[\(\{]\s*dot\s*[\]\)\}]", re.IGNORECASE), "."),
    (re.compile(r"[\[\(\{]\s*@\s*[\]\)\}]"), "@"),  # [@] (@) {@}
    (re.compile(r"[\[\(\{]\s*at\s*[\]\)\}]", re.IGNORECASE), "@"),
    (re.compile(r"[\[\(\{]\s*:\s*[\]\)\}]"), ":"),  # [:]
    (re.compile(r"\\\."), "."),  # backslash-escaped dot
)


def defang(text: str) -> str:
    """Neutralize IOCs in ``text`` so they cannot be accidentally clicked."""
    out = text
    for real, safe in _DEFANG_SCHEMES:
        out = out.replace(real, safe)
    out = out.replace(".", "[.]")
    out = out.replace("@", "[@]")
    return out


def refang(text: str) -> str:
    """Reverse common defang obfuscation, returning live IOC text."""
    out = text
    for pattern, repl in _REFANG_SUBS:
        out = pattern.sub(repl, out)
    return out


# --------------------------------------------------------------------------- #
# extraction (offline)
# --------------------------------------------------------------------------- #
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)
_URL_RE = re.compile(r"\b(?:https?|ftp)://[^\s<>\"'\]\)}]+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b")
_DOMAIN_RE = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b"
)
_MD5_RE = re.compile(r"\b[a-fA-F0-9]{32}\b")
_SHA1_RE = re.compile(r"\b[a-fA-F0-9]{40}\b")
_SHA256_RE = re.compile(r"\b[a-fA-F0-9]{64}\b")
_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)

_URL_TRAILING = ".,;:!?)]}>\"'"

IOC_KEYS = ("ipv4", "url", "email", "domain", "md5", "sha1", "sha256", "cve")


def _clean_url(url: str) -> str:
    return url.rstrip(_URL_TRAILING)


def extract_iocs(text: str, refang_first: bool = True) -> dict[str, list[str]]:
    """Extract IOCs from ``text`` into sorted, de-duplicated lists per type.

    Domains that only occur inside a matched URL or email are dropped so the
    same host is not reported twice. IPv6 is deliberately not extracted here
    (fragile without false positives); build an IPv6 indicator explicitly via
    ``stix_export.stix_pattern`` when you already have one.
    """
    work = refang(text) if refang_first else text

    urls = sorted({_clean_url(m) for m in _URL_RE.findall(work)})
    emails = sorted(set(_EMAIL_RE.findall(work)))
    ipv4 = sorted(set(_IPV4_RE.findall(work)))

    haystacks = [u.lower() for u in urls] + [e.lower() for e in emails]
    domains = set()
    for cand in _DOMAIN_RE.findall(work):
        low = cand.lower()
        if any(low in hay for hay in haystacks):
            continue
        domains.add(low)

    return {
        "ipv4": ipv4,
        "url": urls,
        "email": emails,
        "domain": sorted(domains),
        "md5": sorted({h.lower() for h in _MD5_RE.findall(work)}),
        "sha1": sorted({h.lower() for h in _SHA1_RE.findall(work)}),
        "sha256": sorted({h.lower() for h in _SHA256_RE.findall(work)}),
        "cve": sorted({c.upper() for c in _CVE_RE.findall(work)}),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _read_text(value: str | None) -> str:
    if value is not None:
        return value
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ioc_defang",
        description="Defang/refang IOCs and extract them from text (offline).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_defang = sub.add_parser("defang", help="neutralize IOCs for safe sharing")
    p_defang.add_argument("text", nargs="?", help="text (or stdin if omitted)")

    p_refang = sub.add_parser("refang", help="reverse defang obfuscation")
    p_refang.add_argument("text", nargs="?", help="text (or stdin if omitted)")

    p_extract = sub.add_parser("extract", help="extract IOCs from text")
    p_extract.add_argument("text", nargs="?", help="text (or stdin if omitted)")
    p_extract.add_argument("--json", action="store_true", help="emit JSON")

    args = parser.parse_args(argv)
    text = _read_text(args.text)

    if args.command == "defang":
        print(defang(text))
    elif args.command == "refang":
        print(refang(text))
    elif args.command == "extract":
        iocs = extract_iocs(text)
        if args.json:
            print(json.dumps(iocs, indent=2))
        else:
            for key in IOC_KEYS:
                for value in iocs[key]:
                    print(f"{key}\t{value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
