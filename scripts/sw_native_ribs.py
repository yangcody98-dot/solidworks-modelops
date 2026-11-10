"""Native planar ribs and measured feedback; no application/session ownership.

The caller supplies a task-owned part and protects the original documents, as in
sw_closed_loop_native.NativePartBackend. This module never connects to CAD,
opens/saves/closes documents, changes preferences, deletes features, or retries.
Creation changes only the supplied model. read_native_rib is read-only.

SOLIDWORKS 2025 SP2.0: InsertRib has TEN arguments and returns void. A separate
probe and an L-bracket demonstrated a symmetric 8 mm rib parallel to a fully
defined, open 2D straight-line sketch. Other rib modes are not validated here.
"""
from __future__ import annotations

import math

try:
    from .sw_model_context import capture_model_context
    from .sw_sketch_constraints import collect_sketch_constraint_status
except ImportError:
    from sw_model_context import capture_model_context
    from sw_sketch_constraints import collect_sketch_constraint_status


DOCUMENTATION = {
    "insert_rib": "https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeatureManager~InsertRib.html",
    "rib_data": "https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IRibFeatureData2.html",
}


def _member(obj, name, *args):
    value = getattr(obj, name)
    if args or (callable(value) and not hasattr(value, "_oleobj_")):
        return value(*args)
    return value


def _positive(value, label):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f"{label} must be a positive finite number")
    return float(value)


def _bool(value, label):
    if not isinstance(value, (bool, int)) or value not in (False, True, -1):
        raise RuntimeError(f"{label} is not an available boolean")
    return bool(value)


def _name(name, *, optional=False):
    if optional and name is None:
        return
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be nonempty")


def read_native_rib(feature, *, expected_thickness_mm=None, expected_two_sided=True):
    """Read and validate a native Rib without rebuilding or changing selections.

    Only parallel-to-sketch, undrafted, unflipped material is accepted. The
    two-sided default is the demonstrated mode. False supports the legacy
    low-level wrapper's actual Is2Sided argument, without claiming live coverage.
    """
    if expected_thickness_mm is not None:
        expected_thickness_mm = _positive(expected_thickness_mm, "expected_thickness_mm")
    if not isinstance(expected_two_sided, bool):
        raise ValueError("expected_two_sided must be a boolean")
    if feature is None or _member(feature, "GetTypeName2") != "Rib":
        raise RuntimeError("Created feature is not a native Rib")
    data = _member(feature, "GetDefinition")
    if data is None:
        raise RuntimeError("Native Rib definition is unavailable")
    direction = _member(data, "ExtrusionDirection")
    if isinstance(direction, bool) or not isinstance(direction, int):
        raise RuntimeError("Native Rib extrusion direction is unavailable")
    thickness = _positive(_member(data, "Thickness"), "Rib.Thickness") * 1000
    if not math.isfinite(thickness):
        raise RuntimeError("Native Rib thickness conversion overflow")
    angle = _member(data, "DraftAngle")
    if (isinstance(angle, bool) or not isinstance(angle, (int, float))
            or not math.isfinite(angle)):
        raise RuntimeError("Native Rib draft angle is unavailable")
    result = {
        "feature_type": "Rib", "thickness_mm": thickness,
        "is_two_sided": _bool(_member(data, "IsTwoSided"), "Rib.IsTwoSided"),
        "extrusion_direction": direction,
        "flip_side": _bool(_member(data, "FlipSide"), "Rib.FlipSide"),
        "enable_draft": _bool(_member(data, "EnableDraft"), "Rib.EnableDraft"),
        "draft_angle": float(angle),
    }
    if (result["is_two_sided"] != expected_two_sided or direction != 0
            or result["flip_side"] or result["enable_draft"]
            or abs(result["draft_angle"]) > 1e-12):
        raise RuntimeError(f"Native Rib mode mismatch: {result}")
    if (expected_thickness_mm is not None
            and abs(thickness - expected_thickness_mm) > 1e-6):
        raise RuntimeError(f"Native Rib thickness mismatch: {thickness} != {expected_thickness_mm}")
    return result


