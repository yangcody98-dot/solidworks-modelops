"""Native planar Hole Wizard holes, with strict parameter/position readback.

The caller must supply its own task-owned part and perform session protection.
This module never attaches to SolidWorks, opens/saves/closes documents, changes
application preferences, or falls back to cut-extrude geometry. It changes the
supplied model's selection and creates exactly one native feature per call.
Position sketches are reported honestly; the caller can dimension any remaining
degrees of freedom and must recheck constraint status before delivery.

Signature/enums were checked against installed SOLIDWORKS 2025 Interop DLLs.
The ISO143 through-hole experiment returned no feature in two SOLIDWORKS 2025
trials despite its database size key being confirmed. It is blocked by default
and is not a validated delivery capability; counterbores use the separate,
successfully exercised native counterbore route.
"""
from __future__ import annotations

import math


DOCUMENTATION = {
    "hole_wizard": "https://help.solidworks.com/2021/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeatureManager~HoleWizard5.html",
    "valid_properties": "https://help.solidworks.com/2023/english/api/sldworksapi/Table_of_Wizard_Hole_Types_and_Valid_Properties.htm",
    "planar_positions": "https://help.solidworks.com/2016/English/solidworks/sldworks/c_Hole_Wizard_Overview.htm",
    "point_coordinates": "https://help.solidworks.com/2022/english/api/sldworksapi/create_holes_using_hole_wizard_and_sketch_points_example_vbnet.htm",
}

# swconst.dll: swWzdCounterBore=0, swStandardISO=8,
# swStandardISOSocketHeadCap=139, swEndCondThroughAll=1, swCounterBoreThru=14.
SW_STANDARD_ISO = 8
SW_ISO_SOCKET_HEAD_CAP = 139
SW_ISO_DRILL_SIZES = 143
POSITION_TOLERANCE_MM = 0.01


def _member(obj, name, *args):
    value = getattr(obj, name)
    if args or (callable(value) and not hasattr(value, "_oleobj_")):
        return value(*args)
    return value


