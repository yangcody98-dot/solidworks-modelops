"""Native Hole Wizard contract tests using fake COM only; never attach to CAD."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sw_native_holes import create_native_counterbore  # noqa: E402
import sw_native_holes as native_holes  # noqa: E402


class FakeSketch:
    def __init__(self):
        self.is_3d = False
        self.constraint_status = 2
        self.Name = "HolePositions"
        inverse = SimpleNamespace(ArrayData=[1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0,
                                             0, 0, 0.020, 1.0, 0, 0, 0])
        self.ModelToSketchTransform = SimpleNamespace(Inverse=inverse)

    def Is3D(self):
        return self.is_3d

    def GetConstrainedStatus(self):
        return self.constraint_status


class FakePoint:
    def __init__(self, sketch):
        self.X, self.Y, self.Z = 0.056, 0.036, 0.0
        self.sketch = sketch

    def GetSketch(self):
        return self.sketch


class FakeDefinition:
    Type = 14
    ThruHoleDiameter = 0.009
    CounterBoreDiameter = 0.016
    CounterBoreDepth = 0.006
    EndCondition = 1
    Standard2 = 8
    FastenerType2 = 139
    FastenerSize = "M8"

    def __init__(self, point):
        self.points = [point]
        self.rollback_calls = []

    def GetSketchPointCount(self):
        return len(self.points)

    def GetSketchPoints(self):
        return self.points

    def AccessSelections(self, *_args):
        self.rollback_calls.append("AccessSelections")
        pytest.fail("Reading scalar and position evidence must not roll back the feature")


class FakeSubfeature:
    Name = "HolePositions"

    def __init__(self, sketch):
        self.sketch = sketch

    def GetTypeName2(self):
        return "ProfileFeature"

    def GetSpecificFeature2(self):
        return self.sketch

    def GetNextSubFeature(self):
        return None


class FakeFeature:
    def __init__(self, definition, sketch):
        self.Name = "HoleWizard1"
        self.type_name = "HoleWzd"
        self.definition = definition
        self.subfeature = FakeSubfeature(sketch)

    def GetTypeName2(self):
        return self.type_name

    def GetDefinition(self):
        return self.definition

    def GetFirstSubFeature(self):
        return self.subfeature

    def GetErrorCode2(self):
        return 0


class FakeFace:
    Normal = (0.0, 0.0, 1.0)

    def __init__(self):
        self.planar = True

    def GetSurface(self):
        return SimpleNamespace(IsPlane=lambda: self.planar)

    def GetClosestPointOn(self, x, y, _z):
        return (x, y, 0.020, 0.0, 0.0)


class FakeSelection:
    def __init__(self, model):
        self.model = model
        self.reported_count = 1
        self.type_code = 2
        self.point = (0.056, 0.036, 0.020)

    def GetSelectedObjectCount2(self, mark):
        assert mark == -1
        return self.reported_count if self.model.selected else 0

    def GetSelectedObjectType3(self, index, mark):
        assert index == 1 and mark in (0, -1)
        return self.type_code

    def GetSelectedObject6(self, index, mark):
        assert index == 1 and mark in (0, -1)
        return self.model.face

    def GetSelectionPoint2(self, index, mark):
        assert index == 1 and mark in (0, -1)
        return self.point


class FakeModel:
    def __init__(self):
        self.doc_type = 1
        self.face = FakeFace()
        self.sketch = FakeSketch()
        self.point = FakePoint(self.sketch)
        self.definition = FakeDefinition(self.point)
        self.feature = FakeFeature(self.definition, self.sketch)
        self.wizard_result = self.feature
        self.wizard_calls = []
        self.ray_calls = []
        self.clear_calls = []
        self.selected = False
        self.selection_success = True
        self.existing_feature = None
        self.SelectionManager = FakeSelection(self)
        self.Extension = SimpleNamespace(SelectByRay=self.select_ray)
        self.FeatureManager = SimpleNamespace(HoleWizard5=self.hole_wizard)

    def GetType(self):
        return self.doc_type

    def FeatureByName(self, _name):
        return self.existing_feature

    def GetBodies2(self, body_type, visible_only):
        assert body_type == 0 and visible_only is False
        return [SimpleNamespace(GetFaces=lambda: [self.face])]

    def GetPartBox(self, tight):
        assert tight is True
        return [-0.07, -0.05, 0.0, 0.07, 0.05, 0.020]

    def ClearSelection2(self, all_marks):
        self.clear_calls.append(all_marks)
        self.selected = False

    def select_ray(self, *args):
        self.ray_calls.append(args)
        self.selected = self.selection_success
        return self.selection_success

    def hole_wizard(self, *args):
        self.wizard_calls.append(args)
        return self.wizard_result


@pytest.fixture
def model():
    return FakeModel()


def create(model, **overrides):
    options = {"position_mm": [56.0, 36.0, 20.0], "hole_diameter_mm": 9.0,
               "counterbore_diameter_mm": 16.0, "counterbore_depth_mm": 6.0,
               "name": "MountCounterbore"}
    options.update(overrides)
    return create_native_counterbore(model, **options)


def test_creates_native_wizard_with_exact_sdk_parameters_and_readback(model):
    result = create(model)
    assert result["feature"] is model.feature
    assert {"readback", "subsketches", "evidence"} <= result.keys()
    assert len(model.wizard_calls) == 1
    args = model.wizard_calls[0]
    assert len(args) == 27
    assert args[:5] == (0, 8, 139, "M8", 1)
    assert args[5:10] == pytest.approx((0.009, 0.020, -1, 0.016, 0.006))
    assert args[20] == ""
    assert model.feature.Name == "MountCounterbore"
    assert model.definition.rollback_calls == []


@pytest.mark.parametrize("overrides", [
    {"position_mm": [56, 36]}, {"position_mm": [56, float("nan"), 20]},
    {"hole_diameter_mm": 0}, {"hole_diameter_mm": float("inf")},
    {"counterbore_diameter_mm": 9}, {"counterbore_diameter_mm": 8},
    {"counterbore_depth_mm": 0}, {"counterbore_depth_mm": -1},
    {"name": ""}, {"standard": "unknown"}, {"size": ""},
])
def test_invalid_input_fails_before_any_selection_or_creation(model, overrides):
    with pytest.raises((ValueError, TypeError)):
        create(model, **overrides)
    assert model.wizard_calls == model.ray_calls == model.clear_calls == []


def test_nonpart_document_rejected_before_mutation(model):
    model.doc_type = 2
    with pytest.raises((ValueError, RuntimeError)):
        create(model)
    assert model.wizard_calls == model.ray_calls == model.clear_calls == []


def test_duplicate_feature_name_does_not_replace_existing_feature(model):
    model.existing_feature = object()
    with pytest.raises((ValueError, RuntimeError)):
        create(model)
    assert model.wizard_calls == model.ray_calls == model.clear_calls == []


def test_nonplanar_entry_face_is_rejected_before_hole_creation(model):
    model.face.planar = False
    with pytest.raises(RuntimeError):
        create(model)
    assert model.wizard_calls == []


def test_failed_face_selection_does_not_call_hole_wizard(model):
    model.selection_success = False
    with pytest.raises(RuntimeError):
        create(model)
    assert model.wizard_calls == []


@pytest.mark.parametrize("field,value", [("reported_count", 2), ("type_code", 1),
                                        ("point", (0.055, 0.036, 0.020))])
def test_wrong_selection_evidence_prevents_hole_creation(model, field, value):
    setattr(model.SelectionManager, field, value)
    with pytest.raises(RuntimeError):
        create(model)
    assert model.wizard_calls == []


def test_null_wizard_feature_is_a_failure_without_extrusion_fallback(model):
    model.wizard_result = None
    with pytest.raises(RuntimeError):
        create(model)
    assert len(model.wizard_calls) == 1


def test_generic_cut_cannot_be_reported_as_native_hole_wizard(model):
    model.feature.type_name = "Cut"
    with pytest.raises(RuntimeError):
        create(model)


@pytest.mark.parametrize("field,value", [("Type", 10), ("ThruHoleDiameter", 0.008),
    ("CounterBoreDiameter", 0.015), ("CounterBoreDepth", 0.005), ("EndCondition", 0),
    ("Standard2", 0), ("FastenerType2", 136), ("FastenerSize", "M6")])
def test_incorrect_feature_data_is_not_success(model, field, value):
    setattr(model.definition, field, value)
    with pytest.raises(RuntimeError):
        create(model)


def test_3d_location_sketch_is_rejected(model):
    model.sketch.is_3d = True
    with pytest.raises(RuntimeError):
        create(model)


@pytest.mark.parametrize("points", [[], "duplicate"])
def test_requires_exactly_one_readable_location_point(model, points):
    model.definition.points = [model.point, model.point] if points == "duplicate" else points
    with pytest.raises(RuntimeError):
        create(model)


def test_model_space_position_must_match_requested_coordinates(model):
    model.sketch.ModelToSketchTransform.Inverse.ArrayData[11] = 0.019
    with pytest.raises(RuntimeError):
        create(model)


def test_unavailable_transform_does_not_assume_sketch_coordinates_are_world_coordinates(model):
    model.sketch.ModelToSketchTransform.Inverse.ArrayData = None
    with pytest.raises(RuntimeError):
        create(model)


class FakeThroughDefinition(FakeDefinition):
    Type = 25
    ThruHoleDiameter = 0.006
    FastenerType2 = 143
    FastenerSize = "\u00d86.0"

    @property
    def HoleDiameter(self):
        pytest.fail("swHoleThru uses ThruHoleDiameter, not the blind-hole diameter field")

    @property
    def CounterBoreDiameter(self):
        pytest.fail("Straight through-hole must not read inapplicable counterbore diameter")

    @property
    def CounterBoreDepth(self):
        pytest.fail("Straight through-hole must not read inapplicable counterbore depth")


@pytest.fixture
def through_model(model):
    model.definition = FakeThroughDefinition(model.point)
    model.feature.definition = model.definition
    return model


def create_through(model, **overrides):
    options = {"position_mm": [56.0, 36.0, 20.0], "diameter_mm": 6.0,
               "name": "NativeDowelHole", "experimental": True}
    options.update(overrides)
    return native_holes.create_native_through_hole(model, **options)


def test_native_through_hole_is_blocked_by_default_without_any_cad_access():
    class UntouchedCad:
        def __getattr__(self, name):
            pytest.fail(f"Default-blocked experimental function accessed CAD: {name}")

    with pytest.raises(NotImplementedError, match="not validated"):
        native_holes.create_native_through_hole(
            UntouchedCad(), [56, 36, 20], 6, name="MustNotCreate")


def test_native_through_hole_uses_verified_iso_drill_size_and_correct_readback(through_model):
    result = create_through(through_model)
    assert result["feature"] is through_model.feature
    assert {"readback", "subsketches", "evidence"} <= result.keys()
    assert len(through_model.wizard_calls) == 1
    args = through_model.wizard_calls[0]
    assert len(args) == 27
    assert args[:5] == (2, 8, 143, "\u00d86.0", 1)
    assert args[5:8] == pytest.approx((0.006, 0.020, -1))
    assert through_model.feature.Name == "NativeDowelHole"
    assert through_model.definition.rollback_calls == []


def test_other_through_diameter_requires_explicit_database_size_before_mutation(through_model):
    with pytest.raises(ValueError):
        create_through(through_model, diameter_mm=8.0)
    assert through_model.wizard_calls == through_model.ray_calls == through_model.clear_calls == []


def test_explicit_through_hole_size_is_forwarded_without_guessing(through_model):
    through_model.definition.FastenerSize = "\u00d88.0"
    through_model.definition.ThruHoleDiameter = 0.008
    result = create_through(through_model, diameter_mm=8.0, size="\u00d88.0")
    assert result["feature"] is through_model.feature
    assert through_model.wizard_calls[0][3] == "\u00d88.0"
    assert through_model.wizard_calls[0][5] == pytest.approx(0.008)


@pytest.mark.parametrize("overrides", [{"diameter_mm": 0}, {"diameter_mm": float("nan")},
    {"size": ""}, {"position_mm": [0, 0]}, {"name": ""}])
def test_invalid_through_hole_request_is_rejected_before_mutation(through_model, overrides):
    with pytest.raises((ValueError, TypeError)):
        create_through(through_model, **overrides)
    assert through_model.wizard_calls == through_model.ray_calls == through_model.clear_calls == []


@pytest.mark.parametrize("field,value", [("Type", 22), ("EndCondition", 0),
    ("ThruHoleDiameter", 0.005), ("FastenerType2", 139), ("FastenerSize", "M6")])
def test_through_hole_wrong_native_parameters_never_pass(through_model, field, value):
    setattr(through_model.definition, field, value)
    with pytest.raises(RuntimeError):
        create_through(through_model)


def test_through_hole_null_result_has_no_cut_extrude_fallback(through_model):
    through_model.wizard_result = None
    with pytest.raises(RuntimeError):
        create_through(through_model)
    assert len(through_model.wizard_calls) == 1
