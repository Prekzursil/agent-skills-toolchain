"""Keyless SureChEMBL client and response normalization for patent FTO triage."""

from __future__ import annotations

import html
import re
import time
from collections.abc import Callable, Mapping
from typing import Any, Self
from urllib.parse import quote
from uuid import UUID

import httpx

SURECHEMBL_BASE_URL = "https://www.surechembl.org/api/"
PROVIDER = "SureChEMBL"
USER_AGENT = "patent-search-mcp/0.1 (+https://www.surechembl.org/)"
FTO_CAVEAT = (
    "Triage only: a SureChEMBL structure hit is evidence of an extracted chemical-to-patent "
    "association, not a legal conclusion about novelty, claim scope, validity, ownership, "
    "expiry, or freedom to operate. Review claims and patent families with qualified counsel."
)

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
_PATENT_ID_RE = re.compile(r"^[A-Z]{2,3}-[A-Z0-9]+(?:-[A-Z0-9]+)+$")
_TAG_RE = re.compile(r"<[^>]*>")
_WHITESPACE_RE = re.compile(r"\s+")


class PatentInputError(ValueError):
    """Raised when an MCP-facing input fails boundary validation."""


class PatentSearchError(RuntimeError):
    """Raised when SureChEMBL cannot satisfy a valid request."""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _dicts(value: Any) -> list[Mapping[str, Any]]:
    return [item for item in _as_list(value) if isinstance(item, Mapping)]


def _first_dict(value: Any) -> Mapping[str, Any]:
    values = _dicts(value)
    return values[0] if values else {}


