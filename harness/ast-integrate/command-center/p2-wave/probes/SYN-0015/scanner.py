"""Quantifier-versus-measured-N overclaim scanner (SYN-0015).

Extracts USE (not mention) of universal quantifiers, binds each sentence to
the measured denominator on the adjacent receipt, and rewrites overclaims to
the scope actually measured. A correctly-scoped rewrite is CONFIRMED for the
underlying work: the finding is the sentence, not the code.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

QUANTIFIERS: list[tuple[str, re.Pattern[str]]] = [
    ("no unit", re.compile(r"\bno units?\b", re.I)),
    ("100 percent", re.compile(r"\b100\s*(?:percent|%)", re.I)),
    ("every", re.compile(r"\bevery\b", re.I)),
    ("always", re.compile(r"\balways\b", re.I)),
    ("never", re.compile(r"\bnever\b", re.I)),
    ("none", re.compile(r"(?<![=:])\bnone\b", re.I)),
    (
        "zero",
        re.compile(
            r"\bzero\s+(?:of\b|(?:units?|claims?|files?|cases?|"
            r"contradictions?|probes?|drops?|gaps?|failures?|errors?)\b)",
            re.I,
        ),
    ),
    ("all", re.compile(r"\ball\b", re.I)),
]
INLINE_PAIR = re.compile(r"\b(\d+)\s+of\s+(\d+)\b", re.I)
FENCE = re.compile(r"```.*?```", re.S)
BACKTICK = re.compile(r"`[^`\n]*`")
DOUBLE = re.compile(r'"[^"\n]*"')
CURLY = re.compile(r"“[^”]*”")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _space(match: re.Match[str]) -> str:
    return " " * len(match.group(0))


def mask_mentions(text: str) -> str:
    """Blank quoted / fenced / backtick spans (use-vs-mention)."""
    text = FENCE.sub(_space, text)
    text = BACKTICK.sub(_space, text)
    text = DOUBLE.sub(_space, text)
    text = CURLY.sub(_space, text)
    return text


def split_sentences(text: str) -> list[str]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    parts = SENT_SPLIT.split(text)
    return [p.strip() for p in parts if p.strip()]


def first_quantifier(text: str) -> str | None:
    for name, pat in QUANTIFIERS:
        if pat.search(text):
            return name
    return None


def load_receipt(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"receipt not an object: {path}")
    measured = int(doc["measured_n"])
    population = int(doc["population_n"])
    if population < 1:
        raise ValueError(f"population_n < 1: {path}")
    rel = path.as_posix()
    return {
        "id": str(doc.get("id") or path.stem),
        "measured_n": measured,
        "population_n": population,
        "label": str(doc.get("label") or "units"),
        "path": rel,
        "metric": str(doc.get("metric") or ""),
    }


def inline_denominator(text: str) -> dict[str, int] | None:
    hits = [(int(a), int(b)) for a, b in INLINE_PAIR.findall(text)]
    if not hits:
        return None
    for n, n_pop in hits:
        if n_pop >= 1 and n <= n_pop:
            return {"measured_n": n, "population_n": n_pop}
    n, n_pop = hits[0]
    return {"measured_n": n, "population_n": n_pop}


def names_denominator(sentence: str, measured_n: int, population_n: int) -> bool:
    t = sentence
    if re.search(rf"\b{measured_n}\s+of\s+{population_n}\b", t, re.I):
        return True
    if re.search(rf"\b{measured_n}/{population_n}\b", t):
        return True
    if re.search(rf"\b{measured_n}\s+measured\b", t, re.I) and re.search(
        rf"\b{population_n}\b", t
    ):
        return True
    if re.search(rf"\bof the {measured_n}\b", t, re.I) and re.search(
        rf"\b{population_n}\b", t
    ):
        return True
    return False


def asserted_population(quantifier: str, label: str) -> str:
    if quantifier in {"no unit", "none", "zero", "never"}:
        return f"empty set of all {label} (universal negative)"
    return f"all {label} (universal affirmative)"


def scope_bounded_rewrite(
    sentence: str,
    quantifier: str,
    measured_n: int,
    population_n: int,
    label: str,
) -> str:
    token = {
        "no unit": f"none of the {measured_n} measured {label}",
        "every": f"each of the {measured_n} measured {label}",
        "all": f"the {measured_n} measured {label}",
        "always": f"in each of the {measured_n} measured cases",
        "never": f"in none of the {measured_n} measured cases",
        "none": f"none of the {measured_n} measured {label}",
        "zero": f"zero of the {measured_n} measured {label}",
        "100 percent": f"{measured_n} of {population_n}",
    }[quantifier]
    pat = dict(QUANTIFIERS)[quantifier]
    out = pat.sub(token, sentence, count=1)
    scope = f"{measured_n} of {population_n}"
    if scope not in out:
        out = out.rstrip().rstrip(".") + f" ({scope})."
    return out


def _coverage(measured_n: int, population_n: int) -> str:
    if measured_n < population_n:
        return "subset"
    return "full"


def classify_sentence(
    sentence: str,
    receipt: dict[str, Any] | None,
    *,
    strip_mentions: bool = True,
    source_path: str = "",
    sentence_index: int = 0,
) -> dict[str, Any] | None:
    """Return a finding dict, or None if the sentence is not a quantified USE.

    Finding kinds:
      overclaim — universal USE, bound denominator is a proper subset, not scoped
      confirmed-scoped — universal USE already named to measured N
      confirmed-full — universal USE and measured_n == population_n
      mention — quantifier only inside quotes (returned only when strip_mentions=False)
      unbound — universal USE with no denominator
    """
    visible = mask_mentions(sentence) if strip_mentions else sentence
    quantifier = first_quantifier(visible)
    if quantifier is None:
        return None
    base = {
        "sentence": sentence,
        "quantifier": quantifier,
        "source_path": source_path,
        "sentence_index": sentence_index,
        "use_vs_mention": "use" if strip_mentions else "unmasked",
    }
    if receipt is None:
        return {
            **base,
            "kind": "unbound",
            "classification": "denominator-unavailable",
        }
    measured_n = int(receipt["measured_n"])
    population_n = int(receipt["population_n"])
    label = str(receipt.get("label") or "units")
    scoped = names_denominator(sentence, measured_n, population_n)
    if scoped:
        return {
            **base,
            "kind": "confirmed-scoped",
            "classification": None,
            "underlying_work_verdict": "CONFIRMED",
            "measured_population": {
                "measured_n": measured_n,
                "population_n": population_n,
                "coverage": _coverage(measured_n, population_n),
                "label": label,
            },
        }
    if measured_n >= population_n:
        return {
            **base,
            "kind": "confirmed-full",
            "classification": None,
            "underlying_work_verdict": "CONFIRMED",
            "measured_population": {
                "measured_n": measured_n,
                "population_n": population_n,
                "coverage": "full",
                "label": label,
            },
        }
    rewrite = scope_bounded_rewrite(
        sentence, quantifier, measured_n, population_n, label
    )
    rel = str(receipt.get("path") or "")
    return {
        **base,
        "kind": "overclaim",
        "classification": "overclaim",
        "underlying_work_verdict": "CONFIRMED",
        "asserted_population": asserted_population(quantifier, label),
        "measured_population": {
            "measured_n": measured_n,
            "population_n": population_n,
            "coverage": "subset",
            "label": label,
        },
        "receipt_anchor": {
            "path": rel,
            "receipt_id": receipt.get("id"),
            "pointer": "measured_n,population_n",
        },
        "corrected_sentence": rewrite,
    }


def scan_text(
    text: str,
    receipt: dict[str, Any] | None,
    *,
    strip_mentions: bool = True,
    source_path: str = "",
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for i, sentence in enumerate(split_sentences(text)):
        row = classify_sentence(
            sentence,
            receipt,
            strip_mentions=strip_mentions,
            source_path=source_path,
            sentence_index=i,
        )
        if row is not None:
            findings.append(row)
    return findings


def bind_receipt(synthesis_path: Path, text: str) -> dict[str, Any] | None:
    sibling = synthesis_path.parent / "receipt.json"
    if sibling.is_file():
        rec = load_receipt(sibling)
        rec["path"] = _rel_or_posix(sibling)
        return rec
    inline = inline_denominator(text)
    if inline is None:
        return None
    return {
        "id": "inline",
        "measured_n": inline["measured_n"],
        "population_n": inline["population_n"],
        "label": "units",
        "path": _rel_or_posix(synthesis_path),
        "metric": "inline-k-of-N",
    }


def _rel_or_posix(path: Path) -> str:
    try:
        return path.resolve().as_posix()
    except OSError:
        return path.as_posix()


def scan_dir(
    directory: Path,
    *,
    strip_mentions: bool = True,
) -> dict[str, Any]:
    syn = directory / "synthesis.txt"
    if not syn.is_file():
        raise FileNotFoundError(syn)
    text = syn.read_text(encoding="utf-8")
    receipt = bind_receipt(syn, text)
    findings = scan_text(
        text,
        receipt,
        strip_mentions=strip_mentions,
        source_path=_rel_or_posix(syn),
    )
    overclaims = [f for f in findings if f.get("kind") == "overclaim"]
    return {
        "path": _rel_or_posix(syn),
        "receipt": receipt,
        "findings": findings,
        "overclaims": overclaims,
        "unbound": [f for f in findings if f.get("kind") == "unbound"],
        "quantified_use": findings,
    }


def flagged_record(row: dict[str, Any], fid: str) -> dict[str, Any]:
    mp = row["measured_population"]
    return {
        "id": fid,
        "sentence": row["sentence"],
        "quantifier": row["quantifier"],
        "asserted_population": row["asserted_population"],
        "measured_population": {
            "measured_n": mp["measured_n"],
            "population_n": mp["population_n"],
            "coverage": mp["coverage"],
            "label": mp.get("label") or "units",
        },
        "receipt_anchor": row["receipt_anchor"],
        "corrected_sentence": row["corrected_sentence"],
        "classification": "overclaim",
        "underlying_work_verdict": "CONFIRMED",
        "source_path": row.get("source_path"),
        "corpus": row.get("corpus"),
        "note": (
            "Correctly-scoped rewrite is CONFIRMED for the underlying work; "
            "the finding is the sentence, not the code."
        ),
    }
