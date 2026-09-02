"""SCRATCH dry-run of the proposed candidate algorithm. Not a deliverable.

Validates, BEFORE the shipped resolver is touched:
  1. every target real-world spelling folds to the right canonical id
  2. every over-fold guard case still fails to resolve
  3. no alias in the table can reach a DIFFERENT canonical id through any candidate form
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

REG = Path("C:/Users/Prekzursil/source/ast-integrate/platform/registry/VENDOR-REGISTRY.json")

LEGAL = (
    "inc", "incorporated", "llc", "l-l-c", "ltd", "limited", "plc", "pbc", "p-b-c",
    "corp", "corporation", "co", "company", "gmbh", "mbh", "ag", "sa", "s-a", "sas",
    "s-a-s", "bv", "b-v", "nv", "n-v", "ab", "oy", "oyj", "as", "kk", "k-k", "pte",
    "pty", "llp", "lp", "srl", "s-r-l", "spa", "s-p-a", "kg", "holdings", "group",
)
DESCRIPTOR = ("ai", "labs", "lab", "research")
DOMAINS = (".com", ".ai", ".co", ".io", ".org", ".net", ".dev")
PUNCT = ",.;:!?'\"()[]{}<>*|`~"

_SEP = re.compile(r"[\s_\-]+")


def norm(v: str) -> str:
    folded = unicodedata.normalize("NFKC", v)
    folded = "".join(c for c in folded if unicodedata.category(c) not in ("Cc", "Cf"))
    folded = folded.strip().casefold()
    folded = _SEP.sub("-", folded)
    return folded.strip("-")


def _strip_suffixes(key: str) -> str:
    cur = key
    changed = True
    while changed:
        changed = False
        for suf in (*LEGAL, *DESCRIPTOR):
            tail = "-" + suf
            if cur.endswith(tail) and len(cur) > len(tail):
                cur = cur[: -len(tail)].strip("-.")
                changed = True
    return cur


def candidates(key: str) -> list[str]:
    base = [key]
    if "." in key:
        dotted = _SEP.sub("-", key.replace(".", "-")).strip("-")
        if dotted:
            base.append(dotted)
    for suf in DOMAINS:
        if key.endswith(suf) and len(key) > len(suf):
            base.append(key[: -len(suf)].strip("-."))
    folded = _SEP.sub("-", "".join("-" if c in PUNCT else c for c in key)).strip("-")
    if folded:
        base.append(folded)
    out: list[str] = []
    for form in base:
        for cand in (form, _strip_suffixes(form)):
            if cand and cand not in out:
                out.append(cand)
    return out


def main() -> int:
    raw = json.loads(REG.read_text(encoding="utf-8"))
    idx: dict[str, str] = {}
    for e in raw["identities"]:
        for a in [e["id"], *e.get("aliases", [])]:
            idx[norm(a)] = e["id"]
    # the aliases this unit proposes to ADD (dry-run them into the index)
    for alias, cid in {
        "anthropic-pbc": "anthropic",
        "mistral-ai": "mistral",
        "meta-platforms": "meta",
        "cohere-labs": "cohere",
        "amazon-web-services": "bedrock",
        "google-cloud": "vertex",
        "gcp": "vertex",
    }.items():
        idx[norm(alias)] = cid

    def resolve(v: str) -> str | None:
        for c in candidates(norm(v)):
            if c in idx:
                return idx[c]
        return None

    want_same = {
        "Anthropic PBC": "anthropic", "Anthropic, PBC": "anthropic",
        "Anthropic P.B.C.": "anthropic", "OpenAI, Inc.": "openai",
        "OpenAI L.L.C.": "openai", "Google LLC": "google", "Mistral AI": "mistral",
        "Mistral AI SAS": "mistral", "Microsoft Corporation": "microsoft",
        "Meta Platforms, Inc.": "meta", "Cohere Labs": "cohere",
        "Alibaba Cloud Ltd": "alibaba", "DeepSeek AI Ltd.": "deepseek",
        "xAI Corp": "xai", "x.ai": "xai", "anthropic\u200b": "anthropic",
        "anth\u00adropic": "anthropic", "\u200eanthropic": "anthropic",
        "open\ufeffai": "openai", "Anthropic\u00a0": "anthropic",
        "anthropic.com": "anthropic", "Claude_Code": "anthropic",
        "anthropic\x00": "anthropic", "open ai": "openai",
    }
    want_none_or_plane = [
        "Acme Inc", "Acme AI Ltd", "Anthropic Killer Inc", "Inc", "Ltd.", "AI",
        "openai-ish", "!!!", "...", "unknown-vendor-inc", "xxxxxxxx",
    ]
    want_plane = {
        "Google Cloud": "vertex", "AWS Bedrock Inc": "bedrock",
        "Amazon Web Services": "bedrock", "Azure AI": "azure", "n/a": "unassigned",
        "bedrock": "bedrock", "local": "local", "mixed": "mixed",
    }
    bad = []
    for s, cid in want_same.items():
        got = resolve(s)
        if got != cid:
            bad.append(f"SAME  {s!r}: want {cid} got {got}")
    for s in want_none_or_plane:
        got = resolve(s)
        if got is not None:
            bad.append(f"NONE  {s!r}: must not resolve, got {got}")
    for s, cid in want_plane.items():
        got = resolve(s)
        if got != cid:
            bad.append(f"PLANE {s!r}: want {cid} got {got}")

    # --- collision sweep: no alias may reach a DIFFERENT canonical id via any candidate ------
    collisions = []
    for alias, owner in sorted(idx.items()):
        for c in candidates(alias):
            other = idx.get(c)
            if other is not None and other != owner:
                collisions.append(f"{alias!r} ({owner}) -> candidate {c!r} -> {other}")
    print(f"cases_checked={len(want_same) + len(want_none_or_plane) + len(want_plane)}")
    print(f"failures={len(bad)}")
    for b in bad:
        print("  " + b)
    print(f"alias_candidate_collisions={len(collisions)}")
    for c in collisions:
        print("  " + c)
    ok = not bad and not collisions
    print("SUCCESS:d1-dryrun" if ok else "FAILED:d1-dryrun")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
