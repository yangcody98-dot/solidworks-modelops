"""One native Hole Wizard with multiple 2D placements; no real CAD connection."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sw_native_holes as holes  # noqa: E402


def transform(rotation=None, translation=(0, 0, 0), scale=1):
    return list(rotation or [1, 0, 0, 0, 1, 0, 0, 0, 1]) + list(translation) + [scale, 0, 0, 0]


def test_transform_rotates_then_scales_and_translates_without_transposing_or_scaling_translation():
    matrix = transform([0, 1, 0, -1, 0, 0, 0, 0, 1], (10, -20, 30), 2)
    point = [1, 2, 3]
    assert holes._transform_point(point, matrix) == pytest.approx([6, -18, 36])
    assert point == [1, 2, 3]
    inverse = transform([0, -1, 0, 1, 0, 0, 0, 0, 1], (10, 5, -15), 0.5)
    assert holes._transform_point([6, -18, 36], inverse) == pytest.approx(point)


@pytest.mark.parametrize("point,matrix", [
    ([1, 2], transform()), ([1, 2, float("nan")], transform()),
    ([1, 2, 3], transform()[:-1]), ([1, 2, 3], transform(scale=0)),
    ([1, 2, 3], transform(scale=-1)), ([1, 2, 3], transform(scale=float("inf"))),
])
def test_transform_rejects_missing_or_nonfinite_geometry(point, matrix):
    with pytest.raises(ValueError):
        holes._transform_point(point, matrix)


class FakeSketch:
    def __init__(self, inverse=None, forward=None, *, status=3, is_3d=False):
        self.status, self.is_3d = status, is_3d
        self.ModelToSketchTransform = SimpleNamespace(
            ArrayData=forward or transform(),
            Inverse=SimpleNamespace(ArrayData=inverse or transform()))

    def Is3D(self):
        return self.is_3d

    def GetConstrainedStatus(self):
        return self.status


class FakePoint:
    def __init__(self, sketch, xyz):
        self.sketch = sketch
        self.X, self.Y, self.Z = xyz

    def GetSketch(self):
        return self.sketch


class FakeData:
    def __init__(self, points, reported_count=None):
        self.points, self.reported_count = points, reported_count

    def GetSketchPoints(self):
        return self.points

    def GetSketchPointCount(self):
        return len(self.points) if self.reported_count is None else self.reported_count


@pytest.fixture
def rotated_points():
    inverse = transform([0, 1, 0, -1, 0, 0, 0, 0, 1], (0.05, -0.03, 0.02), 2)
    sketch = FakeSketch(inverse=inverse)
    points = [FakePoint(sketch, xyz) for xyz in
              [(0.001, 0.002, 0), (-0.003, 0.004, 0), (0.005, -0.006, 0), (-0.007, -0.008, 0)]]
    requested = [[46, -28, 20], [42, -36, 20], [62, -20, 20], [66, -44, 20]]
    return SimpleNamespace(sketch=sketch, points=points, requested=requested)


def test_position_readback_uses_inverse_transform_and_matches_unordered_points(rotated_points):
    fixture = rotated_points
    result = holes._positions_readback(FakeData(list(reversed(fixture.points))), fixture.requested)
    assert result["hole_count"] == 4
    assert result["position_sketch_is_3d"] is False
    assert result["position_sketch_constraint_status"] == 3
    for actual, wanted in zip(result["positions_mm"], fixture.requested):
        assert actual == pytest.approx(wanted)
    json.dumps(result, allow_nan=False)


def test_coincident_actual_points_cannot_match_two_overlapping_position_tolerance_balls():
    sketch = FakeSketch(inverse=transform(translation=(0, 0, 0.020)))
    points = [FakePoint(sketch, [0.0000075, 0, 0]), FakePoint(sketch, [0.0000075, 0, 0])]
    # Distinct expected points exceed the input duplicate tolerance. Both actual
    # entries coincide at their midpoint; unique list indices are not unique holes.
    requested = [[0, 0, 20], [0.015, 0, 20]]
    with pytest.raises(RuntimeError):
        holes._positions_readback(FakeData(points), requested)


@pytest.mark.parametrize("failure", ["missing", "extra", "count_mismatch", "duplicate", "wrong_position",
                                    "3d", "unknown_3d", "different_sketch", "underdefined"])
def test_position_readback_rejects_incomplete_or_invalid_group(rotated_points, failure):
    fixture = rotated_points
    points = list(fixture.points)
    reported_count = None
    if failure == "missing":
        points.pop()
    elif failure == "extra":
        points.append(points[0])
    elif failure == "count_mismatch":
        reported_count = 3
    elif failure == "duplicate":
        points[-1] = points[0]
    elif failure == "wrong_position":
        points[-1].X += 0.001
    elif failure == "3d":
        fixture.sketch.is_3d = True
    elif failure == "unknown_3d":
        fixture.sketch.is_3d = None
    elif failure == "different_sketch":
        points[-1].sketch = FakeSketch(inverse=fixture.sketch.ModelToSketchTransform.Inverse.ArrayData)
    else:
        fixture.sketch.status = 2
    with pytest.raises(RuntimeError):
        holes._positions_readback(FakeData(points, reported_count), fixture.requested)


@pytest.mark.parametrize("positions", [[], [[56, 36, 20], [56, 36, 20]],
                                      [[56, 36, 20], [56.005, 36, 20]], [[0, 0]],
                                      [[float("nan"), 0, 20]]])
def test_invalid_or_duplicate_positions_fail_before_any_cad_access(positions):
    class NoCadAccess:
        def __getattr__(self, name):
            pytest.fail(f"Invalid group accessed CAD: {name}")

    with pytest.raises(ValueError):
        holes.create_native_counterbore_group(NoCadAccess(), positions, 9, 16, 6, name="Group")


@pytest.fixture
def group_environment(monkeypatch):
    positions = [[56, 36, 20], [-56, 36, 20], [-56, -36, 20], [56, -36, 20]]
    forward = transform([0, 1, 0, -1, 0, 0, 0, 0, 1], (0, 0, -0.020))
    inverse = transform([0, -1, 0, 1, 0, 0, 0, 0, 1], (0, 0, 0.020))
    position_sketch = FakeSketch(inverse, forward, status=2)
    profile_sketch = FakeSketch(status=3)
    points = [FakePoint(position_sketch, [-0.036, 0.056, 0])]
    state = SimpleNamespace(selected=None, seed_calls=[], selected_features=[], created_points=[],
                            exit_calls=[], rebuilds=[], definitions=0, point_failure=False,
                            constraint_result={"fully_defined": True, "parametric_evidence": True},
                            rebuild_result=True, wrong_active=False)

    class ChildFeature:
        def __init__(self, name, sketch, next_feature=None):
            self.Name, self.sketch, self.next_feature = name, sketch, next_feature

        def GetTypeName2(self):
            return "ProfileFeature"

        def GetSpecificFeature2(self):
            return self.sketch

        def GetNextSubFeature(self):
            return self.next_feature

        def Select2(self, append, mark):
            assert append is False and mark == 0
            state.selected = self
            state.selected_features.append(self.Name)
            return True

    position_feature = ChildFeature("PositionSketch", position_sketch)
    profile_feature = ChildFeature("CrossSectionSketch", profile_sketch, position_feature)

    class WizardFeature:
        def GetDefinition(self):
            state.definitions += 1
            return FakeData(points)

        def GetFirstSubFeature(self):
            return profile_feature  # The placement sketch is deliberately not the first child.

    feature = WizardFeature()

    class Manager:
        ActiveSketch = None

        def CreatePoint(self, x, y, z):
            if state.point_failure:
                return None
            point = FakePoint(self.ActiveSketch, [x, y, z])
            points.append(point)
            state.created_points.append([x, y, z])
            return point

        def InsertSketch(self, update):
            state.exit_calls.append(update)
            self.ActiveSketch = None

    manager = Manager()

    class Model:
        SketchManager = manager

        def ClearSelection2(self, all_marks):
            assert all_marks is True
            state.selected = None

        def EditSketch(self):
            manager.ActiveSketch = profile_sketch if state.wrong_active else state.selected.sketch

        def ForceRebuild3(self, top_only):
            state.rebuilds.append(top_only)
            return state.rebuild_result

    model = Model()
    common_face = object()
    monkeypatch.setattr(holes, "_entry_face", lambda _model, _position: (common_face, [0, 0, 1]))

    def seed(*args, **kwargs):
        state.seed_calls.append((args, kwargs))
        return {"feature": feature, "readback": {"position_mm": positions[0]}, "evidence": {}}

    def constrain(_model):
        assert manager.ActiveSketch is position_sketch
        if state.constraint_result["fully_defined"]:
            position_sketch.status = 3
        return state.constraint_result

    monkeypatch.setattr(holes, "create_native_counterbore", seed)
    monkeypatch.setitem(sys.modules, "sw_sketch_constraints",
                        SimpleNamespace(fully_define_active_sketch=constrain))
    return SimpleNamespace(model=model, positions=positions, state=state, feature=feature,
                           manager=manager, sketch=position_sketch, points=points)


def run_group(environment):
    return holes.create_native_counterbore_group(
        environment.model, environment.positions, 9, 16, 6, name="FourCounterbores")


def test_group_creates_one_feature_and_three_transformed_points_in_its_existing_sketch(group_environment):
    fixture = group_environment
    result = run_group(fixture)
    assert result["feature"] is fixture.feature
    assert len(fixture.state.seed_calls) == 1
    assert fixture.state.selected_features == ["PositionSketch"]
    assert len(fixture.state.created_points) == 3
    for actual, wanted in zip(fixture.state.created_points,
                              [[-0.036, -0.056, 0], [0.036, -0.056, 0], [0.036, 0.056, 0]]):
        assert actual == pytest.approx(wanted)
    assert fixture.state.exit_calls == [True]
    assert fixture.state.rebuilds == [False]
    assert fixture.state.definitions >= 2
    assert fixture.manager.ActiveSketch is None
    assert result["readback"]["hole_count"] == 4
    assert "position_mm" not in result["readback"]
    assert result["sketch_constraints_complete"] is True
    json.dumps({key: value for key, value in result.items() if key != "feature"}, allow_nan=False)


def test_different_supporting_faces_are_rejected_before_creating_any_feature(group_environment, monkeypatch):
    monkeypatch.setattr(holes, "_entry_face", lambda *_args: (object(), [0, 0, 1]))
    with pytest.raises(ValueError, match="same planar face"):
        run_group(group_environment)
    assert group_environment.state.seed_calls == []


@pytest.mark.parametrize("failure", ["point", "underdefined", "no_dimensions", "rebuild", "wrong_active"])
def test_group_failures_stop_without_retrying_the_native_feature(group_environment, failure):
    fixture = group_environment
    if failure == "point":
        fixture.state.point_failure = True
    elif failure == "underdefined":
        fixture.state.constraint_result["fully_defined"] = False
    elif failure == "no_dimensions":
        fixture.state.constraint_result["parametric_evidence"] = False
    elif failure == "rebuild":
        fixture.state.rebuild_result = False
    else:
        fixture.state.wrong_active = True
    with pytest.raises(RuntimeError):
        run_group(fixture)
    assert len(fixture.state.seed_calls) == 1
    if failure != "wrong_active":
        assert fixture.manager.ActiveSketch is None
        assert fixture.state.exit_calls == [True]
    else:
        assert fixture.state.created_points == []