def _valid_context(context, *, solid=False):
    if context.get("features_complete") is not True:
        raise RuntimeError("Feature enumeration is incomplete")
    if any(f.get("error_code") != 0 for f in context["features"]):
        raise RuntimeError("Model contains feature errors or unavailable error codes")
    if solid:
        geometry = context.get("geometry", {})
        if geometry.get("status") != "available" or geometry.get("body_count") != 1:
            raise RuntimeError("Native rib requires exactly one measurable solid")
        _positive(geometry.get("volume_mm3"), "solid volume")


def _select_sketch(model, sketch_name):
    # Reuse the existing object/cache/Chinese-name selection support. Importing
    # this module alone does not initialize COM dependencies.
    try:
        from .sw_part import _ensure_sketch_selected
    except ImportError:
        from sw_part import _ensure_sketch_selected
    return _ensure_sketch_selected(model, sketch_name)


def insert_native_rib(model, sketch_name, thickness_m, *, is_two_sided=True, name=None):
    """Compatibility-level creation: metres in, real Feature out (API is void).

    Call create_native_rib for full sketch/geometry feedback. This lower-level
    entry retains sw_part.rib's existing signature semantics and selection
    support. A post-creation failure leaves the owned feature for inspection.
    """
    thickness_m = _positive(thickness_m, "thickness_m")
    if not math.isfinite(thickness_m * 1000):
        raise ValueError("thickness_m cannot be represented in mm")
    if not isinstance(is_two_sided, bool):
        raise ValueError("is_two_sided must be a boolean")
    _name(name, optional=True)
    if _member(model, "GetType") != 1:
        raise ValueError("Native ribs require a task-owned part document")
    if _member(_member(model, "SketchManager"), "ActiveSketch") is not None:
        raise ValueError("Exit the rib sketch before creating its feature")
    if name is not None and _member(model, "FeatureByName", name) is not None:
        raise ValueError(f"Feature name already exists: {name}")
    before = capture_model_context(model, include_geometry=False)
    _valid_context(before)
    previous = {f["name"] for f in before["features"] if f["type"] == "Rib"}
    _select_sketch(model, sketch_name)
    # Is2Sided, ReverseThicknessDir, Thickness, ReferenceEdgeIndex,
    # ReverseMaterialDir, IsDrafted, DraftOutward, DraftAngle,
    # IsNormToSketch, IsDraftedFromWall. Void: never use its return as a Feature.
    _member(_member(model, "FeatureManager"), "InsertRib",
            is_two_sided, False, thickness_m, 0, False, False, False, 0, False, False)
    if not _member(model, "ForceRebuild3", False):
        raise RuntimeError("Native Rib rebuild failed")
    after = capture_model_context(model, include_geometry=False)
    _valid_context(after)
    ribs = [f for f in after["features"] if f["type"] == "Rib"]
    added = [f for f in ribs if f["name"] not in previous]
    if len(added) != 1 or len(ribs) != len(previous) + 1:
        raise RuntimeError("InsertRib must create exactly one new native Rib")
    feature = _member(model, "FeatureByName", added[0]["name"])
    read_native_rib(feature, expected_thickness_mm=thickness_m * 1000,
                    expected_two_sided=is_two_sided)
    if name is not None:
        feature.Name = name
        if _member(feature, "Name") != name:
            raise RuntimeError("Native Rib rename failed")
    return feature


def _audit_sketches(model):
    result = collect_sketch_constraint_status(model)
    if not all(result.get(key) is True for key in ("complete", "all_fully_defined", "all_parametric")):
        raise RuntimeError("All sketches, including absorbed sketches, must be parametrically fully defined")
    return result


