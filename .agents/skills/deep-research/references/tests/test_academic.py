"""Academic record consolidation tests."""

from research_harness.academic import AcademicRecord, consolidate_academic_records, normalize_doi


def test_normalize_doi_accepts_url_and_prefix_variants():
    expected = "10.1000/xyz.123"
    assert normalize_doi("https://doi.org/10.1000/XYZ.123") == expected
    assert normalize_doi("doi: 10.1000/xyz.123") == expected


def test_duplicate_doi_records_consolidate_without_erasing_provenance_or_type():
    records = (
        AcademicRecord(
            title="A Study",
            provider="exa",
            doi="https://doi.org/10.1000/XYZ",
            publication_type="preprint",
            year=2025,
        ),
        AcademicRecord(
            title="A Study: final version",
            provider="scholarly-access",
            doi="10.1000/xyz",
            url="https://publisher.example/paper",
            publication_type="peer_reviewed_primary",
            year=2026,
        ),
    )
    consolidated = consolidate_academic_records(records)
    assert len(consolidated) == 1
    paper = consolidated[0]
    assert paper.doi == "10.1000/xyz"
    assert paper.providers == ("exa", "scholarly-access")
    assert paper.publication_types == ("peer_reviewed_primary", "preprint")
    assert paper.url == "https://publisher.example/paper"


def test_title_fallback_deduplicates_doi_less_records():
    records = (
        AcademicRecord("  The   Same Study! ", "exa"),
        AcademicRecord("the same study", "scholarly-access", year=2026),
    )
    consolidated = consolidate_academic_records(records)
    assert len(consolidated) == 1
    assert consolidated[0].providers == ("exa", "scholarly-access")


def test_consolidation_joins_doi_record_to_title_only_discovery_record():
    records = (
        AcademicRecord(
            "A Unified Paper",
            "paper-search",
            publication_type="preprint",
        ),
        AcademicRecord(
            "A Unified Paper",
            "scholarly-access",
            doi="10.1000/unified",
            url="https://publisher.example/paper",
            publication_type="peer_reviewed_primary",
        ),
    )
    consolidated = consolidate_academic_records(records)
    assert len(consolidated) == 1
    assert consolidated[0].canonical_id == "doi:10.1000/unified"
    assert consolidated[0].providers == ("paper-search", "scholarly-access")


def test_different_titles_without_identifiers_remain_distinct():
    records = (
        AcademicRecord("Study Alpha", "exa"),
        AcademicRecord("Study Beta", "exa"),
    )
    assert len(consolidate_academic_records(records)) == 2


def test_same_title_does_not_merge_conflicting_dois():
    records = (
        AcademicRecord("Annual report", "source-a", doi="10.1000/alpha"),
        AcademicRecord("Annual report", "source-b", doi="10.1000/beta"),
    )
    consolidated = consolidate_academic_records(records)
    assert len(consolidated) == 2
    assert {paper.doi for paper in consolidated} == {"10.1000/alpha", "10.1000/beta"}


def test_same_title_does_not_merge_conflicting_canonical_urls():
    records = (
        AcademicRecord("Annual report", "source-a", url="https://a.example/report"),
        AcademicRecord("Annual report", "source-b", url="https://b.example/report"),
    )
    assert len(consolidate_academic_records(records)) == 2
