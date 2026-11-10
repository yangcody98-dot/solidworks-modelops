"""Preflight boundaries for real-model CAD plans; no SolidWorks dependency."""
from __future__ import annotations

import copy
import importlib.util
import math
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sw_plan_bridge import (  # noqa: E402
    PlanValidationError, compile_design_plan, resolve_context_bindings,
    validate_operation_plan,
)


def plate_plan():
    return {
        "schema_version": 1,
        "name": "isolated_test_plate",
        "operations": [
            {"id": "outline", "op": "sketch_rectangle", "params": {
                "plane": "Front Plane", "cx_mm": 0, "cy_mm": 0,
                "width_mm": 100, "height_mm": 60}},
            {"id": "stock", "op": "extrude_boss", "params": {
                "sketch_id": "outline", "depth_mm": 8},
             "expect": {"body_count": 1, "bbox_size_mm": [100, 60, 8],
                        "volume_mm3": 48000, "feature_ok": True}},
            {"id": "hole_sketch", "op": "sketch_circles", "params": {
                "plane": "Front Plane", "circles": [
                    {"x_mm": -40, "y_mm": -20, "radius_mm": 3},
                    {"x_mm": 40, "y_mm": 20, "radius_mm": 3}]}},
            {"id": "holes", "op": "extrude_cut", "params": {
                "sketch_id": "hole_sketch", "depth_mm": 8,
                "through_all": True}, "fallback_params": [{"reverse": True}],
             "expect": {"body_count": 1, "holes": [
                 {"diameter_mm": 6, "position_mm": [-40, -20, 0]},
                 {"diameter_mm": 6, "position_mm": [40, 20, 0]}]}},
        ],
        "requirements": [{"body_count": 1,
                          "volume_mm3": 48000 - 2 * math.pi * 3**2 * 8,
                          "volume_tolerance_mm3": 0.1}],
    }


def legacy_plate():
    return {
        "plan_version": 1, "part_family": "plate", "source_brief": "explicit plate",
        "parameters": {"unit": "mm"}, "assumptions": [],
        "features": [
            {"name": "Plate", "type": "base_plate", "required": True,
             "params": {"length": 100, "width": 60, "thickness": 8}},
            {"name": "Holes", "type": "through_hole_pattern", "required": True,
             "params": {"clearance_diameter": 6, "positions_xy": [[-40, -20], [40, 20]]}},
        ],
        "operation_sequence": ["new_part", "base_plate", "through_holes", "save_export_review"],
        "review_plan": {"checks": ["previews_created"]},
    }


def test_validation_copies_data_and_preserves_measurable_requirements():
    original = plate_plan()
    before = copy.deepcopy(original)
    normalized = validate_operation_plan(original)
    assert original == before
    assert normalized is not original
    assert normalized["operations"][-1]["params"]["reverse"] is False
    assert normalized["requirements"][0]["volume_mm3"] < 48000
    normalized["operations"][0]["params"]["width_mm"] = 25
    assert original["operations"][0]["params"]["width_mm"] == 100


@pytest.mark.parametrize("value", [0, -1, True, "8", None, float("nan"), float("inf"), 10**1000])
def test_invalid_dimensions_block_before_cad(value):
    plan = plate_plan()
    plan["operations"][1]["params"]["depth_mm"] = value
    with pytest.raises(PlanValidationError):
        validate_operation_plan(plan)


@pytest.mark.parametrize("mutation,code", [
    (lambda p: p["operations"][2].update(id="outline"), "duplicate_id"),
    (lambda p: p["operations"][1]["params"].update(sketch_id="hole_sketch"), "invalid_reference"),
    (lambda p: p["operations"][3]["params"].update(sketch_id="stock"), "invalid_reference"),
    (lambda p: p["operations"][1].update(op="run_python"), "unsupported_operation"),
    (lambda p: p["operations"][0]["params"].update(execute="save original"), "unsupported_field"),
    (lambda p: p["operations"][3]["params"].update(through_all=1), "invalid_boolean"),
    (lambda p: p.update(schema_version=True), "unsupported_version"),
    (lambda p: p["operations"][0].update(id="../original"), "invalid_id"),
])
def test_invalid_operations_and_references_have_actionable_errors(mutation, code):
    plan = plate_plan()
    mutation(plan)
    with pytest.raises(PlanValidationError) as exc:
        validate_operation_plan(plan)
    assert exc.value.issues[0]["code"] == code
    assert exc.value.issues[0]["path"].startswith("plan.")


def test_cut_requires_a_solid_in_the_new_document():
    plan = plate_plan()
    plan["operations"] = plan["operations"][2:]
    with pytest.raises(PlanValidationError, match="earlier boss"):
        validate_operation_plan(plan)


def test_prefix_validation_permits_initial_sketch_but_keeps_other_checks():
    plan = plate_plan()
    plan["operations"] = plan["operations"][:1]
    plan["requirements"] = []
    with pytest.raises(PlanValidationError, match="at least one boss"):
        validate_operation_plan(plan)
    assert validate_operation_plan(plan, allow_prefix=True)["operations"][0]["id"] == "outline"
    plan["operations"][0]["params"]["width_mm"] = 0
    with pytest.raises(PlanValidationError, match="positive"):
        validate_operation_plan(plan, allow_prefix=True)


@pytest.mark.parametrize("expect", [
    {"bbox_size_mm": [100, 60]}, {"body_count": 1.5},
    {"volume_tolerance_mm3": 0.1}, {"feature_ok": False},
    {"holes": [{"diameter_mm": 6, "position_mm": [0, 0]}]},
    {"holes": []}, {"mass_kg": 2},
])
def test_bad_expectations_are_not_ignored(expect):
    plan = plate_plan()
    plan["requirements"] = [expect]
    with pytest.raises(PlanValidationError):
        validate_operation_plan(plan)


