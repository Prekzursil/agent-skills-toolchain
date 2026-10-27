"""Legal ingest gate: SPDX signals, adverse inference, copyleft. WFA-0031."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceInput:
    source_id: str
    origin: str = ""
    license_text: str | None = None
    license_filename: str | None = None
    license_http_status: int | None = None
    api_doc: dict[str, Any] | None = None
    readme_text: str | None = None
    terms_text: str | None = None


@dataclass
class SourceResult:
    source_id: str
    classification: str
    ingest_mode: str
    code_carried: bool
    signal_a_spdx: str | None
    signal_b_spdx: str | None
    readme_badge_spdx: str | None
    readme_badge_used: bool
    obligations: list[dict[str, Any]] = field(default_factory=list)
    signals_agree: bool = True
    riders: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def api_payload_is_error(doc: dict[str, Any] | None) -> bool:
    if not isinstance(doc, dict):
        return True
    if doc.get("message") and doc.get("documentation_url"):
        return True
    if str(doc.get("error") or ""):
        return True
    return False


def _badge_spdx(readme: str | None) -> str | None:
    if not readme:
        return None
    text = readme.upper()
    if "MIT" in text:
        return "MIT"
    if "GPL-3" in text or "GPL 3" in text:
        return "GPL-3.0"
    return None


def _spdx_from_license(text: str | None) -> str | None:
    if not text:
        return None
    t = text.upper()
    if "GNU GENERAL PUBLIC LICENSE" in t and "VERSION 3" in t:
        return "GPL-3.0"
    if "APACHE LICENSE" in t:
        return "Apache-2.0"
    if "PERMISSION IS HEREBY GRANTED, FREE OF CHARGE" in t:
        return "MIT"
    if "MIT LICENSE" in t:
        return "MIT"
    return None


def _spdx_from_api(doc: dict[str, Any] | None) -> str | None:
    if not isinstance(doc, dict) or api_payload_is_error(doc):
        return None
    lic = doc.get("license") or doc.get("spdx") or {}
    if isinstance(lic, str):
        return lic
    if isinstance(lic, dict):
        return lic.get("spdx_id") or lic.get("key") or lic.get("name")
    return None


class LegalGate:
    def evaluate(self, src: SourceInput) -> SourceResult:
        badge = _badge_spdx(src.readme_text)
        a = _spdx_from_license(src.license_text)
        b = _spdx_from_api(src.api_doc)
        obligations: list[dict[str, Any]] = []
        code_carried = False
        if a is None:
            classification = "ADVERSE-UNLICENSED"
            ingest_mode = "MECHANISM_ONLY"
            obligations.append({"kind": "adverse-inference", "detail": "no license blob"})
            if src.terms_text:
                classification = "ADVERSE-UNLICENSED"
        elif a == "GPL-3.0":
            classification = "COPYLEFT"
            ingest_mode = "MECHANISM_ONLY"
            obligations.append({"kind": "copyleft", "spdx": a})
        elif a == "MIT" and (b in {None, "MIT"}):
            classification = "PERMISSIVE"
            ingest_mode = "ALLOW"
            code_carried = True
        elif a != b and b is not None:
            classification = "DISAGREE"
            ingest_mode = "MECHANISM_ONLY"
            obligations.append({"kind": "signal-disagreement", "a": a, "b": b})
        else:
            classification = "RESTRICTIVE" if a not in {"MIT", "Apache-2.0", "BSD-3-Clause"} else "PERMISSIVE"
            ingest_mode = "MECHANISM_ONLY" if classification != "PERMISSIVE" else "ALLOW"
            code_carried = ingest_mode == "ALLOW"
        return SourceResult(
            source_id=src.source_id,
            classification=classification,
            ingest_mode=ingest_mode,
            code_carried=code_carried,
            signal_a_spdx=a,
            signal_b_spdx=b,
            readme_badge_spdx=badge,
            readme_badge_used=False,
            obligations=obligations,
            signals_agree=(a == b) if a and b else True,
            riders=["openai-anthropic"] if "rider" in src.source_id else [],
        )

    def evaluate_many(self, sources: list[SourceInput]) -> list[SourceResult]:
        return [self.evaluate(s) for s in sources]


def evaluate_many(sources: list[SourceInput]) -> list[SourceResult]:
    return LegalGate().evaluate_many(sources)
