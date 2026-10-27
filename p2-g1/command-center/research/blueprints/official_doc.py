"""Official-document audit: only allowlisted URLs count as official; fetch still required."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

from research.blueprints.citation import (
    UNRESOLVED,
    FetchResult,
    fetch_citation,
)


@dataclass
class OfficialDocVerdict:
    id: str
    url: str
    quoted_span: str
    official: bool
    status: str
    fetch_ok: bool
    fetch_reason: str
    quote_found: bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OfficialDocAudit:
    verdicts: list[OfficialDocVerdict]
    allowlist: list[str]

    @property
    def coverage(self) -> float:
        if not self.verdicts:
            return 1.0
        scored = sum(1 for v in self.verdicts if v.status)
        return scored / len(self.verdicts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowlist": list(self.allowlist),
            "coverage": self.coverage,
            "unresolved_ids": [v.id for v in self.verdicts if v.status == UNRESOLVED],
            "verdicts": [v.to_dict() for v in self.verdicts],
        }


def audit_official_docs(
    documents: Iterable[Mapping[str, Any]],
    allowlist: Sequence[str],
    fetch=fetch_citation,
) -> OfficialDocAudit:
    allowed = set(allowlist)
    verdicts: list[OfficialDocVerdict] = []
    for doc in documents:
        url = str(doc.get("url") or "")
        cid = str(doc.get("id") or "")
        span = str(doc.get("quoted_span") or "")
        official = url in allowed
        fetched: FetchResult = fetch(doc)
        if not fetched.ok:
            status = UNRESOLVED
            found: bool | None = None
        else:
            found = span in (fetched.body or "") if span else False
            status = "RESOLVED" if found and official else UNRESOLVED
        verdicts.append(
            OfficialDocVerdict(
                id=cid,
                url=url,
                quoted_span=span,
                official=official,
                status=status,
                fetch_ok=fetched.ok,
                fetch_reason=fetched.reason,
                quote_found=found,
            )
        )
    return OfficialDocAudit(verdicts=verdicts, allowlist=list(allowlist))
