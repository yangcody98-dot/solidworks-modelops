"""Pure fake-COM tests; importing/capturing never connects to SolidWorks."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sw_model_context as model_context  # noqa: E402
from sw_model_context import capture_document_state, capture_model_context, capture_session_context  # noqa: E402


class Feature:
    def __init__(self, name="Base", kind="Boss", error=0, next_feature=None):
        self.Name = name
        self.kind = kind
        self.error = error
        self.next_feature = next_feature

    def GetTypeName2(self):
        return self.kind

    def GetErrorCode(self):
        return self.error

    def GetNextFeature(self):
        return self.next_feature


class Body:
    def __init__(self, volume=0.000001, box=(-0.01, -0.02, 0, 0.03, 0.04, 0.005)):
        self.volume = volume
        self.box = box
        self.calls = []

    def GetBodyBox(self):
        self.calls.append("GetBodyBox")
        return self.box

    def GetMassProperties(self, density):
        assert density == 1.0
        self.calls.append("GetMassProperties")
        return [0, 0, 0, self.volume, 123.0, self.volume * density] + [0] * 6


class Selection:
    def __init__(self, entries=()):
        self.entries = tuple(entries)
        self.calls = []

    def GetSelectedObjectCount2(self, mark):
        assert mark == -1
        self.calls.append("count")
        return len(self.entries)

    def GetSelectedObjectType3(self, index, mark):
        assert mark == -1
        self.calls.append(("type", index))
        return self.entries[index - 1][0]

    def GetSelectedObject6(self, index, mark):
        assert mark == -1
        self.calls.append(("object", index))
        value = self.entries[index - 1][1]
        if isinstance(value, Exception):
            raise value
        return value


class Model:
    FORBIDDEN = {"ForceRebuild3", "EditRebuild3", "Rebuild", "ClearSelection2",
                 "Save3", "SaveAs", "ShowNamedView2", "ViewZoomtofit2",
                 "ResolveAllLightWeightComponents", "GetComponents", "GetUnits"}

    def __init__(self, title="Fixture.SLDPRT", path=r"C:\parts\Fixture.SLDPRT", bodies=None, kind=1):
        self.title, self.path, self.kind = title, path, kind
        self.save_flag = True
        self.ConfigurationManager = SimpleNamespace(ActiveConfiguration=SimpleNamespace(Name="Default"))
        self.SelectionManager = Selection()
        self.feature = None
        self.bodies = [Body()] if bodies is None else bodies
        self.calls = []
        self.next_document = None
        self.mutations = []

    def __getattr__(self, name):
        if name in self.FORBIDDEN:
            self.mutations.append(name)
            raise AssertionError("Forbidden read-side operation: " + name)
        raise AttributeError(name)

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return self.path

    def GetType(self):
        return self.kind

    def GetSaveFlag(self):
        return self.save_flag

    def FirstFeature(self):
        return self.feature

    def GetPartBox(self, no_conversion):
        assert no_conversion is True
        self.calls.append("GetPartBox")
        return [-0.01, -0.02, 0, 0.03, 0.04, 0.005]

    def GetBodies2(self, kind, visible_only):
        assert (kind, visible_only) == (0, False)
        self.calls.append("GetBodies2")
        return self.bodies

    def GetNext(self):
        return self.next_document


def assert_json(context):
    json.dumps(context, ensure_ascii=False, allow_nan=False)


def test_method_snapshot_units_features_selection_and_read_only():
    model = Model(bodies=[Body(0.000001), Body(0.000002)])
    model.feature = Feature(next_feature=Feature("Hole", "HoleWzd", 7))
    selection = ((22, SimpleNamespace(Name="Hole")), (20, SimpleNamespace(Name2="Fixture-1")))
    model.SelectionManager = Selection(selection)

    context = capture_model_context(model)

    assert context["document"] == {
        "id": context["document"]["id"], "title": model.title,
        "path": model.path, "type": 1, "save_flag": True, "configuration": "Default",
    }
    assert len(context["document"]["id"]) == 24
    assert context["units"] == {"length": "mm", "volume": "mm^3"}
    assert context["geometry"]["bbox_mm"] == [-10, -20, 0, 30, 40, 5]
    assert context["geometry"]["bbox_size_mm"] == [40, 60, 5]
    assert context["geometry"]["volume_mm3"] == pytest.approx(3000)
    assert context["geometry"]["body_count"] == 2
    assert context["geometry"]["status"] == "available"
    assert context["geometry"]["bbox_approximate"] is True
    assert context["features"] == [{"name": "Base", "type": "Boss", "error_code": 0}, {"name": "Hole", "type": "HoleWzd", "error_code": 7}]
    assert context["features_complete"] is True
    assert context["selection"]["objects"] == [{"index": 1, "type": 22, "name": "Hole"}, {"index": 2, "type": 20, "name": "Fixture-1"}]
    assert context["selection"]["complete"] is True
    assert context["warnings"] == []
    assert model.mutations == [] and model.save_flag is True
    assert model.SelectionManager.entries == selection
    assert_json(context)


def test_property_style_getters_and_error_code2_tuple():
    feature = SimpleNamespace(Name="Imported", GetTypeName2="Imported", GetErrorCode2=(12, False), GetNextFeature=None)
    model = SimpleNamespace(
        GetTitle="PropertyPart", GetPathName="", GetType=1, GetSaveFlag=False,
        ConfigurationManager=lambda: SimpleNamespace(ActiveConfiguration=lambda: SimpleNamespace(Name=lambda: "ConfigA")),
        FirstFeature=feature,
        SelectionManager=SimpleNamespace(GetSelectedObjectCount2=0),
        GetPartBox=(0, 0, 0, 0.001, 0.002, 0.003),
        GetBodies2=(SimpleNamespace(GetBodyBox=(0, 0, 0, 0.001, 0.002, 0.003), GetMassProperties=(0, 0, 0, 0.000000006)),),
    )
    context = capture_model_context(model)
    assert context["document"]["configuration"] == "ConfigA"
    assert context["document"]["save_flag"] is False
    assert context["features"][0]["error_code"] == 12
    assert context["geometry"]["bbox_size_mm"] == [1, 2, 3]
    assert context["geometry"]["volume_mm3"] == pytest.approx(6)
    assert context["warnings"] == []
    assert_json(context)


def test_callable_dispatch_property_does_not_invoke_its_default_member():
    class CallableDispatch(SimpleNamespace):
        _oleobj_ = object()

        def __call__(self, *args):
            pytest.fail("A COM property's default member must not be invoked")

    model = Model()
    model.ConfigurationManager = CallableDispatch(
        ActiveConfiguration=CallableDispatch(Name="ConfigA"),
    )
    model.SelectionManager = CallableDispatch(GetSelectedObjectCount2=lambda mark: 0)
    context = capture_model_context(model, include_geometry=False)
    assert context["document"]["configuration"] == "ConfigA"
    assert context["selection"]["count"] == 0
    assert context["warnings"] == []


def test_missing_fields_remain_unknown_and_warn():
    context = capture_model_context(object())
    assert all(value is None for value in context["document"].values())
    assert context["features"] == [] and not context["features_complete"]
    assert context["selection"]["count"] is None
    assert context["geometry"]["body_count"] is None
    assert context["geometry"]["volume_mm3"] is None
    assert context["geometry"]["bbox_mm"] is None
    assert any("document.title" in item for item in context["warnings"])
    assert any("features.first" in item for item in context["warnings"])
    assert_json(context)


def test_partial_body_data_does_not_report_partial_volume_as_total():
    class UnmeasurableBody(Body):
        def GetMassProperties(self, density):
            raise RuntimeError("body unavailable")

    model = Model(bodies=[Body(), UnmeasurableBody()])
    context = capture_model_context(model)
    geometry = context["geometry"]
    assert geometry["body_count"] == 2
    assert geometry["measured_body_count"] == 1
    assert geometry["volume_mm3"] is None
    assert geometry["bodies"][0]["volume_mm3"] == pytest.approx(1000)
    assert geometry["bodies"][1]["volume_mm3"] is None
    assert geometry["status"] == "partial"
    assert any("body unavailable" in item for item in context["warnings"])
    assert_json(context)


def test_no_solid_bodies_is_distinct_from_unreadable_bodies():
    empty = Model(bodies=[])
    empty.GetBodies2 = lambda *args: None
    context = capture_model_context(empty)
    assert context["geometry"]["body_count"] == 0
    assert context["geometry"]["volume_mm3"] == 0

    def fail(*args):
        raise RuntimeError("lightweight data unavailable")

    empty.GetBodies2 = fail
    context = capture_model_context(empty)
    assert context["geometry"]["body_count"] is None
    assert context["geometry"]["volume_mm3"] is None
    assert any("lightweight" in item for item in context["warnings"])


def test_invalid_values_never_leak_nan_or_fake_measurements():
    model = Model(bodies=[Body(float("nan"), (1, 0, 0, 0, 1, 1))])
    model.GetPartBox = lambda *args: [0, 0, 0, float("inf"), 1, 1]
    context = capture_model_context(model)
    assert context["geometry"]["bbox_mm"] is None
    assert context["geometry"]["volume_mm3"] is None
    assert any("non-finite" in item for item in context["warnings"])
    assert any("minimum exceeds" in item for item in context["warnings"])
    assert_json(context)


def test_part_box_failure_falls_back_to_all_solid_body_bounds():
    model = Model(bodies=[Body(box=(0, 0, 0, .01, .01, .01)), Body(box=(.02, -.01, 0, .03, .01, .01))])
    model.GetPartBox = None
    context = capture_model_context(model)
    assert context["geometry"]["bbox_mm"] == [0, -10, 0, 30, 10, 10]
    assert context["geometry"]["bbox_source"].startswith("union")
    assert any("geometry.bbox_mm" in item for item in context["warnings"])


def test_features_are_bounded_and_traversal_failure_is_explicit():
    model = Model()
    model.feature = Feature(next_feature=Feature("Second"))
    context = capture_model_context(model, feature_limit=1, include_geometry=False)
    assert len(context["features"]) == 1
    assert not context["features_complete"]
    assert any("truncated" in item for item in context["warnings"])
    model.feature.next_feature = model.feature
    context = capture_model_context(model, include_geometry=False)
    assert len(context["features"]) == 1
    assert any("repeated COM object" in item for item in context["warnings"])


def test_feature_error_unavailable_is_not_success():
    model = Model()
    model.feature = SimpleNamespace(Name="Base", GetTypeName2="Boss", GetNextFeature=None)
    context = capture_model_context(model, include_geometry=False)
    assert context["features"][0]["error_code"] is None
    assert any("error_code unavailable" in item for item in context["warnings"])


def test_disabled_geometry_never_calls_geometry_getters():
    model = Model()
    context = capture_model_context(model, include_geometry=False)
    assert context["geometry"]["status"] == "not_requested"
    assert context["geometry"]["volume_mm3"] is None
    assert model.calls == [] and model.mutations == []


def test_assembly_bounds_do_not_resolve_or_traverse_components():
    model = Model(kind=2)
    model.GetBox = lambda options: (0, 0, 0, .1, .2, .3)
    context = capture_model_context(model)
    assert context["geometry"]["bbox_size_mm"] == [100, 200, 300]
    assert context["geometry"]["body_count"] is None
    assert context["geometry"]["volume_mm3"] is None
    assert context["geometry"]["scope"] == "assembly_bounds_only"
    assert model.calls == [] and model.mutations == []
    assert any("not resolved" in item for item in context["warnings"])


def test_drawing_geometry_is_explicitly_not_applicable():
    model = Model(kind=3)
    context = capture_model_context(model)
    assert context["geometry"]["status"] == "not_applicable"
    assert context["document"]["configuration"] is None
    assert model.calls == []


def test_selection_failures_preserve_original_count_and_order():
    model = Model()
    model.SelectionManager = Selection(((2, RuntimeError("unavailable face")), (22, SimpleNamespace(Name="Kept"))))
    context = capture_model_context(model, include_geometry=False)
    assert context["selection"]["count"] == 2
    assert context["selection"]["objects"] == [{"index": 1, "type": 2, "name": None}, {"index": 2, "type": 22, "name": "Kept"}]
    assert context["selection"]["complete"] is False
    assert any("unavailable face" in item for item in context["warnings"])
    assert model.mutations == []


def test_document_id_is_stable_but_configuration_specific():
    model = Model()
    first = capture_model_context(model, include_geometry=False)["document"]["id"]
    model.save_flag = False
    model.path = r"c:/PARTS/Fixture.SLDPRT"
    assert capture_model_context(model, include_geometry=False)["document"]["id"] == first
    model.ConfigurationManager.ActiveConfiguration.Name = "Other"
    assert capture_model_context(model, include_geometry=False)["document"]["id"] != first


def test_session_enumerates_without_activation_or_geometry():
    first = Model()
    second = Model("Second.SLDPRT", r"C:\parts\Second.SLDPRT")
    first.next_document = second
    sw = SimpleNamespace(ActiveDoc=second, GetFirstDocument=lambda: first)
    result = capture_session_context(sw)
    assert [doc["title"] for doc in result["documents"]] == [first.title, second.title]
    assert result["active_document"]["id"] == result["documents"][1]["id"]
    assert result["documents_complete"] is True
    assert first.calls == second.calls == []
    assert first.mutations == second.mutations == []
    assert result["warnings"] == []
    assert_json(result)


def test_session_fallback_and_empty_session():
    model = Model()
    result = capture_session_context(SimpleNamespace(ActiveDoc=lambda: model, GetDocuments=(model,)))
    assert len(result["documents"]) == 1
    assert result["documents_complete"] is True
    assert any("GetFirstDocument" in item for item in result["warnings"])
    result = capture_session_context(SimpleNamespace(ActiveDoc=None, GetFirstDocument=None))
    assert result == {"active_document": None, "documents": [], "documents_complete": True, "warnings": []}


def test_session_cycle_and_unavailable_active_document_warn():
    model = Model()
    model.next_document = model
    result = capture_session_context(SimpleNamespace(GetFirstDocument=model))
    assert result["active_document"] is None
    assert len(result["documents"]) == 1
    assert result["documents_complete"] is False
    assert any("active_document unavailable" in item for item in result["warnings"])
    assert any("repeated COM object" in item for item in result["warnings"])


def test_session_malformed_document_list_is_explicitly_unavailable():
    result = capture_session_context(SimpleNamespace(ActiveDoc=None, GetDocuments=123))
    assert result["documents"] == []
    assert result["documents_complete"] is False
    assert any("expected SAFEARRAY" in item for item in result["warnings"])


@pytest.mark.parametrize("limit", [-1, 1.5, True])
def test_invalid_feature_limit_rejected(limit):
    with pytest.raises(ValueError, match="feature_limit"):
        capture_model_context(Model(), feature_limit=limit)


def test_lightweight_document_state_never_reads_features_or_geometry():
    model = Model()
    attempted = []
    def forbidden(name):
        def getter(*_args):
            attempted.append(name)
            raise AssertionError("Lightweight snapshot read " + name)
        return getter
    model.FirstFeature = forbidden("FirstFeature")
    model.GetBodies2 = forbidden("GetBodies2")
    model.GetPartBox = forbidden("GetPartBox")
    selected = SimpleNamespace(Name="SelectedHole")
    model.SelectionManager = Selection(((22, selected),))
    result = capture_document_state(model)
    assert result["document"]["path"] == model.path
    assert result["selection"]["objects"] == [{"index": 1, "type": 22, "name": "SelectedHole"}]
    assert result["scope"] == "document metadata and selection only"
    assert "features" not in result and "geometry" not in result
    assert result["warnings"] == []
    assert attempted == model.calls == model.mutations == []
    assert_json(result)


@pytest.mark.parametrize("enumeration", ["linked", "array"])
@pytest.mark.parametrize("count,complete", [(2, True), (3, True), (4, False)])
def test_session_inventory_limit_exact_boundary_without_large_fixtures(monkeypatch, enumeration, count, complete):
    monkeypatch.setattr(model_context, "_MAX_SESSION_DOCUMENTS", 3)
    models = [Model(f"Part{i}", f"C:/parts/part{i}.sldprt") for i in range(count)]
    if enumeration == "linked":
        for first, second in zip(models, models[1:]):
            first.next_document = second
        app = SimpleNamespace(ActiveDoc=models[0], GetFirstDocument=lambda: models[0])
    else:
        app = SimpleNamespace(ActiveDoc=models[0], GetDocuments=lambda: tuple(models))
    result = capture_session_context(app)
    assert len(result["documents"]) == min(3, count)
    assert result["documents_complete"] is complete
    assert all(model.calls == model.mutations == [] for model in models)
    if not complete:
        assert any("limit" in warning or "truncated" in warning for warning in result["warnings"])


def test_production_inventory_limit_covers_large_loaded_assembly():
    assert model_context._MAX_SESSION_DOCUMENTS >= 1121
