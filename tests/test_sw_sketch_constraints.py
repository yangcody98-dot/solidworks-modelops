"""Constraint status and true dimension evidence, without connecting to CAD."""
from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from sw_sketch_constraints import (  # noqa: E402
    collect_sketch_constraint_status, fully_define_active_sketch,
)


class Relation:
    def __init__(self, kind):
        self.kind = kind

    def GetRelationType(self):
        return self.kind


class Sketch:
    def __init__(self, status=2, relations=(4, 5, 9), segments=4):
        self.status = status
        self.relations = [Relation(kind) for kind in relations]
        self.RelationManager = SimpleNamespace(GetRelations=self.get_relations)
        self.Is3D = False
        self.segments = [object() for _ in range(segments)]

    def GetConstrainedStatus(self):
        return self.status

    def get_relations(self, filter_value):
        assert filter_value == 0
        return self.relations

    def GetSketchSegments(self):
        return self.segments


class Dimension:
    def __init__(self, name, driven=2, value=0.02):
        self.FullName, self.DrivenState, self.SystemValue = name, driven, value


class DisplayDimension:
    def __init__(self, dimension):
        self.dimension = dimension

    def GetDimension2(self, configuration):
        assert configuration == 0
        return self.dimension


class Feature:
    def __init__(self, name, sketch=None, kind="ProfileFeature", dimensions=2):
        self.Name, self.sketch, self.kind = name, sketch, kind
        self.next = None
        self.next_sub = None
        self.first_sub = None
        self.dimensions = [DisplayDimension(Dimension(f"D{i + 1}@{name}")) for i in range(dimensions)]

    def GetTypeName2(self):
        return self.kind

    def GetSpecificFeature2(self):
        return self.sketch

    def GetFirstSubFeature(self):
        return self.first_sub

    def GetNextFeature(self):
        return self.next

    def GetNextSubFeature(self):
        return self.next_sub

    def GetFirstDisplayDimension(self):
        return self.dimensions[0] if self.dimensions else None

    def GetNextDisplayDimension(self, previous):
        index = self.dimensions.index(previous) + 1
        return self.dimensions[index] if index < len(self.dimensions) else None


class Manager:
    def __init__(self, active, *, result=0, after=3):
        self.ActiveSketch = active
        self.result, self.after = result, after
        self.calls = []

    def FullyDefineSketch(self, *args):
        self.calls.append(args)
        self.ActiveSketch.status = self.after
        return self.result

    def InsertSketch(self, *_args):
        pytest.fail("helper must verify before exit, not exit the caller's sketch")


class Model:
    def __init__(self, feature, active=None, **manager_options):
        self.feature = feature
        self.SketchManager = Manager(active if active is not None else feature.sketch, **manager_options)
        self.selections_cleared = 0

    def FirstFeature(self):
        return self.feature

    def ClearSelection2(self, all_marks):
        assert all_marks is True
        self.selections_cleared += 1

    def SketchAddConstraints(self, *_args):
        pytest.fail("must not blanket Fix sketch entities")


def model_with_sketch(**kwargs):
    return Model(Feature("Sketch1", Sketch()), **kwargs)


def test_success_requires_true_solver_status_and_driving_dimensions_not_api_return():
    model = model_with_sketch(result=987)
    report = fully_define_active_sketch(model)
    assert report["before_status"] == 2
    assert report["after_status"] == 3
    assert report["api_return"] == 987
    assert report["fully_defined"] is True
    assert report["parametric_evidence"] is True
    assert report["driving_dimension_count"] == 2
    assert report["fixed_relation_count"] == 0
    assert model.SketchManager.calls == [(True, True, 1023, True, 1, None, 1, None, 0, 0)]
    assert model.SketchManager.ActiveSketch is model.feature.sketch


@pytest.mark.parametrize("after", [None, 1, 2, 4, 5, 6, 7, 999])
def test_zero_api_return_does_not_make_underdefined_or_unknown_sketch_pass(after):
    model = model_with_sketch(result=0, after=after)
    report = fully_define_active_sketch(model)
    assert report["fully_defined"] is False
    assert report["status"] == "blocked"


