#!/usr/bin/env python3
"""CC-0019 tests: fail-closed without corpus; conservation/planted/idempotence on fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import corpus_normalize as cn
import pytest

REPO = Path(__file__).resolve().parents[3]


def _mini_corpus(tmp_path: Path) -> Path:
    """Build a tiny fixture corpus. Not a substitute for the real mount."""
    root = tmp_path / "harness-restore-fixture"
    root.mkdir()
    (root / "_USER-PROMPTS.md").write_text(
        "# Prompt One\n\n## Finding Alpha\n\nAlpha body text for resolve.\n\n"
        "## Finding Beta\n\nBeta body text distinct.\n",
        encoding="utf-8",
    )
    (root / "07-OPTION-UNIVERSE.md").write_text(
        "# Options\n\n## Option Card One\n\nDo the thing via mechanism X.\n",
        encoding="utf-8",
    )
    (root / "findings.json").write_text(
        json.dumps(
            {
                "findings": [
                    {
                        "id": "F-1",
                        "title": "Incident note",
                        "claim": "Service timed out under load",
                    },
                    {
                        "id": "F-2",
                        "title": "Duplicate mech",
                        "claim": "Service timed out under load",
                    },
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "empty.txt").write_text("", encoding="utf-8")
    (root / "bad.json").write_text("{not-json", encoding="utf-8")
    return root


def test_corpus_presence_probe_reports_absent_on_cloud() -> None:
    """Contracted mount is typically missing in Cursor Cloud — measure, don't invent."""
    report = cn.corpus_presence_probe()
    assert report["success_invented"] is False
    assert report["corpus_fabricated"] is False
    assert "blocked_on_if_absent" in report
    assert "harness-restore-20260806" in report["blocked_on_if_absent"]
    # Soft assertion: if somehow mounted, corpus_present may be True; still no invent.
    assert isinstance(report["corpus_present"], bool)
    assert isinstance(report["candidates"], list)
    assert report["candidates"]


def test_resolve_corpus_root_raises_when_missing(tmp_path: Path) -> None:
    missing = tmp_path / "no-such-corpus"
    with pytest.raises(cn.CorpusAbsentError) as ei:
        cn.resolve_corpus_root(missing)
    assert str(missing.resolve()) in ei.value.looked


def test_normalize_refuses_absent_corpus(tmp_path: Path) -> None:
    missing = tmp_path / "absent"
    with pytest.raises(cn.CorpusAbsentError):
        cn.normalize_corpus(missing)


def test_normalize_conservation_planted_and_idempotence(tmp_path: Path) -> None:
    root = _mini_corpus(tmp_path)
    result = cn.normalize_corpus(root, inject_planted=True, use_rank=True)
    cons = result.conservation
    assert cons.ok(), cons.as_dict()
    assert cons.inputs == cons.emitted + cons.merged + cons.dropped
    assert cons.dropped >= 1  # empty + bad json at minimum
    assert cons.merged >= 1  # duplicate "Service timed out under load"
    assert result.planted_synthetic_present is True
    assert cn.PLANTED_SYNTHETIC_ID in result.record_ids
    assert any(d.reason for d in cons.dropped_enumerated)

    # Idempotence: unchanged corpus → same ids
    again = cn.normalize_corpus(root, inject_planted=True, use_rank=True)
    assert again.record_ids == result.record_ids

    idemp = cn.idempotence_check(root)
    assert idemp["idempotent"] is True


def test_planted_detector_absent_when_disabled(tmp_path: Path) -> None:
    root = _mini_corpus(tmp_path)
    result = cn.normalize_corpus(root, inject_planted=False, use_rank=False)
    assert result.planted_synthetic_present is False
    assert cn.PLANTED_SYNTHETIC_ID not in result.record_ids


def test_sample_anchors_resolve_fraction(tmp_path: Path) -> None:
    root = _mini_corpus(tmp_path)
    result = cn.normalize_corpus(root, inject_planted=True, use_rank=False)
    sample = cn.sample_anchors_resolve(result.records, sample_size=20, seed=19)
    assert sample["sample_size_actual"] <= 20
    assert 0.0 <= sample["resolve_fraction"] <= 1.0
    # Fixture files exist — expect a non-zero resolve rate.
    assert sample["resolved"] >= 1


def test_cli_probe_presence_exit_codes() -> None:
    # Exit 2 when absent is the honest Cloud path; exit 0 only if mounted.
    report = cn.corpus_presence_probe()
    rc = cn.main(["probe-presence"])
    assert rc in (0, 2)
    assert (rc == 0) == report["corpus_present"]
