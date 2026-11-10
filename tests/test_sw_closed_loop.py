"""Closed-loop decisions against measured fake geometry, without COM."""
from __future__ import annotations

import copy
import math
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sw_closed_loop import execute_plan, check_expectations  # noqa: E402
from sw_plan_bridge import PlanValidationError  # noqa: E402


def operation_plan():
    return {"schema_version": 1, "name": "feedback_test", "operations": [
        {"id": "outline", "op": "sketch_rectangle", "params": {
            "plane": "Front Plane", "cx_mm": 0, "cy_mm": 0, "width_mm": 100, "height_mm": 60}},
        {"id": "stock", "op": "extrude_boss", "params": {"sketch_id": "outline", "depth_mm": 8},
         "expect": {"body_count": 1, "volume_mm3": 48000, "bbox_size_mm": [100, 60, 8]}},
        {"id": "hole_profile", "op": "sketch_circles", "params": {
            "plane": "Front Plane", "circles": [{"x_mm": 0, "y_mm": 0, "radius_mm": 3}]}},
        {"id": "hole", "op": "extrude_cut", "params": {
            "sketch_id": "hole_profile", "depth_mm": {"from_context": "geometry.bbox_size_mm.2", "offset_mm": 2},
            "through_all": True}, "fallback_params": [{"reverse": True}], "expect": {"body_count": 1}},
    ], "requirements": [{"body_count": 1, "volume_mm3": 48000 - math.pi * 9 * 8,
                           "volume_tolerance_mm3": 0.01}]}


class MeasuredBackend:
    def __init__(self, cut_failure=None):
        self.context = {"features": [], "features_complete": True,
                        "geometry": {"body_count": 0, "volume_mm3": 0, "bbox_mm": None, "bbox_size_mm": None}}
        self.actions = []
        self.profiles = {}
        self.cut_failure = cut_failure
        self.cut_attempts = {}
        self.rebuild_result = True

    def snapshot(self):
        return copy.deepcopy(self.context)

    def rebuild(self):
        return self.rebuild_result

    def execute(self, action):
        self.actions.append(copy.deepcopy(action))
        operation, params = action["op"], action["params"]
        geometry = self.context["geometry"]
        if operation.startswith("sketch_"):
            self.profiles[action["id"]] = params
        elif operation == "extrude_boss":
            profile = self.profiles[params["sketch_id"]]
            w, h, d = profile["width_mm"], profile["height_mm"], params["depth_mm"]
            geometry.update(body_count=1, volume_mm3=w * h * d,
                            bbox_size_mm=[w, h, d], bbox_mm=[-w / 2, -h / 2, 0, w / 2, h / 2, d])
        elif operation == "extrude_cut":
            count = self.cut_attempts.get(action["id"], 0) + 1
            self.cut_attempts[action["id"]] = count
            fail = count == 1 and self.cut_failure
            if fail == "unchanged":
                return {"created": False}
            if fail == "feature_mutated":
                self.context["features"].append({"name": "failed_cut", "type": "Cut", "error_code": 1})
                return {"created": False}
            if fail == "geometry_mutated":
                geometry["volume_mm3"] -= 5
                return {"created": False}
            if fail == "exception_mutated":
                geometry["volume_mm3"] -= 5
                raise RuntimeError("operation partially mutated then raised")
            if fail == "unknown":
                geometry["volume_mm3"] = None
                return {"created": False}
            if fail == "incomplete_features":
                self.context["features_complete"] = False
                return {"created": False}
            radius = self.profiles[params["sketch_id"]]["circles"][0]["radius_mm"]
            geometry["volume_mm3"] -= math.pi * radius**2 * geometry["bbox_size_mm"][2]
        self.context["features"].append({"name": action["id"], "type": operation, "error_code": 0})
        return {"created": True, "feature_name": action["id"]}


def test_context_binding_uses_preceding_actual_measurement_and_reports_evidence():
    backend = MeasuredBackend()
    plan = operation_plan()
    source = {"geometry": {"bbox_size_mm": [50, 60, 90]}}
    plan["operations"][0]["params"]["width_mm"] = {"from_source": "geometry.bbox_size_mm.0", "scale": 2}
    events = []
    result = execute_plan(plan, backend, source_context=source, event_sink=events.append)
    assert result["status"] == "passed"
    assert backend.actions[0]["params"]["width_mm"] == 100
    assert backend.actions[-1]["params"]["depth_mm"] == 10  # measured 8, not source thickness 90
    assert len(events) == 4
    assert result["steps"][-1]["before"]["geometry"]["bbox_size_mm"][2] == 8
    assert result["engineering_review_required"] is True


def test_failed_nonmutating_cut_gets_exactly_one_declared_reverse_attempt():
    backend = MeasuredBackend("unchanged")
    result = execute_plan(operation_plan(), backend)
    assert result["status"] == "passed"
    cut_actions = [a for a in backend.actions if a["op"] == "extrude_cut"]
    assert [a["params"]["reverse"] for a in cut_actions] == [False, True]
    assert cut_actions[0]["params"]["depth_mm"] == cut_actions[1]["params"]["depth_mm"]
    assert result["feedback"][0]["code"] == "retry_declared_direction"