@pytest.mark.parametrize("before", [None, 1, 4, 5, 6, 7])
def test_unsolved_initial_status_does_not_trigger_blind_repair(before):
    model = model_with_sketch()
    model.feature.sketch.status = before
    report = fully_define_active_sketch(model)
    assert report["fully_defined"] is False
    assert model.SketchManager.calls == []
    assert model.selections_cleared == 0


@pytest.mark.parametrize("fixed_type", [17, 70, 74])
def test_fully_fixed_ordinary_geometry_is_not_reported_parametric(fixed_type):
    sketch = Sketch(status=3, relations=(fixed_type,))
    model = Model(Feature("Locked", sketch))
    report = fully_define_active_sketch(model)
    assert report["native_fully_defined"] is True
    assert report["fully_defined"] is False
    assert report["parametric_evidence"] is False
    assert report["fixed_relation_count"] == 1
    assert model.SketchManager.calls == []


@pytest.mark.parametrize("driven_state", [None, 0, 1])
def test_reference_or_unknown_dimensions_do_not_count_as_driving(driven_state):
    model = model_with_sketch()
    for display in model.feature.dimensions:
        display.dimension.DrivenState = driven_state
    report = fully_define_active_sketch(model)
    assert report["native_fully_defined"] is True
    assert report["fully_defined"] is False
    assert report["driving_dimension_count"] == 0


def test_unreadable_relations_cannot_hide_fix_constraints():
    model = model_with_sketch()
    model.feature.sketch.relations = [None]
    report = fully_define_active_sketch(model)
    assert report["relations_complete"] is False
    assert report["fully_defined"] is False


def test_missing_active_sketch_is_read_only_block():
    model = model_with_sketch()
    model.SketchManager.ActiveSketch = None
    result = fully_define_active_sketch(model)
    assert result["fully_defined"] is False
    assert model.selections_cleared == 0
    assert not model.SketchManager.calls


def test_unknown_or_missing_dimension_value_cannot_pass():
    model = model_with_sketch()
    model.feature.dimensions[0].dimension.SystemValue = float("nan")
    result = fully_define_active_sketch(model)
    assert result["dimensions_complete"] is False
    assert result["fully_defined"] is False
    collected = collect_sketch_constraint_status(model)
    assert collected["all_fully_defined"] is False
    assert collected["all_parametric"] is False


def test_3d_sketch_is_not_auto_modified_by_2d_helper():
    model = model_with_sketch()
    model.feature.sketch.Is3D = True
    result = fully_define_active_sketch(model)
    assert result["fully_defined"] is False
    assert model.SketchManager.calls == []


def test_unknown_sketch_dimension_does_not_enter_2d_solver():
    model = model_with_sketch()
    model.feature.sketch.Is3D = None
    result = fully_define_active_sketch(model)
    assert result["fully_defined"] is False
    assert model.SketchManager.calls == []


def test_collector_visits_absorbed_sketches_and_is_read_only():
    boss = Feature("Boss", kind="Boss", dimensions=0)
    profile = Feature("Absorbed", Sketch(status=3))
    boss.first_sub = profile
    second = Feature("Other", Sketch(status=2))
    boss.next = second
    model = Model(boss, active=profile.sketch)
    result = collect_sketch_constraint_status(model)
    assert result["sketch_count"] == 2
    assert result["all_fully_defined"] is False
    assert {s["name"] for s in result["sketches"]} == {"Absorbed", "Other"}
    assert model.selections_cleared == 0
    assert model.SketchManager.calls == []


def hole_wizard_model(*, profile_segments=7, fixed=(17,), driving=4, owner_type="HoleWzd"):
    hole = Feature("NativeCounterbore", kind=owner_type, dimensions=0)
    position = Feature("Position", Sketch(status=3, relations=(1, 1), segments=0))
    profile = Feature("Section", Sketch(status=3, relations=(4, 5) + fixed, segments=profile_segments), dimensions=driving)
    hole.first_sub = position
    position.next_sub = profile
    return Model(hole, active=position.sketch), profile