def _clean_scalar(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.casefold() == "null" else text


def _clean_text(value: Any) -> str:
    text = html.unescape(_clean_scalar(value))
    text = _TAG_RE.sub(" ", text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return f"{text[: max_chars - 3].rstrip()}...", True


def _format_date(value: Any) -> str:
    text = _clean_scalar(value)
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _validate_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise PatentInputError(f"{name} must be an integer")
    if not minimum <= value <= maximum:
        raise PatentInputError(f"{name} must be between {minimum} and {maximum}")
    return value


def validate_smiles(smiles: Any) -> str:
    if not isinstance(smiles, str):
        raise PatentInputError("smiles must be a string")
    value = smiles.strip()
    if not value:
        raise PatentInputError("smiles must not be empty")
    if len(value) > 2_000:
        raise PatentInputError("smiles must be at most 2000 characters")
    if _CONTROL_RE.search(value):
        raise PatentInputError("smiles must not contain control characters")
    return value


def validate_search_id(search_id: Any) -> str:
    if not isinstance(search_id, str) or not search_id.strip():
        raise PatentInputError("search_id must be a UUID string")
    try:
        return str(UUID(search_id.strip()))
    except ValueError as exc:
        raise PatentInputError("search_id must be a valid UUID") from exc


def validate_patent_id(patent_id: Any) -> str:
    if not isinstance(patent_id, str):
        raise PatentInputError("patent_id must be a string")
    value = patent_id.strip().upper()
    if not value:
        raise PatentInputError("patent_id must not be empty")
    if len(value) > 80 or _CONTROL_RE.search(value) or not _PATENT_ID_RE.fullmatch(value):
        raise PatentInputError(
            "patent_id must use SureChEMBL UCID form, for example WO-2020096695-A1"
        )
    return value


def _response_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, Mapping):
        for key in ("error_message", "detail", "message", "error"):
            detail = _clean_text(payload.get(key))
            if detail:
                return detail[:500]
    return _clean_text(response.text)[:500] or "no response detail"


def _preferred_text(entries: list[tuple[str, str]]) -> str:
    for language, text in entries:
        if language.casefold() == "en" and text:
            return text
    return next((text for _, text in entries if text), "")


def _dedupe_strings(values: list[str], limit: int = 100) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        key = re.sub(r"[^a-z0-9]", "", cleaned.casefold())
        if cleaned and key and key not in seen:
            seen.add(key)
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _title_entries(technical_data: Mapping[str, Any]) -> list[dict[str, str]]:
    titles: list[dict[str, str]] = []
    for item in _dicts(technical_data.get("inventionTitles")):
        title = _clean_text(item.get("title"))
        if title:
            titles.append({"language": _clean_scalar(item.get("lang")), "title": title})
    return titles


def _search_result_title(metadata: Mapping[str, Any]) -> str:
    candidates: list[tuple[str, str]] = []
    for group in _dicts(metadata.get("titles")):
        language = _clean_scalar(group.get("lang"))
        for title in _as_list(group.get("titles")):
            cleaned = _clean_text(title)
            if cleaned:
                candidates.append((language, cleaned))
    return _preferred_text(candidates)


def _party_name(item: Mapping[str, Any]) -> str:
    addressbook = item.get("addressbook")
    source = addressbook if isinstance(addressbook, Mapping) else item
    for key in ("name", "organizationName", "orgname"):
        value = _clean_text(source.get(key))
        if value:
            return value
    parts = [
        _clean_text(source.get("firstName")),
        _clean_text(source.get("middleName")),
        _clean_text(source.get("lastName")),
    ]
    return " ".join(part for part in parts if part)


def _parties(parties: Mapping[str, Any], group: str, singular: str) -> list[str]:
    container = parties.get(group)
    if not isinstance(container, Mapping):
        return []
    return _dedupe_strings([_party_name(item) for item in _dicts(container.get(singular))])


def _classifications(technical_data: Mapping[str, Any], outer: str, inner: str) -> list[str]:
    values: list[str] = []
    for container in _dicts(technical_data.get(outer)):
        entries = _dicts(container.get(inner)) or [container]
        values.extend(_clean_text(entry.get("classification")) for entry in entries)
    return _dedupe_strings(values)


def _section_text(entries: Any) -> str:
    candidates: list[tuple[str, str]] = []
    for item in _dicts(entries):
        section = item.get("section")
        if not isinstance(section, Mapping):
            continue
        content = _clean_text(section.get("content"))
        if content:
            candidates.append((_clean_scalar(item.get("lang")), content))
    return _preferred_text(candidates)


def _legal_events(document: Mapping[str, Any], limit: int = 10) -> list[dict[str, str]]:
    legal_status = document.get("legalStatus")
    if not isinstance(legal_status, Mapping):
        return []
    events: list[dict[str, str]] = []
    for event in _dicts(legal_status.get("legal-event")):
        body = event.get("legal-event-body")
        title_value: Any = ""
        if isinstance(body, Mapping):
            title_value = body.get("event-title")
        if isinstance(title_value, Mapping):
            title_value = title_value.get("$") or title_value.get("content")
        events.append(
            {
                "date": _format_date(event.get("@date")),
                "country": _clean_scalar(event.get("@country")),
                "code": _clean_scalar(event.get("@code")),
                "impact": _clean_scalar(event.get("@impact")),
                "title": _clean_text(title_value),
            }
        )
    events.sort(key=lambda event: event["date"], reverse=True)
    return events[:limit]


class SureChEMBLClient:
    """Small synchronous client for the keyless SureChEMBL v1 REST API."""

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._owns_client = http_client is None
        self._client = http_client or httpx.Client(
            base_url=SURECHEMBL_BASE_URL,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
        )
        self._sleep = sleeper
        self._monotonic = monotonic

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Mapping[str, Any]:
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise PatentSearchError("SureChEMBL request timed out") from exc
        except httpx.HTTPStatusError as exc:
            detail = _response_error(exc.response)
            raise PatentSearchError(
                f"SureChEMBL returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.RequestError as exc:
            raise PatentSearchError(f"SureChEMBL request failed: {exc.__class__.__name__}") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise PatentSearchError("SureChEMBL returned invalid JSON") from exc
        if not isinstance(payload, Mapping):
            raise PatentSearchError("SureChEMBL returned an unexpected response shape")
        if _clean_scalar(payload.get("status")).upper() != "OK":
            detail = _clean_text(payload.get("error_message")) or "request was not successful"
            raise PatentSearchError(f"SureChEMBL error: {detail[:500]}")
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise PatentSearchError(
                "SureChEMBL response did not contain an object-valued data field"
            )
        return data

    def start_substructure_search(self, smiles: Any, structure_limit: Any = 25) -> str:
        normalized_smiles = validate_smiles(smiles)
        normalized_limit = _validate_int(structure_limit, "structure_limit", 1, 100)
        data = self._request(
            "POST",
            "search/structure",
            json={
                "StructureSearchRequest": {
                    "struct": normalized_smiles,
                    "structSearchType": "SUBSTRUCTURE",
                    "maxResults": normalized_limit,
                    "saveSearch": "false",
                    "query": "",
                    "options": "",
                    "chemTermFilter": "",
                    "childOf": "",
                    "searchAppendix": "",
                    "docSectionFilter": "",
                }
            },
        )
        search_id = _clean_scalar(data.get("hash"))
        return validate_search_id(search_id)

    def search_status(self, search_id: Any) -> Mapping[str, Any]:
        normalized_id = validate_search_id(search_id)
        return self._request("GET", f"search/{quote(normalized_id, safe='')}/status")

    def _wait_for_search(self, search_id: str, wait_seconds: int) -> Mapping[str, Any]:
        deadline = self._monotonic() + wait_seconds
        while True:
            status = self.search_status(search_id)
            message = _clean_text(status.get("message"))
            message_folded = message.casefold()
            if "finished" in message_folded:
                return status
            if "failed" in message_folded or "error" in message_folded:
                raise PatentSearchError(f"SureChEMBL structure search failed: {message}")
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                return status
            self._sleep(min(0.5, remaining))

    def structure_results(self, search_id: Any, structure_limit: Any = 25) -> Mapping[str, Any]:
        normalized_id = validate_search_id(search_id)
        normalized_limit = _validate_int(structure_limit, "structure_limit", 1, 100)
        return self._request(
            "GET",
            f"search/{quote(normalized_id, safe='')}/results",
            params={"page": 1, "max_results": normalized_limit},
        )

    def patents_for_structures(
        self, chemical_ids: list[str], patent_limit: Any = 50
    ) -> Mapping[str, Any]:
        normalized_limit = _validate_int(patent_limit, "patent_limit", 1, 100)
        if not chemical_ids or len(chemical_ids) > 100:
            raise PatentInputError("chemical_ids must contain between 1 and 100 IDs")
        if any(not re.fullmatch(r"\d+", chemical_id) for chemical_id in chemical_ids):
            raise PatentInputError("chemical_ids must contain decimal SureChEMBL IDs")
        return self._request(
            "POST",
            "search/documents_for_structures",
            params={
                "chemicalIds": ",".join(chemical_ids),
                "page": 1,
                "itemsPerPage": normalized_limit,
            },
            json={},
        )

    @staticmethod
    def _normalize_structures(
        data: Mapping[str, Any],
    ) -> tuple[list[dict[str, Any]], int]:
        results = data.get("results")
        if not isinstance(results, Mapping):
            return [], 0
        structures: list[dict[str, Any]] = []
        allowed = (
            "chemical_id",
            "name",
            "smiles",
            "inchi_key",
            "mol_formula",
            "mol_weight",
            "similarity",
            "global_frequency",
        )
        for item in _dicts(results.get("structures")):
            structures.append(
                {key: item.get(key) for key in allowed if item.get(key) not in (None, "")}
            )
        return structures, _safe_int(results.get("total_hits"), len(structures))

    @staticmethod
    def _normalize_patents(data: Mapping[str, Any]) -> tuple[list[dict[str, str]], int]:
        results = data.get("results")
        if not isinstance(results, Mapping):
            return [], 0
        patents: list[dict[str, str]] = []
        for item in _dicts(results.get("documents")):
            metadata = item.get("metadata")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            patent_id = _clean_scalar(item.get("docId"))
            if not patent_id:
                continue
            patents.append(
                {
                    "patent_id": patent_id,
                    "title": _search_result_title(metadata),
                    "publication_date": _clean_scalar(metadata.get("pd")),
                    "applicant": _clean_scalar(item.get("pa")),
                }
            )
        return patents, _safe_int(results.get("total_hits"), len(patents))

    def continue_substructure_search(
        self,
        search_id: Any,
        *,
        structure_limit: Any = 25,
        patent_limit: Any = 50,
        wait_seconds: Any = 10,
    ) -> dict[str, Any]:
        normalized_id = validate_search_id(search_id)
        normalized_structure_limit = _validate_int(structure_limit, "structure_limit", 1, 100)
        normalized_patent_limit = _validate_int(patent_limit, "patent_limit", 1, 100)
        normalized_wait = _validate_int(wait_seconds, "wait_seconds", 0, 60)
        status = self._wait_for_search(normalized_id, normalized_wait)
        message = _clean_text(status.get("message"))
        if "finished" not in message.casefold():
            return {
                "ok": True,
                "status": "pending",
                "provider": PROVIDER,
                "search_id": normalized_id,
                "message": message or "Structure search is still running.",
                "next_tool": "patent_structure_search_results",
                "fto_caveat": FTO_CAVEAT,
            }

        structure_data = self.structure_results(normalized_id, normalized_structure_limit)
        structures, structure_total = self._normalize_structures(structure_data)
        chemical_ids = [
            str(item["chemical_id"])
            for item in structures
            if str(item.get("chemical_id", "")).isdigit()
        ]
        patents: list[dict[str, str]] = []
        patent_total = 0
        if chemical_ids:
            patent_data = self.patents_for_structures(chemical_ids, normalized_patent_limit)
            patents, patent_total = self._normalize_patents(patent_data)

        query_data = structure_data.get("query")
        query_data = query_data if isinstance(query_data, Mapping) else {}
        return {
            "ok": True,
            "status": "complete",
            "provider": PROVIDER,
            "search_id": normalized_id,
            "query": {
                "smiles": _clean_scalar(query_data.get("structure")),
                "search_type": "substructure",
            },
            "matched_structure_total": structure_total,
            "matched_structure_count_returned": len(structures),
            "matched_structures": structures,
            "patent_total": patent_total,
            "patent_count_returned": len(patents),
            "patents": patents,
            "fto_caveat": FTO_CAVEAT,
        }

    def search_patents_by_substructure(
        self,
        smiles: Any,
        *,
        structure_limit: Any = 25,
        patent_limit: Any = 50,
        wait_seconds: Any = 20,
    ) -> dict[str, Any]:
        normalized_smiles = validate_smiles(smiles)
        normalized_structure_limit = _validate_int(structure_limit, "structure_limit", 1, 100)
        normalized_patent_limit = _validate_int(patent_limit, "patent_limit", 1, 100)
        normalized_wait = _validate_int(wait_seconds, "wait_seconds", 0, 60)
        search_id = self.start_substructure_search(normalized_smiles, normalized_structure_limit)
        result = self.continue_substructure_search(
            search_id,
            structure_limit=normalized_structure_limit,
            patent_limit=normalized_patent_limit,
            wait_seconds=normalized_wait,
        )
        if result["status"] == "pending":
            result["query"] = {
                "smiles": normalized_smiles,
                "search_type": "substructure",
            }
        return result

    def patent_metadata(
        self,
        patent_id: Any,
        *,
        include_abstract: bool = True,
        include_claims: bool = False,
        text_char_limit: Any = 6_000,
    ) -> dict[str, Any]:
        normalized_id = validate_patent_id(patent_id)
        if not isinstance(include_abstract, bool) or not isinstance(include_claims, bool):
            raise PatentInputError("include_abstract and include_claims must be booleans")
        normalized_text_limit = _validate_int(text_char_limit, "text_char_limit", 500, 20_000)
        data = self._request("GET", f"document/{quote(normalized_id, safe='')}/contents")
        contents = data.get("contents")
        contents = contents if isinstance(contents, Mapping) else {}
        document = contents.get("patentDocument")
        if not isinstance(document, Mapping):
            raise PatentSearchError("SureChEMBL document response omitted patentDocument")

        bibliographic = document.get("bibliographicData")
        bibliographic = bibliographic if isinstance(bibliographic, Mapping) else {}
        publication_reference = _first_dict(bibliographic.get("publicationReference"))
        publication_document = _first_dict(publication_reference.get("documentId"))
        technical_data = bibliographic.get("technicalData")
        technical_data = technical_data if isinstance(technical_data, Mapping) else {}
        titles = _title_entries(technical_data)
        preferred_title = _preferred_text([(item["language"], item["title"]) for item in titles])

        application_reference = _first_dict(bibliographic.get("applicationReference"))
        application_document = _first_dict(
            application_reference.get("documentIdList") or application_reference.get("documentId")
        )
        priority_container = bibliographic.get("priorityClaims")
        priority_container = priority_container if isinstance(priority_container, Mapping) else {}
        priority_dates = sorted(
            date
            for claim in _dicts(priority_container.get("priorityClaims"))
            if (date := _format_date(_first_dict(claim.get("documentId")).get("date")))
        )
        parties = bibliographic.get("parties")
        parties = parties if isinstance(parties, Mapping) else {}

        result: dict[str, Any] = {
            "ok": True,
            "status": "complete",
            "provider": PROVIDER,
            "patent_id": _clean_scalar(data.get("doc_id"))
            or _clean_scalar(publication_reference.get("ucid"))
            or normalized_id,
            "title": preferred_title,
            "titles": titles,
            "publication_date": _format_date(publication_document.get("date")),
            "publication_country": _clean_scalar(
                _first_dict(publication_document.get("country")).get("content")
                if isinstance(publication_document.get("country"), Mapping)
                else publication_document.get("country")
            ),
            "application_id": _clean_scalar(application_reference.get("ucid")),
            "application_date": _format_date(application_document.get("date")),
            "earliest_priority_date": priority_dates[0] if priority_dates else "",
            "family_id": _clean_scalar(document.get("family")),
            "applicants": _parties(parties, "applicants", "applicant"),
            "inventors": _parties(parties, "inventors", "inventor"),
            "cpc_classifications": _classifications(
                technical_data, "classificationsCpc", "classificationCpc"
            ),
            "ipcr_classifications": _classifications(
                technical_data, "classificationsIpcr", "classificationIpcr"
            ),
            "legal_events": _legal_events(document),
            "pdf_url": _clean_scalar(document.get("pdfUrl")),
            "has_pdf": bool(document.get("hasPDF")),
            "fto_caveat": FTO_CAVEAT,
            "legal_status_note": (
                "SureChEMBL legal events are informational and may be incomplete or stale; "
                "verify status in each relevant patent office register."
            ),
        }

        if include_abstract:
            abstract, truncated = _truncate(
                _section_text(document.get("abstracts")), normalized_text_limit
            )
            result["abstract"] = abstract
            result["abstract_truncated"] = truncated
        if include_claims:
            claims, truncated = _truncate(
                _section_text(document.get("claimResponses")), normalized_text_limit
            )
            result["claims"] = claims
            result["claims_truncated"] = truncated
        return result