def _number(value, label, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{label} must be positive")
    return float(value)


def _vector(value, label, count=3):
    if not isinstance(value, (list, tuple)) or len(value) != count:
        raise ValueError(f"{label} must contain {count} coordinates")
    return [_number(v, label) for v in value]


def _same_object(a, b):
    if a is b:
        return True
    if a is None or b is None:
        return False
    if hasattr(a, "_oleobj_") and hasattr(b, "_oleobj_"):
        import pythoncom
        return (a._oleobj_.QueryInterface(pythoncom.IID_IUnknown)
                == b._oleobj_.QueryInterface(pythoncom.IID_IUnknown))
    return False


def _entry_face(model, position_m):
    matches = []
    for body in _member(model, "GetBodies2", 0, False) or []:
        for face in _member(body, "GetFaces") or []:
            if not _member(_member(face, "GetSurface"), "IsPlane"):
                continue
            closest = _member(face, "GetClosestPointOn", *position_m)
            if closest is None or len(closest) < 3:
                raise RuntimeError("Cannot determine entry-face position")
            if math.dist(position_m, closest[:3]) <= POSITION_TOLERANCE_MM / 1000:
                normal = _vector(list(_member(face, "Normal")), "entry face normal")
                length = math.sqrt(sum(v * v for v in normal))
                if length <= 1e-12:
                    raise RuntimeError("Entry face has no usable planar normal")
                matches.append((face, [v / length for v in normal]))
    if len(matches) != 1:
        raise RuntimeError(f"Hole position must lie on exactly one planar face; found {len(matches)}")
    return matches[0]


def _select_entry(model, position_m, face, normal):
    _member(model, "ClearSelection2", True)
    start = [p + n * 0.005 for p, n in zip(position_m, normal)]
    direction = [-n for n in normal]
    # SelectByRay is the documented HoleWizard5 placement API. Face type=2, mark=0.
    if not _member(_member(model, "Extension"), "SelectByRay",
                   *start, *direction, 0.0001, 2, False, 0, 0):
        raise RuntimeError("Could not select planar Hole Wizard entry point")
    selection = _member(model, "SelectionManager")
    if (_member(selection, "GetSelectedObjectCount2", -1) != 1
            or _member(selection, "GetSelectedObjectType3", 1, 0) != 2):
        raise RuntimeError("Hole Wizard requires one selected planar face")
    selected = _member(selection, "GetSelectedObject6", 1, 0)
    if not _same_object(selected, face):
        raise RuntimeError("Ray selected a different face; no hole created")
    pick = _member(selection, "GetSelectionPoint2", 1, 0)
    if pick is None or len(pick) != 3:
        raise RuntimeError("Selected entry point is unavailable")
    projected = _member(face, "GetClosestPointOn", *pick)
    if projected is None or math.dist(position_m, projected[:3]) > POSITION_TOLERANCE_MM / 1000:
        raise RuntimeError("Selected entry point differs from requested hole position")
    return [float(v) * 1000 for v in projected[:3]]


def _through_depth_argument(model, normal):
    """Supply a positive dimensional argument while EndCondition remains ThroughAll.

    The API's documented -1-ignore rule covers Value1..Value12, not the main
    Depth argument. Project the measured model bounds instead of guessing one.
    """
    try:
        box = _vector(list(_member(model, "GetPartBox", True)), "part bounds", 6)
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("Cannot measure a positive depth argument for native through-hole") from exc
    extent = sum(abs(n) * (box[i + 3] - box[i]) for i, n in enumerate(normal))
    if extent <= 0 or any(box[i + 3] < box[i] for i in range(3)):
        raise RuntimeError("Native through-hole model bounds have no positive thickness")
    return extent


def _position_readback(data, requested_mm):
    points = list(_member(data, "GetSketchPoints") or [])
    if _member(data, "GetSketchPointCount") != 1 or len(points) != 1:
        raise RuntimeError("Native hole must contain exactly one placement point")
    point = points[0]
    sketch = _member(point, "GetSketch")
    if bool(_member(sketch, "Is3D")):
        raise RuntimeError("Hole Wizard created a 3D position sketch; planar placement required")
    xyz = [_number(_member(point, axis), f"point.{axis}") for axis in ("X", "Y", "Z")]
    try:
        inverse = _member(_member(sketch, "ModelToSketchTransform"), "Inverse")
        transform = _vector(list(_member(inverse, "ArrayData")), "sketch-to-model transform", 16)
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError("Native placement sketch-to-model transform is unavailable") from exc
    # SOLIDWORKS MathTransform: 0..8 row-major rotation, 9..11 translation, 12 scale.
    actual_mm = [1000 * (transform[12] * sum(xyz[j] * transform[j * 3 + i] for j in range(3))
                        + transform[9 + i]) for i in range(3)]
    if math.dist(actual_mm, requested_mm) > POSITION_TOLERANCE_MM:
        raise RuntimeError(f"Native hole position mismatch: expected {requested_mm}, actual {actual_mm}")
    return {"position_mm": actual_mm, "position_sketch_is_3d": False,
            "position_sketch_constraint_status": int(_member(sketch, "GetConstrainedStatus"))}


def _subsketches(feature):
    result = []
    child = _member(feature, "GetFirstSubFeature")
    for _ in range(20):
        if child is None:
            break
        kind = str(_member(child, "GetTypeName2"))
        if kind in {"ProfileFeature", "3DProfileFeature"}:
            sketch = _member(child, "GetSpecificFeature2")
            is_3d = bool(_member(sketch, "Is3D"))
            if is_3d:
                raise RuntimeError("Native Hole Wizard subsketch unexpectedly uses 3D geometry")
            status = int(_member(sketch, "GetConstrainedStatus"))
            result.append({"name": str(_member(child, "Name")), "type": kind,
                           "is_3d": False, "constraint_status": status, "fully_defined": status == 3})
        child = _member(child, "GetNextSubFeature")
    else:
        raise RuntimeError("Hole Wizard subfeature enumeration did not terminate")
    if not result:
        raise RuntimeError("Native Hole Wizard subsketch evidence is unavailable")
    return result


def create_native_counterbore(model, position_mm, hole_diameter_mm,
                              counterbore_diameter_mm, counterbore_depth_mm, *,
                              name, standard="ISO", size="M8"):
    """Create one native, through-all ISO socket-head counterbore on a planar face.

    Dimensions/positions use mm. Only ``feature`` in the result is a COM handle;
    all remaining fields are JSON data. A readback failure raises and does not
    retry, delete, or replace the partially created feature.
    """
    position = _vector(position_mm, "position_mm")
    diameter = _number(hole_diameter_mm, "hole_diameter_mm", positive=True)
    cb_diameter = _number(counterbore_diameter_mm, "counterbore_diameter_mm", positive=True)
    cb_depth = _number(counterbore_depth_mm, "counterbore_depth_mm", positive=True)
    if cb_diameter <= diameter:
        raise ValueError("counterbore diameter must exceed through-hole diameter")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be nonempty")
    if standard not in ("ISO", SW_STANDARD_ISO) or not isinstance(size, str) or not size.strip():
        raise ValueError("Only the verified ISO socket-head family is supported; provide a valid size")
    if _member(model, "GetType") != 1:
        raise ValueError("Native counterbores require a task-owned part document")
    if _member(model, "FeatureByName", name) is not None:
        raise ValueError(f"Feature name already exists: {name}")
    position_m = [v / 1000 for v in position]
    face, normal = _entry_face(model, position_m)
    depth_argument = _through_depth_argument(model, normal)
    selected_mm = _select_entry(model, position_m, face, normal)
    # Official 27-argument signature; EndCondition, not Depth, specifies ThroughAll.
    # Value1..4: counterbore diameter, depth, zero head clearance, normal fit.
    args = [0, SW_STANDARD_ISO, SW_ISO_SOCKET_HEAD_CAP, size, 1,
            diameter / 1000, depth_argument, -1.0,
            cb_diameter / 1000, cb_depth / 1000, 0.0, 1.0] + [-1.0] * 8 + [
            "", False, True, True, False, False, False]
    feature = _member(_member(model, "FeatureManager"), "HoleWizard5", *args)
    if feature is None or feature is False:
        raise RuntimeError("HoleWizard5 did not create a native feature")
    if _member(feature, "GetTypeName2") != "HoleWzd":
        raise RuntimeError("Created feature is not native HoleWzd")
    data = _member(feature, "GetDefinition")
    readback = {"feature_type": "HoleWzd", "wizard_type": int(_member(data, "Type")),
                "end_condition": int(_member(data, "EndCondition")),
                "standard": int(_member(data, "Standard2")),
                "fastener_type": int(_member(data, "FastenerType2")),
                "size": str(_member(data, "FastenerSize")),
                "hole_diameter_mm": float(_member(data, "ThruHoleDiameter")) * 1000,
                "counterbore_diameter_mm": float(_member(data, "CounterBoreDiameter")) * 1000,
                "counterbore_depth_mm": float(_member(data, "CounterBoreDepth")) * 1000}
    if (readback["wizard_type"] != 14 or readback["end_condition"] != 1
            or readback["standard"] != 8 or readback["fastener_type"] != 139
            or readback["size"] != size):
        raise RuntimeError(f"Native Hole Wizard type/standard/end condition mismatch: {readback}")
    for key, expected in (("hole_diameter_mm", diameter), ("counterbore_diameter_mm", cb_diameter),
                          ("counterbore_depth_mm", cb_depth)):
        if not math.isfinite(readback[key]) or abs(readback[key] - expected) > 1e-6:
            raise RuntimeError(f"Native Hole Wizard {key} mismatch: {readback[key]} != {expected}")
    readback.update(_position_readback(data, position))
    subsketches = _subsketches(feature)
    feature.Name = name
    actual_name = str(_member(feature, "Name"))
    if actual_name != name:
        raise RuntimeError(f"Native feature rename failed: {actual_name}")
    return {"feature": feature, "readback": readback, "feature_name": actual_name,
            "subsketches": subsketches,
            "sketch_constraints_complete": all(item["fully_defined"] for item in subsketches),
            "evidence": {"entry_point_mm": selected_mm, "api": "IFeatureManager.HoleWizard5",
                         "argument_count": len(args), "arguments": args, "documentation": DOCUMENTATION}}


def create_native_through_hole(model, position_mm, diameter_mm, *, name, size=None,
                               experimental=False):
    """Experimental ISO drill-size through-hole probe; disabled by default.

    The installed Toolbox database confirms ISO143 diameter 6's size key is
    'Ø6.0'. Other sizes must be provided explicitly by a caller who has checked
    their database; no speculative catalogue-name conversion is performed.
    SOLIDWORKS 2025 returned None in two real creation trials, including with a
    positive Depth argument. This is not a validated delivery capability.
    Only an explicit experimental=True enables developer investigation on a
    task-owned part; the default raises before reading or changing any CAD state.
    """
    if experimental is not True:
        raise NotImplementedError(
            "ISO143 native through-hole creation is not validated: SOLIDWORKS 2025 "
            "returned no feature in two trials. Only experimental=True permits a developer probe.")
    position = _vector(position_mm, "position_mm")
    diameter = _number(diameter_mm, "diameter_mm", positive=True)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("name must be nonempty")
    if size is None:
        if abs(diameter - 6.0) > 1e-9:
            raise ValueError("Only Ø6.0 has a verified default drill size; supply a database-verified size")
        size = "\u00d86.0"
    if not isinstance(size, str) or not size.strip():
        raise ValueError("size must be a nonempty verified ISO drill-size key")
    if _member(model, "GetType") != 1:
        raise ValueError("Native holes require a task-owned part document")
    if _member(model, "FeatureByName", name) is not None:
        raise ValueError(f"Feature name already exists: {name}")
    position_m = [v / 1000 for v in position]
    face, normal = _entry_face(model, position_m)
    depth_argument = _through_depth_argument(model, normal)
    selected_mm = _select_entry(model, position_m, face, normal)
    args = [2, SW_STANDARD_ISO, SW_ISO_DRILL_SIZES, size, 1,
            diameter / 1000, depth_argument, -1.0] + [-1.0] * 12 + [
            "", False, True, True, False, False, False]
    feature = _member(_member(model, "FeatureManager"), "HoleWizard5", *args)
    if feature is None or feature is False:
        raise RuntimeError("HoleWizard5 did not create a native feature")
    if _member(feature, "GetTypeName2") != "HoleWzd":
        raise RuntimeError("Created feature is not native HoleWzd")
    data = _member(feature, "GetDefinition")
    readback = {"feature_type": "HoleWzd", "wizard_type": int(_member(data, "Type")),
                "end_condition": int(_member(data, "EndCondition")),
                "standard": int(_member(data, "Standard2")),
                "fastener_type": int(_member(data, "FastenerType2")),
                "size": str(_member(data, "FastenerSize")),
                "hole_diameter_mm": float(_member(data, "ThruHoleDiameter")) * 1000}
    if (readback["wizard_type"] != 25 or readback["end_condition"] != 1
            or readback["standard"] != 8 or readback["fastener_type"] != 143
            or readback["size"] != size):
        raise RuntimeError(f"Native through-hole type/standard/end condition mismatch: {readback}")
    if not math.isfinite(readback["hole_diameter_mm"]) or abs(readback["hole_diameter_mm"] - diameter) > 1e-6:
        raise RuntimeError("Native through-hole diameter mismatch")
    readback.update(_position_readback(data, position))
    subsketches = _subsketches(feature)
    feature.Name = name
    actual_name = str(_member(feature, "Name"))
    if actual_name != name:
        raise RuntimeError(f"Native feature rename failed: {actual_name}")
    return {"feature": feature, "readback": readback, "feature_name": actual_name,
            "subsketches": subsketches,
            "sketch_constraints_complete": all(item["fully_defined"] for item in subsketches),
            "evidence": {"entry_point_mm": selected_mm, "api": "IFeatureManager.HoleWizard5",
                         "argument_count": len(args), "arguments": args, "documentation": DOCUMENTATION,
                         "experimental": True, "validated_delivery_capability": False,
                         "default_size_source": "Installed swbrowser.sldedb ISO_DATA_HW_DrillSizes: SIZE=Ø6.0, Diameter=6, enabled=1, key=93"}}


def _transform_point(point, transform):
    """Apply the documented SW row-vector rotation/scale/translation convention."""
    point = _vector(point, "point")
    transform = _vector(transform, "MathTransform.ArrayData", 16)
    if transform[12] <= 0:
        raise ValueError("Transform scale must be positive")
    return [transform[12] * sum(point[j] * transform[j * 3 + i] for j in range(3))
            + transform[9 + i] for i in range(3)]


def _positions_readback(data, requested_positions):
    points = list(_member(data, "GetSketchPoints") or [])
    if int(_member(data, "GetSketchPointCount")) != len(requested_positions) or len(points) != len(requested_positions):
        raise RuntimeError("Hole Wizard placement point count differs from the requested hole count")
    actual = []
    position_sketch = None
    for point in points:
        sketch = _member(point, "GetSketch")
        if _member(sketch, "Is3D") is not False:
            raise RuntimeError("Grouped holes require one 2D positioning sketch")
        if position_sketch is None:
            position_sketch = sketch
        elif not _same_object(position_sketch, sketch):
            raise RuntimeError("Placement points belong to different sketches")
        xyz = [_number(_member(point, axis), f"point.{axis}") for axis in ("X", "Y", "Z")]
        inverse = _member(_member(sketch, "ModelToSketchTransform"), "Inverse")
        matrix = list(_member(inverse, "ArrayData"))
        actual.append([v * 1000 for v in _transform_point(xyz, matrix)])
    for index, point in enumerate(actual):
        if any(math.dist(point, other) <= POSITION_TOLERANCE_MM for other in actual[:index]):
            raise RuntimeError("Native Hole Wizard contains coincident placement points")
    unmatched = set(range(len(actual)))
    matches = []
    for requested in requested_positions:
        candidates = [(math.dist(requested, actual[index]), index) for index in unmatched]
        distance, index = min(candidates)
        if distance > POSITION_TOLERANCE_MM:
            raise RuntimeError(f"Grouped hole position mismatch: expected {requested}, actual {actual[index]}")
        unmatched.remove(index)
        matches.append(actual[index])
    status = int(_member(position_sketch, "GetConstrainedStatus"))
    if status != 3:
        raise RuntimeError("Grouped hole positioning sketch is not fully defined")
    return {"hole_count": len(matches), "positions_mm": matches,
            "position_sketch_is_3d": False, "position_sketch_constraint_status": status}


def create_native_counterbore_group(model, positions_mm, hole_diameter_mm,
                                    counterbore_diameter_mm, counterbore_depth_mm, *,
                                    name, standard="ISO", size="M8"):
    """Create ONE HoleWzd feature with multiple fully defined placement points.

    Model-space input coordinates use mm. All entries must lie on the same
    planar face. This adds points to Hole Wizard's position sketch; it does not
    create separate hole features or a linear-pattern feature. Caller supplies
    and protects its task-owned document, as with the single-hole interface.
    """
    if not isinstance(positions_mm, (list, tuple)) or not positions_mm:
        raise ValueError("positions_mm must contain at least one hole position")
    positions = [_vector(p, f"positions_mm[{i}]") for i, p in enumerate(positions_mm)]
    for i, point in enumerate(positions):
        if any(math.dist(point, other) <= POSITION_TOLERANCE_MM for other in positions[:i]):
            raise ValueError("Duplicate placement positions are not allowed")
    # Establish a common supporting face before the first geometry mutation.
    faces = [_entry_face(model, [v / 1000 for v in p])[0] for p in positions]
    if any(not _same_object(faces[0], face) for face in faces[1:]):
        raise ValueError("All counterbores in one feature must share the same planar face")
    result = create_native_counterbore(model, positions[0], hole_diameter_mm,
        counterbore_diameter_mm, counterbore_depth_mm, name=name, standard=standard, size=size)
    feature = result["feature"]
    data = _member(feature, "GetDefinition")
    first_point = list(_member(data, "GetSketchPoints") or [])[0]
    position_sketch = _member(first_point, "GetSketch")
    position_feature = None
    child = _member(feature, "GetFirstSubFeature")
    for _ in range(20):
        if child is None:
            break
        if _member(child, "GetTypeName2") == "ProfileFeature":
            specific = _member(child, "GetSpecificFeature2")
            if _same_object(specific, position_sketch):
                position_feature = child
                break
        child = _member(child, "GetNextSubFeature")
    if position_feature is None:
        raise RuntimeError("Cannot identify the native Hole Wizard position sketch")
    _member(model, "ClearSelection2", True)
    if not _member(position_feature, "Select2", False, 0):
        raise RuntimeError("Cannot select Hole Wizard position sketch")
    _member(model, "EditSketch")
    manager = _member(model, "SketchManager")
    active = _member(manager, "ActiveSketch")
    if not _same_object(active, position_sketch):
        raise RuntimeError("Wrong sketch became active; no additional points inserted")
    try:
        matrix = list(_member(_member(position_sketch, "ModelToSketchTransform"), "ArrayData"))
        for point in positions[1:]:
            local = _transform_point([v / 1000 for v in point], matrix)
            if abs(local[2]) > POSITION_TOLERANCE_MM / 1000:
                raise RuntimeError("Placement point lies outside the native positioning plane")
            added = _member(manager, "CreatePoint", local[0], local[1], 0.0)
            if added is None:
                raise RuntimeError("Failed to add Hole Wizard positioning point")
        try:
            from .sw_sketch_constraints import fully_define_active_sketch
        except ImportError:
            from sw_sketch_constraints import fully_define_active_sketch
        constraints = fully_define_active_sketch(model)
        if not constraints.get("fully_defined") or not constraints.get("parametric_evidence"):
            raise RuntimeError(f"Grouped hole sketch requires dimensions/relations: {constraints}")
    finally:
        if _same_object(_member(manager, "ActiveSketch"), position_sketch):
            _member(manager, "InsertSketch", True)
    if not _member(model, "ForceRebuild3", False):
        raise RuntimeError("Grouped Hole Wizard feature failed to rebuild")
    data = _member(feature, "GetDefinition")
    result["readback"].pop("position_mm", None)
    result["readback"].update(_positions_readback(data, positions))
    result["subsketches"] = _subsketches(feature)
    result["sketch_constraints_complete"] = all(s["fully_defined"] for s in result["subsketches"])
    if not result["sketch_constraints_complete"]:
        raise RuntimeError("Native grouped hole subsketches are not fully defined")
    result["position_sketch_constraints"] = constraints
    result["evidence"]["method"] = "one HoleWizard5 call; multiple points in its native positioning sketch"
    return result