@pytest.mark.parametrize("failure", ["feature_mutated", "geometry_mutated", "exception_mutated", "unknown", "incomplete_features"])
def test_mutation_or_unknown_state_forbids_retry(failure):
    backend = MeasuredBackend(failure)
    result = execute_plan(operation_plan(), backend)
    assert result["status"] == "needs_revision"
    assert backend.cut_attempts["hole"] == 1
    assert not any(f["code"] == "retry_declared_direction" for f in result["feedback"])


def test_failed_measurement_stops_later_operations():
    plan = operation_plan()
    plan["operations"][1]["expect"]["body_count"] = 2
    backend = MeasuredBackend()
    result = execute_plan(plan, backend)
    assert result["status"] == "needs_revision"
    assert [a["id"] for a in backend.actions] == ["outline", "stock"]
    assert result["steps"][-1]["attempts"][0]["checks"][2]["passed"] is False


def test_unknown_measurement_does_not_pass_expectation():
    context = {"features": [], "features_complete": False,
               "geometry": {"body_count": None, "volume_mm3": None, "bbox_size_mm": None}}
    checks = check_expectations(context, {"body_count": 1, "volume_mm3": 1,
                                          "bbox_size_mm": [1, 1, 1], "feature_ok": True})
    assert len(checks) == 4
    assert all(c["passed"] is False for c in checks)


def test_unknown_feature_error_is_not_hidden_by_another_known_feature():
    context = {"features_complete": True, "features": [
        {"name": "known", "error_code": 0}, {"name": "unknown", "error_code": None}], "geometry": {}}
    assert check_expectations(context, {"feature_ok": True})[0]["passed"] is False


def test_hole_checks_forward_measured_geometry_and_explicit_mm_tolerance(monkeypatch):
    received = {}
    def validate(measurements, holes, **tolerances):
        received.update(measurements=measurements, holes=holes, tolerances=tolerances)
        return {"status": "pass"}
    monkeypatch.setitem(sys.modules, "sw_review", SimpleNamespace(validate_hole_positions=validate))
    measurement = {"cylindrical_faces": [{"radius_mm": 3}]}
    holes = [{"diameter_mm": 6, "position_mm": [0, 0, 0]}]
    context = {"geometry": {"hole_measurements": measurement}}
    checks = check_expectations(context, {"holes": holes, "hole_tolerance_mm": 0.02})
    assert checks[0]["passed"] is True
    assert received["measurements"] is measurement
    assert received["holes"] == holes
    assert received["tolerances"] == {"position_tolerance_mm": 0.02, "diameter_tolerance_mm": 0.02}


def test_unsupported_plan_rejected_before_backend_snapshot_or_execute():
    class UntouchedBackend:
        def snapshot(self):
            pytest.fail("must reject before touching backend")
    plan = operation_plan()
    plan["operations"][1]["op"] = "arbitrary_macro"
    with pytest.raises(PlanValidationError):
        execute_plan(plan, UntouchedBackend())


def test_missing_reference_geometry_stops_without_drawing_default_shape():
    plan = operation_plan()
    plan["operations"][0]["params"]["width_mm"] = {"from_source": "geometry.bbox_size_mm.0"}
    backend = MeasuredBackend()
    report = execute_plan(plan, backend)
    assert report["status"] == "needs_revision"
    assert backend.actions == []
    assert report["feedback"][0]["code"] == "invalid_context_binding"


def test_rebuild_failure_stops_even_when_feature_creation_reports_success():
    backend = MeasuredBackend()
    backend.rebuild_result = False
    report = execute_plan(operation_plan(), backend)
    assert report["status"] == "needs_revision"
    assert len(backend.actions) == 1


def test_expectation_and_final_requirement_bindings_are_resolved():
    plan = operation_plan()
    plan["operations"][1]["expect"]["volume_mm3"] = {"from_source": "geometry.volume_mm3"}
    plan["requirements"] = [{"body_count": {"from_source": "geometry.body_count"}}]
    source = {"geometry": {"volume_mm3": 48000, "body_count": 1}}
    report = execute_plan(plan, MeasuredBackend(), source_context=source)
    assert report["status"] == "passed"
    assert report["final_checks"][0]["expected"] == 1


def test_reverse_retry_budget_is_global_not_reset_for_each_cut():
    plan = operation_plan()
    second_profile = copy.deepcopy(plan["operations"][2])
    second_profile["id"] = "second_profile"
    second_profile["params"]["circles"][0]["x_mm"] = 20
    second_cut = copy.deepcopy(plan["operations"][3])
    second_cut["id"] = "second_cut"
    second_cut["params"]["sketch_id"] = "second_profile"
    plan["operations"].extend([second_profile, second_cut])
    plan["requirements"] = []
    backend = MeasuredBackend("unchanged")
    report = execute_plan(plan, backend)
    assert backend.cut_attempts["hole"] == 2
    assert backend.cut_attempts["second_cut"] == 1
    assert report["status"] == "needs_revision"
