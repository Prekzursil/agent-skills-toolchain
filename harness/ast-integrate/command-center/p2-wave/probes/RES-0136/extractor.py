"""Two-signal non-OSI rider extractor.

Signal 1 (structural): labelled rider / additional-commercial headings plus
operative grant-narrowing sentences. Does not treat the MIT phrase
"without restriction" as a rider.

Signal 2 (MIT residual): if a MIT grant is present, subtract the SPDX MIT
body and inspect leftover tokens for grant-narrowing language. Independent
of the heading parser.

A detector that keyed on the word "restriction" would fire on every MIT
file; both signals are written so that case stays silent.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"

_WS = re.compile(r"[^a-z0-9]+")

MIT_GRANT = "permission is hereby granted free of charge"
MIT_AS_IS = "the software is provided as is"
# Operative grant-narrowing, not mention-of-riders in prose.
OPERATIVE_NO_GRANT = "no rights are granted to any restricted party"
OPERATIVE_NO_PROVIDE = "you may not provide disclose distribute"
RIDER_HEADING = re.compile(
    r"(?im)^\s*(additional\s+rider\b.*|commons\s+clause\b.*|"
    r"\d+\.\s*additional\s+commercial\s+terms\b.*)$"
)
COMMERCIAL_MAU = re.compile(
    r"additional commercial terms.{0,400}700 million",
    re.IGNORECASE | re.DOTALL,
)
AUP_INCORPORATED = re.compile(
    r"acceptable use policy.{0,200}incorporated by reference",
    re.IGNORECASE | re.DOTALL,
)
NARROWING_RESIDUAL = (
    "restricted part",
    "no rights are granted",
    "this rider",
    "additional rider",
    "you may not provide",
    "commons clause",
    "null and void",
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def naive_restriction_word(text: str) -> bool:
    """Broken control: MIT's 'without restriction' must not count as a rider."""
    return "restriction" in text.lower()


def normalize(text: str) -> str:
    t = text.replace("\r\n", "\n").replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    t = t.lower()
    t = _WS.sub(" ", t)
    return " ".join(t.split())


def load_spdx_mit() -> str:
    return (FIXTURES / "spdx-MIT.txt").read_text(encoding="utf-8")


load_spdx_mit = load_spdx_mit


def mit_core_norm(spdx_text: str) -> str:
    """SPDX MIT body without title and copyright placeholder."""
    n = normalize(spdx_text)
    n = n.replace("mit license", " ", 1)
    n = re.sub(r"copyright c year copyright holders", " ", n)
    return " ".join(n.split())


def has_mit_grant(norm: str) -> bool:
    return MIT_GRANT in norm and MIT_AS_IS in norm


def signal_structural(text: str) -> dict:
    heading = None
    for line in text.replace("\r\n", "\n").splitlines():
        if RIDER_HEADING.match(line.strip()):
            heading = line.strip()
            break
    n = normalize(text)
    operative = OPERATIVE_NO_GRANT in n or (
        "you may not provide" in n and "restricted party" in n
    )
    commercial = bool(COMMERCIAL_MAU.search(text))
    aup = bool(AUP_INCORPORATED.search(text))
    osi_rider = bool(heading and operative) or (
        heading is not None
        and heading.lower().startswith("additional rider")
        and "restricted part" in n
    )
    # Llama-style: not an OSI+rider; still a field-of-use / additional-commercial licence.
    non_osi_field = commercial or (aup and not has_mit_grant(n))
    return {
        "id": "structural-clause",
        "heading": heading,
        "operative_grant_narrowing": operative,
        "additional_commercial_mau": commercial,
        "aup_incorporated": aup,
        "osi_plus_rider": osi_rider,
        "non_osi_field_of_use": non_osi_field and not osi_rider,
    }


def signal_mit_residual(text: str, spdx_text: str) -> dict:
    n = normalize(text)
    core = mit_core_norm(spdx_text)
    mit = has_mit_grant(n)
    leftover = n
    if mit and core:
        leftover = n.replace(core, " ", 1) if core in n else n
        leftover = " ".join(leftover.split())
    hits = [tok for tok in NARROWING_RESIDUAL if tok in leftover] if mit else []
    return {
        "id": "mit-template-residual",
        "mit_grant_present": mit,
        "residual_has_narrowing": bool(hits),
        "narrowing_hits": hits,
        "residual_preview": leftover[:240],
        "osi_plus_rider": bool(mit and hits),
    }


def extract_verbatim_block(text: str) -> str | None:
    lines = text.replace("\r\n", "\n").splitlines()
    start = None
    for i, line in enumerate(lines):
        if RIDER_HEADING.match(line.strip()) and "rider" in line.lower():
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("The above copyright notice"):
            end = j
            break
    block = "\n".join(lines[start:end]).strip()
    return block or None


def extract_llama_commercial(text: str) -> str | None:
    m = re.search(
        r"2\.\s*Additional Commercial Terms\..{0,700}",
        text.replace("\r\n", "\n"),
        re.DOTALL,
    )
    return m.group(0).strip() if m else None


def classify(text: str, spdx_text: str | None = None) -> dict:
    spdx = spdx_text if spdx_text is not None else load_spdx_mit()
    s1 = signal_structural(text)
    s2 = signal_mit_residual(text, spdx)
    osi_plus = bool(s1["osi_plus_rider"] or s2["osi_plus_rider"])
    # Require agreement on MIT-family docs; Llama is non-OSI so s2 is silent.
    if s2["mit_grant_present"]:
        osi_plus = bool(s1["osi_plus_rider"] and s2["osi_plus_rider"])
    rider_kind = None
    if osi_plus:
        n = normalize(text)
        kinds = []
        if "restricted part" in n:
            kinds.append("field-of-use")
        if "training corpus" in n or "evaluation harness" in n:
            kinds.append("no-ml-training-or-eval-folding-for-restricted-parties")
        rider_kind = "+".join(kinds) if kinds else "non-osi-rider"
    elif s1["non_osi_field_of_use"]:
        rider_kind = "non-osi-licence-additional-commercial-and-aup"
    quotes = []
    block = extract_verbatim_block(text)
    if block:
        quotes.append({"kind": "osi-rider-block", "text": block})
    llama = extract_llama_commercial(text)
    if llama:
        quotes.append({"kind": "additional-commercial-terms", "text": llama})
    return {
        "has_non_osi_rider": osi_plus,
        "has_non_osi_licence": bool(s1["non_osi_field_of_use"]),
        "osi_base": "MIT" if s2["mit_grant_present"] else None,
        "rider_kind": rider_kind,
        "signal_structural": s1,
        "signal_mit_residual": s2,
        "quotes": quotes,
        "signals_agree_on_osi_rider": (
            s1["osi_plus_rider"] == s2["osi_plus_rider"]
            if s2["mit_grant_present"]
            else (not s1["osi_plus_rider"])
        ),
    }


def classify_path(path: Path, spdx_text: str | None = None) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    out = classify(text, spdx_text)
    out["path"] = str(path)
    out["sha256"] = sha256_bytes(raw)
    out["bytes"] = len(raw.replace(b"\r\n", b"\n"))
    return out