def test_native_hole_profile_anchor_is_allowed_only_with_owner_and_driving_evidence():
    model, _ = hole_wizard_model()
    result = collect_sketch_constraint_status(model)
    assert result["all_fully_defined"] is True
    profile = next(s for s in result["sketches"] if s["name"] == "Section")
    assert profile["owner_feature"] == {"name": "NativeCounterbore", "type": "HoleWzd"}
    assert profile["native_feature_controlled"] is True
    assert profile["fixed_relation_count"] == 1
    assert profile["driving_dimension_count"] == 4
    assert profile["parametric_evidence"] is True


@pytest.mark.parametrize("kwargs", [
    {"profile_segments": 0}, {"fixed": (17, 17)}, {"fixed": (74,)},
    {"driving": 1}, {"owner_type": "Boss"},
])
def test_hole_wizard_exception_does_not_allow_position_points_or_blanket_fix(kwargs):
    model, _ = hole_wizard_model(**kwargs)
    result = collect_sketch_constraint_status(model)
    profile = next(s for s in result["sketches"] if s["name"] == "Section")
    assert profile["native_feature_controlled"] is False
    assert result["all_fully_defined"] is False


def test_duplicate_timeline_sketch_is_not_counted_twice_and_gains_absorbed_owner():
    model, profile = hole_wizard_model()
    # The same section appears first at top level and later under HoleWzd.
    profile.next = model.feature
    model.feature = profile
    result = collect_sketch_constraint_status(model)
    assert result["all_fully_defined"] is True
    assert result["sketch_count"] == 2
    assert next(s for s in result["sketches"] if s["name"] == "Section")["native_feature_controlled"] is True


def test_cyclic_or_truncated_feature_tree_does_not_pass():
    model = Model(Feature("Sketch1", Sketch(status=3)))
    model.feature.next = model.feature
    result = collect_sketch_constraint_status(model)
    assert result["complete"] is False
    assert result["all_fully_defined"] is False
    model.feature.next = Feature("Sketch2", Sketch(status=3))
    result = collect_sketch_constraint_status(model, feature_limit=1)
    assert result["complete"] is False
    assert result["all_fully_defined"] is False


def test_dimensionless_external_relation_case_requires_explicit_opt_out():
    model = Model(Feature("PointAtOrigin", Sketch(status=3, relations=(9,), segments=0), dimensions=0))
    assert fully_define_active_sketch(model)["fully_defined"] is False
    assert fully_define_active_sketch(model, require_driving_dimensions=False)["fully_defined"] is True


def test_unsupported_relation_mask_is_rejected_before_writing():
    model = model_with_sketch()
    with pytest.raises(ValueError):
        fully_define_active_sketch(model, relations_mask=1024)
    assert model.SketchManager.calls == []


def origin_selection(model, accepted_name, point=None):
    """Fake a localized model origin without creating or selecting real CAD."""
    point = point if point is not None else SimpleNamespace(X=0.0, Y=0.0, Z=0.0)
    calls = []

    def select(name, kind, x, y, z, append, mark, datum, options):
        assert kind == "EXTSKETCHPOINT"
        assert (x, y, z, append, mark, options) == (0, 0, 0, False, 6, 0)
        assert model.selections_cleared > 0
        calls.append(name)
        return name == accepted_name

    model.Extension = SimpleNamespace(SelectByID2=select)
    model.SelectionManager = SimpleNamespace(GetSelectedObject6=lambda index, mark: point)
    return point, calls


@pytest.mark.parametrize("name", ["Point1@Origin", "点1@原点"])
def test_real_origin_point_is_passed_to_both_datum_parameters(name):
    model = model_with_sketch()
    point, calls = origin_selection(model, name)
    result = fully_define_active_sketch(model)
    assert result["fully_defined"] is True
    assert result["datum"] == {"status": "model_origin", "name": name,
                               "coordinates_m": [0.0, 0.0, 0.0]}
    assert calls[-1] == name
    args = model.SketchManager.calls[0]
    assert args[5] is point and args[7] is point


