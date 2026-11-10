"""Native Rib contracts with fake COM only; no CAD attachment or model I/O."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sw_native_ribs as ribs  # noqa: E402


class Definition:
    def __init__(self):
        self.Thickness = .008
        self.IsTwoSided = True
        self.ReverseThicknessDir = False
        self.ExtrusionDirection = 0
        self.Type = 0
        self.FlipSide = False
        self.EnableDraft = False
        self.DraftOutward = False
        self.DraftAngle = 0.0
        self.DraftFromWall = False

    def AccessSelections(self, *_args):
        pytest.fail("Readback must not roll back or edit the feature")


class Line:
    ConstructionGeometry = False

    def GetType(self):
        return 0  # swSketchLINE

    def GetStartPoint2(self):
        return SimpleNamespace(X=-.062, Y=-.028, Z=0.0)

    def GetEndPoint2(self):
        return SimpleNamespace(X=-.012, Y=.012, Z=0.0)


class Sketch:
    def __init__(self):
        self.Name = "RibSketch"
        self.Is3D = False
        self.status = 3
        self.segments = [Line()]

    def GetConstrainedStatus(self):
        return self.status

    def GetSketchSegments(self):
        return self.segments


class Feature:
    def __init__(self, model, name, kind, definition=None, sketch=None):
        self.model, self.Name, self.kind = model, name, kind
        self.definition, self.sketch = definition, sketch

    def GetTypeName2(self):
        return self.kind

    def GetDefinition(self):
        return self.definition

    def GetSpecificFeature2(self):
        return self.sketch

    def Select2(self, append, mark):
        self.model.selections.append((self.Name, append, mark))
        return True

    def GetNextFeature(self):
        index = self.model.features.index(self) + 1
        return self.model.features[index] if index < len(self.model.features) else None

    def GetFirstSubFeature(self):
        return None


class Model:
    def __init__(self):
        self.definition = Definition()
        self.sketch = Sketch()
        self.doc_type = 1
        self.features = [Feature(self, "Base", "Extrusion"),
                         Feature(self, "RibSketch", "ProfileFeature", sketch=self.sketch)]
        self.created = Feature(self, "Rib1", "Rib", self.definition)
        self.SketchManager = SimpleNamespace(ActiveSketch=None)
        self.FeatureManager = SimpleNamespace(InsertRib=self.insert_rib)
        self.calls, self.rebuilds, self.selections, self.clears = [], [], [], []
        self.created_count = 1
        self.volume = 230400.0
        self.added_volume = 8000.0
        self.body_count = 1
        self.features_complete = True
        self.feature_error = 0
        self.rebuild_result = True
        self.audit_ok = True
        self.audit_after_ok = True
        self.input_absorbed = True

    def GetType(self):
        return self.doc_type

    def FeatureByName(self, name):
        return next((f for f in self.features if f.Name == str(name)), None)

    def FirstFeature(self):
        return self.features[0]

    def ClearSelection2(self, all_marks):
        self.clears.append(all_marks)

    def ForceRebuild3(self, top_only):
        self.rebuilds.append(top_only)
        return self.rebuild_result

    def insert_rib(self, *args):
        self.calls.append(args)
        if self.created_count:
            self.features.append(self.created)
            self.volume += self.added_volume
        if self.created_count > 1:
            self.features.append(Feature(self, "Rib2", "Rib", self.definition))
        return None  # InsertRib is void even when it succeeds.

    def context(self, **_kwargs):
        return {
            "document": {"type": self.doc_type, "id": "new-owned-part"},
            "features": [{"name": f.Name, "type": f.kind, "error_code": self.feature_error}
                         for f in self.features],
            "features_complete": self.features_complete,
            "geometry": {"status": "available", "body_count": self.body_count,
                         "volume_mm3": self.volume, "bbox_mm": [-60., -40., 0., 60., 40., 92.],
                         "bbox_size_mm": [120., 80., 92.]},
            "warnings": [],
        }

    def audit(self):
        valid = self.audit_ok and (not self.calls or self.audit_after_ok)
        owner = ({"name": self.created.Name, "type": "Rib"}
                 if self.calls and self.input_absorbed else {})
        return {"all_fully_defined": valid, "all_parametric": valid,
                "complete": True, "sketch_count": 1, "status": "pass" if valid else "fail",
                "sketches": [{"name": "RibSketch", "fully_defined": valid,
                              "parametric_evidence": valid, "constraint_status": 3 if valid else 2,
                              "segment_count": len(self.sketch.segments),
                              "owner_feature": owner}], "warnings": []}


@pytest.fixture
def model(monkeypatch):
    instance = Model()
    monkeypatch.setattr(ribs, "capture_model_context", lambda m, **kw: m.context(**kw))
    monkeypatch.setattr(ribs, "collect_sketch_constraint_status", lambda m: m.audit())
    # Reuse the existing selection boundary without loading or attaching to CAD.
    part = importlib.import_module("sw_part")
    monkeypatch.setattr(part, "_ensure_sketch_selected",
                        lambda m, name: m.FeatureByName(str(name)).Select2(False, 0))
    return instance


def create(model, **options):
    arguments = {"model": model, "sketch_name": "RibSketch", "thickness_mm": 8,
                 "name": "Central_Rib_T8", "expected_added_volume_mm3": 8000}
    arguments.update(options)
    return ribs.create_native_rib(**arguments)


def test_successful_void_insert_returns_the_actual_new_rib(model):
    result = create(model)
    assert result["feature"] is model.created
    assert model.created.Name == "Central_Rib_T8"
    assert len(model.calls) == 1
    assert model.calls[0] == (True, False, .008, 0, False, False, False, 0, False, False)
    assert result["readback"]["feature_type"] == "Rib"
    assert result["readback"]["thickness_mm"] == pytest.approx(8)
    assert result["after"]["geometry"]["volume_mm3"] - result["before"]["geometry"]["volume_mm3"] == pytest.approx(8000)
    assert result["sketch_constraints"]["all_fully_defined"]
    assert result["sketch_constraints"]["all_parametric"]


def test_low_level_keeps_legacy_single_sided_api_argument(model):
    model.definition.IsTwoSided = False
    result = ribs.insert_native_rib(model, "RibSketch", .008, is_two_sided=False)
    assert result is model.created
    assert model.calls == [(False, False, .008, 0, False, False, False, 0, False, False)]


@pytest.mark.parametrize("field,value", [
    ("Thickness", .007), ("IsTwoSided", False), ("ExtrusionDirection", 1),
    ("EnableDraft", True), ("DraftAngle", .1), ("FlipSide", True),
])
def test_readback_mismatches_fail_without_retry_or_replacement(model, field, value):
    setattr(model.definition, field, value)
    with pytest.raises((ValueError, RuntimeError)):
        create(model)
    assert len(model.calls) == 1
    assert model.created in model.features


@pytest.mark.parametrize("count", [0, 2])
def test_void_call_requires_exactly_one_new_rib(model, count):
    model.created_count = count
    with pytest.raises(RuntimeError):
        create(model)
    assert len(model.calls) == 1


@pytest.mark.parametrize("options", [
    {"thickness_mm": 0}, {"thickness_mm": -1}, {"thickness_mm": float("nan")},
    {"thickness_mm": float("inf")}, {"thickness_mm": True}, {"name": ""},
    {"expected_added_volume_mm3": -1}, {"expected_added_volume_mm3": float("nan")},
    {"volume_tolerance_mm3": -1}, {"volume_tolerance_mm3": float("inf")},
])
def test_invalid_inputs_do_not_select_rebuild_or_create(model, options):
    with pytest.raises((ValueError, TypeError)):
        create(model, **options)
    assert model.calls == model.rebuilds == model.selections == model.clears == []


@pytest.mark.parametrize("state", ["assembly", "active_sketch", "3d", "underdefined",
                                    "two_lines", "body_count", "audit", "duplicate_name"])
def test_invalid_initial_state_is_rejected_before_mutation(model, state):
    if state == "assembly": model.doc_type = 2
    elif state == "active_sketch": model.SketchManager.ActiveSketch = model.sketch
    elif state == "3d": model.sketch.Is3D = True
    elif state == "underdefined": model.sketch.status = 2
    elif state == "two_lines": model.sketch.segments.append(Line())
    elif state == "body_count": model.body_count = 2
    elif state == "audit": model.audit_ok = False
    elif state == "duplicate_name": model.features.append(Feature(model, "Central_Rib_T8", "Rib", model.definition))
    with pytest.raises((ValueError, RuntimeError)):
        create(model)
    assert model.calls == model.rebuilds == model.selections == model.clears == []


@pytest.mark.parametrize("volume", [0, -100, 7500])
def test_wrong_added_volume_is_not_accepted_as_success(model, volume):
    model.added_volume = volume
    with pytest.raises(RuntimeError):
        create(model)
    assert len(model.calls) == 1


def test_newly_underdefined_sketch_fails_postcheck(model):
    model.audit_after_ok = False
    with pytest.raises(RuntimeError):
        create(model)
    assert len(model.calls) == 1


def test_other_sketch_cannot_satisfy_requested_input_absorption(model):
    model.input_absorbed = False
    with pytest.raises(RuntimeError, match="absorb"):
        create(model)
    assert len(model.calls) == 1


def test_readback_is_read_only_and_does_not_use_access_selections():
    definition = Definition()
    feature = Feature(None, "Rib1", "Rib", definition)
    result = ribs.read_native_rib(feature, expected_thickness_mm=8)
    assert result["thickness_mm"] == pytest.approx(8)
    assert result["is_two_sided"] is True
    assert result["extrusion_direction"] == 0


def test_existing_nonrib_feature_cannot_pass_native_readback():
    feature = Feature(None, "Boss1", "Extrusion", Definition())
    with pytest.raises((ValueError, RuntimeError)):
        ribs.read_native_rib(feature, expected_thickness_mm=8)


def test_legacy_wrapper_preserves_meters_false_and_default(monkeypatch):
    part = importlib.import_module("sw_part")
    calls = []
    result = object()
    def insert(m, sketch, thickness, **options):
        calls.append((m, sketch, thickness, options))
        return result
    monkeypatch.setattr(ribs, "insert_native_rib", insert)
    model = object()
    assert part.rib(model, "sketch", .008) is result
    assert part.rib(model, "sketch", .005, False) is result
    assert calls[0][:3] == (model, "sketch", .008)
    assert calls[0][3]["is_two_sided"] is True
    assert calls[1][:3] == (model, "sketch", .005)
    assert calls[1][3]["is_two_sided"] is False


def test_construction_line_is_rejected_before_any_mutation(model):
    model.sketch.segments[0].ConstructionGeometry = True
    with pytest.raises(ValueError, match="Construction"):
        create(model)
    assert model.calls == model.rebuilds == model.selections == model.clears == []


@pytest.mark.parametrize("failure", ["two_bodies", "feature_error", "incomplete_features"])
def test_bad_post_creation_model_feedback_is_rejected(model, failure):
    original_insert = model.insert_rib
    def insert(*args):
        original_insert(*args)
        if failure == "two_bodies": model.body_count = 2
        elif failure == "feature_error": model.feature_error = 1
        else: model.features_complete = False
    model.FeatureManager.InsertRib = insert
    with pytest.raises(RuntimeError):
        create(model)
    assert len(model.calls) == 1


def test_unspecified_expected_volume_reports_only_positive_addition(model):
    model.added_volume = 7500
    result = create(model, expected_added_volume_mm3=None)
    assert result["checks"]["added_volume_mm3"] == 7500
    assert result["checks"]["expected_volume_checked"] is False
    assert result["checks"]["expected_added_volume_mm3"] is None
