"""Catalog tests imported by IMP-0073 probes."""
from __future__ import annotations

from tools.marketplace.index_migrate import (
    COMPATIBILITY_WINDOW_VERSIONS,
    CURRENT_SCHEMA_VERSION,
    UNSUPPORTED,
    file_record_count,
    lossy_migrate_1_to_2,
    migrate,
    parse_index,
    schema_version_of,
    semantics,
)


def sample_v1_index() -> dict:
    return {
        "schema_version": 1,
        "plugins": [
            {"name": "alpha", "version": "1.0.0"},
            {"name": "beta", "version": "1.2.0"},
            {"name": "gamma", "version": "0.9.0"},
        ],
    }


def test_round_trip_preserves_semantics() -> None:
    v1 = sample_v1_index()
    v2 = migrate(v1, 2)
    back = migrate(v2, 1)
    assert semantics(v1) == semantics(v2) == semantics(back)
    assert schema_version_of(v2) == CURRENT_SCHEMA_VERSION
    assert file_record_count(v2) > file_record_count(v1)


def test_lossy_migration_fails_round_trip() -> None:
    v1 = sample_v1_index()
    lossy = lossy_migrate_1_to_2(v1)
    back = migrate(lossy, 1)
    assert semantics(v1) != semantics(back)


def test_compatibility_window_is_a_number_of_versions() -> None:
    assert isinstance(COMPATIBILITY_WINDOW_VERSIONS, int)
    assert COMPATIBILITY_WINDOW_VERSIONS >= 1


def test_old_parser_declares_unsupported() -> None:
    v2 = migrate(sample_v1_index(), 2)
    parsed = parse_index(v2, parser_version=1)
    assert parsed.status == UNSUPPORTED
    assert parsed.records is None