def test_actual_origin_feature_name_is_used_for_localized_or_renamed_origin():
    model = model_with_sketch()
    model.feature.next = Feature("MyDatumOrigin", kind="OriginProfileFeature", dimensions=0)
    point, calls = origin_selection(model, "点1@MyDatumOrigin")
    report = fully_define_active_sketch(model)
    assert report["datum"]["status"] == "model_origin"
    assert calls == ["Point1@Origin", "点1@原点", "Point1@MyDatumOrigin", "点1@MyDatumOrigin"]
    assert model.SketchManager.calls[0][5] is point


@pytest.mark.parametrize("point", [
    SimpleNamespace(X=0.01, Y=0.0, Z=0.0),
    SimpleNamespace(X=0.0, Y=float("nan"), Z=0.0),
    SimpleNamespace(X=0.0, Y=0.0),
])
def test_wrong_or_unknown_origin_cannot_be_used_as_a_datum(point):
    model = model_with_sketch(after=2)
    origin_selection(model, "Point1@Origin", point)
    result = fully_define_active_sketch(model)
    assert result["datum"]["status"] == "null"
    assert model.SketchManager.calls[0][5] is None
    assert model.SketchManager.calls[0][7] is None
    assert result["fully_defined"] is False


def test_failed_origin_lookup_has_bounded_candidates_and_retains_null_behavior():
    model = model_with_sketch(after=3)
    _, calls = origin_selection(model, "not found")
    result = fully_define_active_sketch(model)
    assert calls == ["Point1@Origin", "点1@原点"]
    assert result["datum"]["status"] == "null"
    assert result["fully_defined"] is True
    assert model.SketchManager.calls[0] == (True, True, 1023, True, 1, None, 1, None, 0, 0)


def test_fully_defined_sketch_does_not_select_or_solve_again():
    model = model_with_sketch()
    model.feature.sketch.status = 3
    _, calls = origin_selection(model, "Point1@Origin")
    assert fully_define_active_sketch(model)["fully_defined"] is True
    assert calls == []
    assert model.selections_cleared == 0


def test_dimension_enumeration_excludes_plane_and_neighbor_feature_dimensions():
    model = model_with_sketch()
    own = model.feature.dimensions
    for display in own:
        display.dimension.FullName += "@Test.Part"
    plane = DisplayDimension(Dimension("D1@Demo_Base_Top@Test.Part"))
    neighbor = DisplayDimension(Dimension("D1@Sketch11@Test.Part", driven=None))
    model.feature.dimensions = [plane, own[0], neighbor, own[1]]
    report = fully_define_active_sketch(model)
    assert report["dimension_count"] == 2
    assert report["driving_dimension_count"] == 2
    assert report["dimensions_complete"] is True
    assert report["excluded_dimension_names"] == [plane.dimension.FullName, neighbor.dimension.FullName]
    assert {d["name"] for d in report["dimensions"]} == {"D1@Sketch1@Test.Part", "D2@Sketch1@Test.Part"}
    assert collect_sketch_constraint_status(model)["all_parametric"] is True


def test_unrelated_driving_dimension_cannot_make_dimensionless_sketch_pass():
    model = model_with_sketch()
    model.feature.dimensions = [DisplayDimension(Dimension("D1@Demo_Base_Top@零件41.Part"))]
    report = fully_define_active_sketch(model)
    assert report["driving_dimension_count"] == 0
    assert report["fully_defined"] is False
    assert collect_sketch_constraint_status(model)["all_parametric"] is False


@pytest.mark.parametrize("name", ["D1", "D1@@Part", "@Sketch1@Part"])
def test_unknown_dimension_owner_blocks_complete_evidence(name):
    model = model_with_sketch()
    model.feature.dimensions[0].dimension.FullName = name
    result = fully_define_active_sketch(model)
    assert result["dimensions_complete"] is False
    assert result["fully_defined"] is False
