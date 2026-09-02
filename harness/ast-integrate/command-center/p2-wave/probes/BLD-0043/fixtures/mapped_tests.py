"""Fixture tests with STRUCTURAL requirement mappings for BLD-0043 controls.

Channels used here:
  * test-id  — REQ id encoded in the function name (REQ-FX-01 .. REQ-FX-06, DEL)
  * marker   — pytest.mark.req / REQ_IDS assignment (REQ-FX-07, REQ-FX-08)
  * registry — fixtures/registry.json (REQ-FX-09, REQ-FX-10)
"""
from __future__ import annotations

import pytest

WORK_UNIT_FLOOR = 2048
WORKFLOW_CANDIDATE_FLOOR = 160
BLUEPRINT_FLOOR = 96
FLAGSHIP_FLOOR = 40
PROTOCOL_FLOOR = 48
PRESET_FLOOR = 64
IDEA_FLOOR = 100
TEST_LAYER_FLOOR = 36
STOPPING_FLOOR = 21
BOUND_UNIT_ID = "CC-0024"
CATALOG_IDS = {"CC-0024", "BLD-0043", "B08"}


def test_REQ_FX_01_work_unit_floor_is_2048():
    assert WORK_UNIT_FLOOR == 2048
    assert "work unit" in "2048 work units"


def test_REQ_FX_02_workflow_candidate_floor_is_160():
    assert WORKFLOW_CANDIDATE_FLOOR == 160
    assert "workflow" in "160 workflow candidates"


def test_REQ_FX_03_blueprint_floor_is_96():
    assert BLUEPRINT_FLOOR == 96
    assert "blueprint" in "96 blueprints"


def test_REQ_FX_04_flagship_floor_is_40():
    assert FLAGSHIP_FLOOR == 40
    assert "flagship" in "40 flagship workflows"


def test_REQ_FX_05_protocol_floor_is_48():
    assert PROTOCOL_FLOOR == 48
    assert "protocol" in "48 council protocols"


def test_REQ_FX_06_preset_floor_is_64():
    assert PRESET_FLOOR == 64
    assert "preset" in "64 editable presets"


@pytest.mark.req("REQ-FX-07")
def test_marker_idea_brainstorm_floor_is_100():
    assert IDEA_FLOOR == 100
    assert "idea" in "100-unique-idea brainstorm target"


def test_marker_test_layer_floor_is_36():
    REQ_IDS = ("REQ-FX-08",)
    assert TEST_LAYER_FLOOR == 36
    assert "test layer" in "36 test layers"
    assert REQ_IDS == ("REQ-FX-08",)


def test_registry_mapped_stopping_conditions():
    assert STOPPING_FLOOR == 21
    assert "stopping" in "21 stopping conditions"


def test_registry_mapped_bound_unit_in_catalog():
    assert BOUND_UNIT_ID in CATALOG_IDS
    assert "bound" in "every bound unit id must exist in the merged catalog"
    assert "catalog" in "merged catalog"


def test_REQ_FX_DEL_sole_mapping_delete_moves_untested():
    assert "delete" in "deleting the sole mapped test must untest this requirement"
    assert "untest" in "must untest this requirement"