def _input_sketch(model, sketch_name):
    # Resolve in the supplied part, rather than trusting an external object's
    # feature handle. A SketchSelectionRef can still supply its actual name.
    feature = _member(model, "FeatureByName", str(sketch_name))
    if feature is None or _member(feature, "GetTypeName2") != "ProfileFeature":
        raise ValueError("Provide the actual name/reference of a closed-edit 2D rib sketch")
    sketch = _member(feature, "GetSpecificFeature2")
    if _bool(_member(sketch, "Is3D"), "Sketch.Is3D"):
        raise ValueError("Only a 2D straight-line rib sketch has been validated")
    if _member(sketch, "GetConstrainedStatus") != 3:
        raise ValueError("Rib sketch is not fully defined")
    segments = list(_member(sketch, "GetSketchSegments") or [])
    if len(segments) != 1 or _member(segments[0], "GetType") != 0:
        raise ValueError("Validated rib sketch must contain one open straight line")
    if _bool(_member(segments[0], "ConstructionGeometry"), "Sketch.ConstructionGeometry"):
        raise ValueError("Construction lines cannot define a native rib")
    return str(_member(feature, "Name"))


def create_native_rib(model, sketch_name, thickness_mm, *, name="Native_Rib",
                      expected_added_volume_mm3=None, volume_tolerance_mm3=0.1):
    """Create the demonstrated symmetric rib and check real model feedback.

    Units are mm/mm3. Only ``feature`` is a COM object; other return fields are
    JSON evidence. If an expected material addition is known, pass its value
    (e.g. 0.5 * 40 * 50 * 8 = 8000 for the demonstrated L-bracket). Otherwise
    only positive addition is checked; no exact-volume claim is made.
    """
    thickness_mm = _positive(thickness_mm, "thickness_mm")
    tolerance = _positive(volume_tolerance_mm3, "volume_tolerance_mm3")
    if expected_added_volume_mm3 is not None:
        expected_added_volume_mm3 = _positive(expected_added_volume_mm3, "expected_added_volume_mm3")
    _name(name)
    if _member(model, "GetType") != 1:
        raise ValueError("Native ribs require a task-owned part document")
    if _member(_member(model, "SketchManager"), "ActiveSketch") is not None:
        raise ValueError("Exit the rib sketch before creating its feature")
    if _member(model, "FeatureByName", name) is not None:
        raise ValueError(f"Feature name already exists: {name}")
    input_name = _input_sketch(model, sketch_name)
    _audit_sketches(model)
    before = capture_model_context(model)
    _valid_context(before, solid=True)
    feature = insert_native_rib(model, input_name, thickness_mm / 1000, name=name)
    readback = read_native_rib(feature, expected_thickness_mm=thickness_mm)
    after = capture_model_context(model)
    _valid_context(after, solid=True)
    delta = after["geometry"]["volume_mm3"] - before["geometry"]["volume_mm3"]
    if delta <= 0:
        raise RuntimeError("Native Rib added no material")
    if expected_added_volume_mm3 is not None and abs(delta - expected_added_volume_mm3) > tolerance:
        raise RuntimeError(f"Native Rib volume mismatch: {delta} != {expected_added_volume_mm3}")
    sketches = _audit_sketches(model)
    if not any(s.get("name") == input_name and s.get("owner_feature", {}).get("type") == "Rib"
               and s.get("owner_feature", {}).get("name") == name for s in sketches["sketches"]):
        raise RuntimeError("Rib did not absorb the requested input sketch")
    return {"feature": feature, "readback": readback, "before": before, "after": after,
            "sketch_constraints": sketches,
            "checks": {"single_native_rib": True, "single_solid": True,
                       "feature_errors_zero": True, "all_sketches_fully_defined": True,
                       "all_sketches_parametric": True, "input_sketch_absorbed": True,
                       "added_volume_mm3": delta,
                       "expected_added_volume_mm3": expected_added_volume_mm3,
                       "expected_volume_checked": expected_added_volume_mm3 is not None,
                       "volume_tolerance_mm3": tolerance},
            "evidence": {"api": "IFeatureManager.InsertRib", "argument_count": 10,
                         "returns": "void", "documentation": DOCUMENTATION}}
