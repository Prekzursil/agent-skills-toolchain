"""Fixture-backed tests for the keyless SureChEMBL client."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from patent_api import (
    PatentInputError,
    PatentSearchError,
    SureChEMBLClient,
    validate_patent_id,
    validate_search_id,
    validate_smiles,
)

SEARCH_ID = "11111111-1111-4111-8111-111111111111"


def api_response(data: dict, *, status: str = "OK", error: str = "") -> dict:
    return {"status": status, "error_message": error, "data": data}


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[SureChEMBLClient, httpx.Client]:
    http_client = httpx.Client(
        base_url="https://surechembl.example/api/",
        transport=httpx.MockTransport(handler),
    )
    return SureChEMBLClient(http_client=http_client, sleeper=lambda _: None), http_client


def test_substructure_search_uses_root_wrapper_and_resolves_patents() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/api/search/structure":
            payload = json.loads(request.content)
            assert payload == {
                "StructureSearchRequest": {
                    "struct": "c1ccccc1",
                    "structSearchType": "SUBSTRUCTURE",
                    "maxResults": 2,
                    "saveSearch": "false",
                    "query": "",
                    "options": "",
                    "chemTermFilter": "",
                    "childOf": "",
                    "searchAppendix": "",
                    "docSectionFilter": "",
                }
            }
            return httpx.Response(200, json=api_response({"hash": SEARCH_ID}))
        if request.url.path.endswith("/status"):
            return httpx.Response(
                200,
                json=api_response({"message": "Searching finished.", "resultCount": 2}),
            )
        if request.url.path.endswith("/results"):
            assert request.url.params["page"] == "1"
            assert request.url.params["max_results"] == "2"
            return httpx.Response(
                200,
                json=api_response(
                    {
                        "query": {"structure": "c1ccccc1"},
                        "results": {
                            "total_hits": 12,
                            "structures": [
                                {
                                    "chemical_id": "101",
                                    "name": "benzene",
                                    "smiles": "c1ccccc1",
                                    "inchi_key": "UHOVQNZJYSORNB-UHFFFAOYSA-N",
                                    "ignored": "not returned",
                                },
                                {
                                    "chemical_id": "202",
                                    "name": "ethylbenzene",
                                    "smiles": "CCc1ccccc1",
                                },
                            ],
                        },
                    }
                ),
            )
        if request.url.path == "/api/search/documents_for_structures":
            assert request.method == "POST"
            assert request.url.params["chemicalIds"] == "101,202"
            assert request.url.params["itemsPerPage"] == "3"
            assert json.loads(request.content) == {}
            return httpx.Response(
                200,
                json=api_response(
                    {
                        "results": {
                            "total_hits": 7,
                            "documents": [
                                {
                                    "docId": "WO-2024000001-A1",
                                    "metadata": {
                                        "pd": "2024-01-04",
                                        "titles": [
                                            {"lang": "fr", "titles": ["Titre"]},
                                            {
                                                "lang": "en",
                                                "titles": ["Example compound"],
                                            },
                                        ],
                                    },
                                    "pa": "Example Pharma",
                                }
                            ],
                        }
                    }
                ),
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client, http_client = make_client(handler)
    try:
        result = client.search_patents_by_substructure(
            "c1ccccc1", structure_limit=2, patent_limit=3, wait_seconds=0
        )
    finally:
        http_client.close()

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert result["matched_structure_total"] == 12
    assert result["matched_structures"][0]["chemical_id"] == "101"
    assert "ignored" not in result["matched_structures"][0]
    assert result["patent_total"] == 7
    assert result["patents"] == [
        {
            "patent_id": "WO-2024000001-A1",
            "title": "Example compound",
            "publication_date": "2024-01-04",
            "applicant": "Example Pharma",
        }
    ]
    assert calls == [
        "POST /api/search/structure",
        f"GET /api/search/{SEARCH_ID}/status",
        f"GET /api/search/{SEARCH_ID}/results",
        "POST /api/search/documents_for_structures",
    ]


def test_substructure_search_returns_continuation_when_pending() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/search/structure":
            return httpx.Response(200, json=api_response({"hash": SEARCH_ID}))
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json=api_response({"message": "Searching..."}))
        raise AssertionError("pending search must not fetch results")

    client, http_client = make_client(handler)
    try:
        result = client.search_patents_by_substructure("CCO", wait_seconds=0)
    finally:
        http_client.close()

    assert result["status"] == "pending"
    assert result["search_id"] == SEARCH_ID
    assert result["next_tool"] == "patent_structure_search_results"
    assert result["query"] == {"smiles": "CCO", "search_type": "substructure"}


def test_patent_metadata_normalizes_bibliography_claims_and_legal_events() -> None:
    claims = " ".join(["<claim-text>1. A claimed compound.</claim-text>"] * 30)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/document/WO-2024000001-A1/contents"
        document = {
            "bibliographicData": {
                "publicationReference": [
                    {
                        "ucid": "WO-2024000001-A1",
                        "documentId": [
                            {
                                "country": {"content": "WO"},
                                "docNumber": "2024000001",
                                "kind": "A1",
                                "date": "20240104",
                            }
                        ],
                    }
                ],
                "applicationReference": {
                    "ucid": "US-2022999999-W",
                    "documentIdList": [{"date": "20230701"}],
                },
                "priorityClaims": {
                    "priorityClaims": [
                        {"documentId": {"date": "20220102"}},
                        {"documentId": {"date": "20211231"}},
                    ]
                },
                "technicalData": {
                    "inventionTitles": [
                        {"lang": "FR", "title": "Titre"},
                        {"lang": "EN", "title": "A useful compound"},
                    ],
                    "classificationsCpc": [
                        {"classificationCpc": [{"classification": "C07D  401/14"}]}
                    ],
                    "classificationsIpcr": [
                        {"classificationIpcr": [{"classification": "A61K  31/00"}]}
                    ],
                },
                "parties": {
                    "applicants": {
                        "applicant": [
                            {"addressbook": {"lastName": "Example Pharma Inc"}},
                            {"addressbook": {"lastName": "EXAMPLE PHARMA, INC."}},
                        ]
                    },
                    "inventors": {
                        "inventor": [
                            {
                                "addressbook": {
                                    "firstName": "Ada",
                                    "lastName": "Lovelace",
                                }
                            }
                        ]
                    },
                },
            },
            "family": "12345",
            "abstracts": [
                {"lang": "FR", "section": {"content": "Resume"}},
                {
                    "lang": "EN",
                    "section": {"content": "An <b>English</b> abstract.</p>"},
                },
            ],
            "claimResponses": {"lang": "EN", "section": {"content": claims}},
            "legalStatus": {
                "legal-event": [
                    {
                        "@date": "20250203",
                        "@country": "WO",
                        "@code": "ENP",
                        "@impact": "+",
                        "legal-event-body": {"event-title": {"$": "ENTRY INTO NATIONAL PHASE"}},
                    }
                ]
            },
            "pdfUrl": "https://example.test/patent.pdf",
            "hasPDF": True,
        }
        return httpx.Response(
            200,
            json=api_response(
                {"doc_id": "WO-2024000001-A1", "contents": {"patentDocument": document}}
            ),
        )

    client, http_client = make_client(handler)
    try:
        result = client.patent_metadata(
            "wo-2024000001-a1", include_claims=True, text_char_limit=500
        )
    finally:
        http_client.close()

    assert result["title"] == "A useful compound"
    assert result["publication_date"] == "2024-01-04"
    assert result["publication_country"] == "WO"
    assert result["application_date"] == "2023-07-01"
    assert result["earliest_priority_date"] == "2021-12-31"
    assert result["applicants"] == ["Example Pharma Inc"]
    assert result["inventors"] == ["Ada Lovelace"]
    assert result["cpc_classifications"] == ["C07D 401/14"]
    assert result["abstract"] == "An English abstract."
    assert result["claims_truncated"] is True
    assert len(result["claims"]) == 500
    assert "<claim-text>" not in result["claims"]
    assert result["legal_events"][0]["date"] == "2025-02-03"
    assert result["has_pdf"] is True


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: validate_smiles(""), "must not be empty"),
        (lambda: validate_smiles("CC\nO"), "control characters"),
        (lambda: validate_search_id("not-a-uuid"), "valid UUID"),
        (lambda: validate_patent_id("2024000001"), "SureChEMBL UCID"),
    ],
)
def test_boundary_validation(call: Callable[[], object], message: str) -> None:
    with pytest.raises(PatentInputError, match=message):
        call()


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            httpx.Response(503, json={"error_message": "maintenance"}),
            "HTTP 503: maintenance",
        ),
        (
            httpx.Response(
                200,
                json=api_response({}, status="BAD_REQUEST", error="bad structure"),
            ),
            "SureChEMBL error: bad structure",
        ),
    ],
)
def test_provider_errors_are_actionable(response: httpx.Response, message: str) -> None:
    client, http_client = make_client(lambda _: response)
    try:
        with pytest.raises(PatentSearchError, match=message):
            client.start_substructure_search("CCO")
    finally:
        http_client.close()
