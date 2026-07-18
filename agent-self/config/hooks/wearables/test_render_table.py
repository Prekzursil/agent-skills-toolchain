"""Tests for the /biopull rendering LOGIC (WU-1E) — VERBATIM table contract.

PURE function (NOT the live skill wiring). 8 columns, exact order:
  Source | Target/Assay context | Metric | Value(normalized) | Value(as-reported) | n | Confidence | Ref
Default sort = Target then ascending normalized affinity. Inline ! disagreement
flag with footnoted spread. Footer VERBATIM:
  sources hit: <list> | accessed YYYY-MM-DD | n rows, m flagged
--raw escape -> full JSON.
"""

import json


from wearables.datum import Provenance, make_datum
from wearables.render_table import HEADER, render_raw, render_table


def _prov(db="ChEMBL", pmid="PMID:1", acc="CHEMBL701"):
    return Provenance(pmid=pmid, db=db, accession=acc, access_date="2026-06-16")


def _datum(**over):
    base = dict(
        compound_id="KPYSYYIEGFHWSV-UHFFFAOYSA-N",
        target_id="O75899",
        target_context="GABAB1/2-heterodimer",
        metric="Ki",
        value=12.0,
        value_as_reported=12000.0,
        unit="nM",
        unit_as_reported="pM",
        n=3,
        confidence="high",
        source="ChEMBL",
        source_class="public_db",
        provenance=_prov(),
    )
    base.update(over)
    return make_datum(**base)


def test_header_is_verbatim_8_columns():
    assert HEADER == [
        "Source",
        "Target/Assay context",
        "Metric",
        "Value(normalized)",
        "Value(as-reported)",
        "n",
        "Confidence",
        "Ref",
    ]


def test_table_has_header_separator_and_footer():
    out = render_table([_datum()], accessed="2026-06-16")
    lines = out.splitlines()
    # header, separator, one data row, blank, footer
    assert lines[0].startswith("| Source |")
    assert set(lines[1].replace("|", "").replace(" ", "")) <= {"-"}
    assert lines[2].startswith("| ChEMBL |")
    assert lines[-1].startswith("sources hit:")


def test_row_columns_in_exact_order():
    out = render_table([_datum()], accessed="2026-06-16")
    row = [c.strip() for c in out.splitlines()[2].strip("|").split("|")]
    assert row[0] == "ChEMBL"
    assert row[1] == "GABAB1/2-heterodimer"
    assert row[2] == "Ki"
    assert row[3] == "12.0 nM"
    assert row[4] == "12000.0 pM"
    assert row[5] == "3"
    assert row[6] == "high"
    assert row[7] == "PMID:1"


def test_footer_verbatim_format():
    data = [
        _datum(source="ChEMBL"),
        _datum(
            source="PubChem",
            value=15.0,
            provenance=_prov(db="PubChem", pmid=None, acc="2284"),
        ),
    ]
    out = render_table(data, accessed="2026-06-16")
    footer = out.splitlines()[-1]
    assert (
        footer
        == "sources hit: ChEMBL, PubChem | accessed 2026-06-16 | 2 rows, 0 flagged"
    )


def test_default_sort_target_then_ascending_affinity():
    rows = [
        _datum(target_context="GABAB1-subunit-alone", value=50.0),
        _datum(target_context="GABAB1/2-heterodimer", value=80.0),
        _datum(target_context="GABAB1/2-heterodimer", value=10.0),
    ]
    out = render_table(rows, accessed="2026-06-16")
    body = out.splitlines()[2:5]
    contexts = [r.strip("|").split("|")[1].strip() for r in body]
    norms = [r.strip("|").split("|")[3].strip() for r in body]
    # Target is the primary key (alphabetical: '-' (0x2D) sorts before '/'
    # (0x2F), so subunit-alone precedes heterodimer); within a group,
    # ascending normalized affinity.
    assert contexts == [
        "GABAB1-subunit-alone",
        "GABAB1/2-heterodimer",
        "GABAB1/2-heterodimer",
    ]
    assert norms[1] == "10.0 nM"
    assert norms[2] == "80.0 nM"


def test_inline_disagreement_flag_and_footnote():
    flagged = _datum(flags=("disagreement:Ki spread 3.2x",))
    out = render_table([flagged], accessed="2026-06-16")
    lines = out.splitlines()
    # the ! marker appears inline on the flagged metric cell
    assert "Ki !" in lines[2]
    # a footnote with the quantified spread is present
    assert any("spread 3.2x" in ln for ln in lines)
    # footer counts the flagged row
    assert "1 rows, 1 flagged" in lines[-1]


def test_non_disagreement_flag_is_not_treated_as_disagreement():
    # A flag that is NOT a disagreement marker must not flip the metric cell
    # (exercises the loop's non-matching continue branch).
    out = render_table([_datum(flags=("unresolved:cross-id",))], accessed="2026-06-16")
    lines = out.splitlines()
    assert "Ki !" not in lines[2]
    assert "0 flagged" in lines[-1]


def test_none_value_and_none_n_render_as_dash():
    out = render_table([_datum(value=None, n=None)], accessed="2026-06-16")
    row = [c.strip() for c in out.splitlines()[2].strip("|").split("|")]
    assert row[3] == "-"
    assert row[5] == "-"


def test_ref_falls_back_to_db_accession_when_no_pmid():
    out = render_table(
        [_datum(provenance=_prov(db="GtoPdb", pmid=None, acc="1084"))],
        accessed="2026-06-16",
    )
    row = [c.strip() for c in out.splitlines()[2].strip("|").split("|")]
    assert row[7] == "GtoPdb:1084"


def test_empty_data_renders_header_and_zero_footer():
    out = render_table([], accessed="2026-06-16")
    lines = out.splitlines()
    assert lines[0].startswith("| Source |")
    assert lines[-1] == "sources hit:  | accessed 2026-06-16 | 0 rows, 0 flagged"


def test_raw_escape_returns_full_json():
    data = [_datum()]
    out = render_raw(data)
    parsed = json.loads(out)
    assert isinstance(parsed, list)
    assert parsed[0]["source"] == "ChEMBL"
    assert parsed[0]["value"] == 12.0
    assert parsed[0]["value_as_reported"] == 12000.0
    assert parsed[0]["provenance"]["db"] == "ChEMBL"
    assert parsed[0]["flags"] == []