def test_fallback_cannot_change_hole_sizes_or_cut_depth():
    plan = plate_plan()
    plan["operations"][-1]["fallback_params"] = [{"reverse": True, "depth_mm": 4}]
    with pytest.raises(PlanValidationError, match="unsupported fields"):
        validate_operation_plan(plan)
    plan["operations"][-1]["fallback_params"] = [{"reverse": False}]
    with pytest.raises(PlanValidationError, match="opposite"):
        validate_operation_plan(plan)
    plan["operations"][-1]["fallback_params"] = [{"reverse": True}, {"reverse": False}]
    with pytest.raises(PlanValidationError, match="only one"):
        validate_operation_plan(plan)


def test_binding_distinguishes_live_context_from_reference_source():
    plan = plate_plan()
    plan["operations"][0]["params"]["width_mm"] = {
        "from_source": "geometry.bbox_size_mm.0", "scale": 1.2, "offset_mm": 10}
    plan["operations"][-1]["params"]["depth_mm"] = {
        "from_context": "geometry.bbox_size_mm.2", "offset_mm": 1}
    normalized = validate_operation_plan(plan)
    live = {"geometry": {"bbox_size_mm": [100, 60, 8]}}
    reference = {"geometry": {"bbox_size_mm": [50, 30, 5]}}
    resolved = resolve_context_bindings(normalized, live, reference)
    checked = validate_operation_plan(resolved, allow_bindings=False)
    assert checked["operations"][0]["params"]["width_mm"] == 70
    assert checked["operations"][-1]["params"]["depth_mm"] == 9
    assert isinstance(plan["operations"][0]["params"]["width_mm"], dict)


@pytest.mark.parametrize("binding", [
    {"from_context": "document.path"},
    {"from_context": "geometry.__class__"},
    {"from_context": ["geometry", "bbox_size_mm", 0]},
    {"from_context": "geometry.bbox_size_mm.0", "from_source": "geometry.bbox_size_mm.0"},
    {"from_context": "geometry.bbox_size_mm.0", "scale": float("nan")},
    {"from_context": "geometry.bbox_size_mm.0", "fallback": 90},
])
def test_bindings_are_restricted_data_paths(binding):
    plan = plate_plan()
    plan["operations"][0]["params"]["width_mm"] = binding
    with pytest.raises(PlanValidationError):
        validate_operation_plan(plan)


def test_missing_evidence_never_becomes_a_template_default():
    binding = {"from_source": "geometry.bbox_size_mm.0"}
    with pytest.raises(PlanValidationError, match="no measured value"):
        resolve_context_bindings(binding, {"geometry": {"bbox_size_mm": [90, 60, 8]}})
    with pytest.raises(PlanValidationError):
        resolve_context_bindings(binding, {}, {"geometry": {"bbox_size_mm": [None, 60, 8]}})


def test_resolved_dimensions_are_revalidated_before_execution():
    plan = plate_plan()
    plan["operations"][0]["params"]["width_mm"] = {
        "from_source": "geometry.bbox_size_mm.0", "scale": -1}
    normalized = validate_operation_plan(plan)
    with pytest.raises(PlanValidationError, match="unresolved"):
        validate_operation_plan(normalized, allow_bindings=False)
    resolved = resolve_context_bindings(normalized, {}, {"geometry": {"bbox_size_mm": [50, 30, 5]}})
    with pytest.raises(PlanValidationError, match="positive"):
        validate_operation_plan(resolved, allow_bindings=False)


def test_legacy_plate_compiles_to_executable_geometry_and_retains_reference_data():
    source = legacy_plate()
    before = copy.deepcopy(source)
    compiled = compile_design_plan(source)
    assert source == before
    assert [op["op"] for op in compiled["operations"]] == [
        "sketch_rectangle", "extrude_boss", "sketch_circles", "extrude_cut"]
    assert compiled["operations"][1]["expect"]["volume_mm3"] == 48000
    assert compiled["operations"][-1]["expect"]["holes"][1]["position_mm"] == [40, 20, 0]
    assert compiled["metadata"]["legacy_review_plan"] == source["review_plan"]


def test_default_legacy_planner_is_blocked_without_dropping_required_or_optional_features():
    path = ROOT / "subskills/solidworks-vibecad/scripts/plan_from_brief.py"
    spec = importlib.util.spec_from_file_location("legacy_vibecad_planner_for_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plan = module.build_plan("安装座 100x60x8mm")
    before = copy.deepcopy(plan)
    with pytest.raises(PlanValidationError) as exc:
        compile_design_plan(plan)
    assert plan == before
    failures = str(exc.value)
    assert "fillet" in failures and "chamfer" in failures and "pocket_pair" in failures
    assert "close_same_name_documents" in failures


@pytest.mark.parametrize("positions", [[[49, 0]], [[0, 0], [0, 0]], [[0, 0], [5, 0]]])
def test_legacy_holes_outside_stock_or_overlapping_are_rejected(positions):
    plan = legacy_plate()
    plan["features"][1]["params"]["positions_xy"] = positions
    with pytest.raises(PlanValidationError):
        compile_design_plan(plan)


def test_normalized_plan_is_idempotent():
    normalized = validate_operation_plan(plate_plan())
    assert validate_operation_plan(normalized) == normalized
    assert compile_design_plan(normalized) == normalized


def test_metadata_must_be_finite_json_data():
    plan = plate_plan()
    plan["metadata"] = {"value": float("nan")}
    with pytest.raises(PlanValidationError):
        validate_operation_plan(plan)
