"""Create and audit real sketch dimensions/relations, never blanket Fix locks.

References (also checked against the installed SW interop type libraries):
https://help.solidworks.com/2024/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISketchManager~FullyDefineSketch.html
https://help.solidworks.com/2026/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swSketchFullyDefineRelationType_e.html
https://help.solidworks.com/2011/English/api/sldworksapi/Fully_Define_Underdefined_Sketch_Example_VB.htm
https://help.solidworks.com/2017/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~FullName.html

FullyDefineSketch's integer return has no documented success meaning. Only the
sketch constraint status and actual dimension/relation evidence are accepted.
The mutating helper must be called while the intended owned sketch is active;
the whole-model collector is read-only and also visits absorbed subfeatures.
"""
from __future__ import annotations

import math
from typing import Any


SW_FULLY_CONSTRAINED = 3
SW_DIMENSION_DRIVING = 2
SW_ALL_RELATIONS = 0
FULLY_DEFINE_RELATIONS = 1023  # ten documented relation bits; no Fixed bit
FIXED_RELATION_TYPES = frozenset({17, 70, 74})
CONSTRAINT_STATUS = {
    1: "unknown", 2: "under_defined", 3: "fully_defined", 4: "over_defined",
    5: "no_solution", 6: "invalid_solution", 7: "autosolve_off",
}
SKETCH_FEATURE_TYPES = frozenset({"ProfileFeature", "3DProfileFeature"})


def _member(obj: Any, name: str, *args: Any) -> Any:
    value = getattr(obj, name)
    # A COM property returning IDispatch can be callable; do not invoke its
    # default member when asking for ActiveSketch/RelationManager/etc.
    if callable(value) and (args or getattr(value, "_oleobj_", None) is None):
        return value(*args)
    return value


def _read(obj, name, warnings, *args, default=None):
    try:
        return _member(obj, name, *args)
    except Exception as exc:
        warnings.append(f"{name}: {type(exc).__name__}: {exc}")
        return default


def _integer(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value != int(value):
        return None
    return int(value)


def _same_object(left, right):
    if left is right:
        return True
    if left is None or right is None:
        return False
    left_ole, right_ole = getattr(left, "_oleobj_", None), getattr(right, "_oleobj_", None)
    if left_ole is None or right_ole is None:
        return False
    try:
        import pythoncom
        return left_ole.QueryInterface(pythoncom.IID_IUnknown) == right_ole.QueryInterface(pythoncom.IID_IUnknown)
    except Exception:
        return left_ole == right_ole


def _null_dispatch(manager):
    if getattr(manager, "_oleobj_", None) is None:
        return None  # fake backend; no COM imports in offline tests
    import pythoncom
    from win32com.client import VARIANT
    return VARIANT(pythoncom.VT_DISPATCH, None)


def _feature_tree(model, warnings, limit=2000):
    """Return (all unique features, complete), bounded against COM tree cycles."""
    features, seen, complete = [], {}, True
    try:
        first = _member(model, "FirstFeature")
    except Exception as exc:
        warnings.append(f"FirstFeature: {exc}")
        return [], False
    stack = [(first, False, None)]
    while stack:
        feature, is_subfeature, owner = stack.pop()
        chain_seen = set()
        while feature is not None:
            if len(features) >= limit:
                warnings.append("Feature traversal limit reached")
                return features, False
            try:
                name = str(_member(feature, "Name"))
                kind = str(_member(feature, "GetTypeName2"))
            except Exception as exc:
                warnings.append(f"Feature metadata unavailable: {exc}")
                complete = False
                name, kind = f"unknown_{id(feature)}", "unknown"
            key = (name, kind)
            if key in chain_seen:
                warnings.append(f"Feature traversal cycle at {name}")
                complete = False
                break
            chain_seen.add(key)
            if key not in seen:
                seen[key] = len(features)
                features.append((feature, name, kind, owner))
                try:
                    child = _member(feature, "GetFirstSubFeature")
                    if child is not None:
                        stack.append((child, True, {"name": name, "type": kind}))
                except Exception as exc:
                    warnings.append(f"{name}.GetFirstSubFeature: {exc}")
                    complete = False
            elif owner is not None and features[seen[key]][3] is None:
                # Some absorbed sketches also appear in the top-level timeline.
                # Retain the actual owning feature when reached through children.
                old = features[seen[key]]
                features[seen[key]] = (old[0], old[1], old[2], owner)
            try:
                feature = _member(feature, "GetNextSubFeature" if is_subfeature else "GetNextFeature")
            except Exception as exc:
                warnings.append(f"{name}.next feature: {exc}")
                complete = False
                break
    return features, complete


def _origin_datum(model, manager, warnings):
    """Resolve a real model-origin sketch point, or return typed-null datums.

    Mark 6 is horizontal (2) plus vertical (4), as in the official example.
    The installed Chinese SW uses 点1@原点; names are deliberately bounded.
    No point is created, moved or fixed by this lookup.
    """
    null = _null_dispatch(manager)
    evidence = {"status": "null", "name": None, "coordinates_m": None}
    try:
        extension = _member(model, "Extension")
        selections = _member(model, "SelectionManager")
    except Exception as exc:
        warnings.append(f"Origin datum unavailable; using null datum: {exc}")
        return null, evidence
    candidates = ["Point1@Origin", "点1@原点"]
    features, _ = _feature_tree(model, warnings)
    for _, name, kind, _ in features:
        if kind == "OriginProfileFeature":
            for point_name in ("Point1", "点1"):
                candidate = f"{point_name}@{name}"
                if candidate not in candidates:
                    candidates.append(candidate)
    # An ordinary part has one origin. Bound unusual/invalid feature trees too.
    for candidate in candidates[:8]:
        try:
            model.ClearSelection2(True)
            selected = _member(extension, "SelectByID2", candidate, "EXTSKETCHPOINT",
                               0, 0, 0, False, 6, null, 0)
            if not selected:
                continue
            point = _member(selections, "GetSelectedObject6", 1, -1)
            coordinates = [_member(point, axis) for axis in ("X", "Y", "Z")]
            if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                       and math.isfinite(value) and abs(value) <= 1e-12 for value in coordinates):
                warnings.append(f"Rejected non-origin datum {candidate}: {coordinates!r}")
                continue
            evidence.update(status="model_origin", name=candidate,
                            coordinates_m=[float(value) for value in coordinates])
            return point, evidence
        except Exception as exc:
            warnings.append(f"Origin datum {candidate}: {type(exc).__name__}: {exc}")
    # Failed selection must not supply an accidental datum through mark 6.
    model.ClearSelection2(True)
    warnings.append("Model origin was not resolved; using null datum and verifying actual constraint status")
    return null, evidence


def _dimensions(feature, warnings, limit=1000):
    result, seen, excluded = [], set(), []
    if feature is None:
        warnings.append("Sketch feature unavailable; dimensions cannot be audited")
        return result, False, excluded
    try:
        feature_name = str(_member(feature, "Name"))
        display = _member(feature, "GetFirstDisplayDimension")
    except Exception as exc:
        warnings.append(f"GetFirstDisplayDimension: {exc}")
        return result, False, excluded
    complete = True
    visited = 0
    while display is not None:
        if visited >= limit:
            warnings.append("Dimension traversal limit reached")
            return result, False, excluded
        visited += 1
        try:
            dimension = _member(display, "GetDimension2", 0)
            if dimension is None:
                raise RuntimeError("display dimension has no model dimension")
            name = str(_member(dimension, "FullName"))
            if name in seen:
                warnings.append(f"Dimension traversal cycle at {name}")
                return result, False, excluded
            seen.add(name)
            # SW display-dimension iteration can include a preceding plane or
            # another feature. FullName is dimension@feature[@document].
            parts = name.split("@")
            if len(parts) < 2 or not parts[0] or not parts[1]:
                warnings.append(f"Dimension ownership unavailable: {name!r}")
                complete = False
            elif parts[1] != feature_name:
                excluded.append(name)
            else:
                driven = _integer(_read(dimension, "DrivenState", warnings))
                raw_value = _read(dimension, "SystemValue", warnings)
                system_value = (float(raw_value) if isinstance(raw_value, (int, float))
                                and not isinstance(raw_value, bool) and math.isfinite(raw_value) else None)
                result.append({"name": name, "driven_state": driven,
                               "driving": driven == SW_DIMENSION_DRIVING, "system_value": system_value})
                if driven not in (1, 2) or system_value is None:
                    complete = False
        except Exception as exc:
            warnings.append(f"Dimension evidence: {exc}")
            complete = False
        try:
            display = _member(feature, "GetNextDisplayDimension", display)
        except Exception as exc:
            warnings.append(f"GetNextDisplayDimension: {exc}")
            return result, False, excluded
    return result, complete, excluded


def _relations(sketch, warnings):
    try:
        manager = _member(sketch, "RelationManager")
        values = _member(manager, "GetRelations", SW_ALL_RELATIONS)
        values = [] if values is None else list(values)
    except Exception as exc:
        warnings.append(f"Sketch relations unavailable: {exc}")
        return [], False
    result, complete = [], True
    for relation in values:
        if relation is None:
            warnings.append("Null sketch relation in returned array")
            complete = False
            continue
        kind = _integer(_read(relation, "GetRelationType", warnings))
        result.append({"type": kind, "fixed": kind in FIXED_RELATION_TYPES})
        if kind is None:
            complete = False
    return result, complete


def _sketch_evidence(sketch, feature, name, warnings, owner=None):
    status = _integer(_read(sketch, "GetConstrainedStatus", warnings))
    if status not in CONSTRAINT_STATUS:
        warnings.append(f"Unknown or unavailable constrained status: {status!r}")
        status = None
    dimensions, dimensions_complete, excluded_dimensions = _dimensions(feature, warnings)
    relations, relations_complete = _relations(sketch, warnings)
    fixed_count = sum(relation["fixed"] for relation in relations)
    driving_count = sum(dimension["driving"] for dimension in dimensions)
    try:
        segments = _member(sketch, "GetSketchSegments")
        segment_count = 0 if segments is None else len(segments)
    except Exception:
        segment_count = None
    # SolidWorks itself generates a Hole Wizard section sketch with an internal
    # anchored point plus driving diameter/depth dimensions. It is distinct from
    # the point-only position sketch and must not be mistaken for blanket Fix.
    native_controlled = (owner is not None and owner.get("type") == "HoleWzd"
                         and status == SW_FULLY_CONSTRAINED and dimensions_complete
                         and driving_count >= 2 and relations_complete and fixed_count == 1
                         and all(r["type"] == 17 for r in relations if r["fixed"])
                         and segment_count is not None and segment_count >= 3)
    fully_defined = (status == SW_FULLY_CONSTRAINED and relations_complete
                     and (fixed_count == 0 or native_controlled))
    return {"name": name, "constraint_status": status,
            "constraint_status_name": CONSTRAINT_STATUS.get(status, "unavailable"),
            "native_fully_defined": status == SW_FULLY_CONSTRAINED,
            "fully_defined": fully_defined,
            "owner_feature": owner, "segment_count": segment_count,
            "native_feature_controlled": native_controlled,
            "dimensions": dimensions, "dimensions_complete": dimensions_complete,
            "excluded_dimension_names": excluded_dimensions,
            "dimension_count": len(dimensions), "driving_dimension_count": driving_count,
            "relations": relations, "relations_complete": relations_complete,
            "fixed_relation_count": fixed_count,
            "parametric_evidence": fully_defined and dimensions_complete and driving_count > 0}


def fully_define_active_sketch(model, *, relations_mask=FULLY_DEFINE_RELATIONS,
                               require_driving_dimensions=True):
    """Dimension/constrain the active 2D sketch and verify it before sketch exit.

    Does not enter/exit a sketch, save, or fix entities. The caller owns the
    document and is responsible for checking intended dimensions/geometry after
    automatic constraint inference. Integer API return is recorded, not trusted.
    When available, the real model origin supplies both baseline-dimension
    datums. Missing localized origin selection falls back to null datums and
    still requires the solver's real fully-defined state.
    ``fully_defined`` requires SW status=3, known absence of Fixed relations and,
    by default, real driving dimensions. For a deliberately dimensionless sketch
    constrained to external geometry, callers can explicitly opt out of the last
    requirement; the evidence still distinguishes that case.
    """
    if type(relations_mask) is not int or relations_mask < 0 or relations_mask & ~FULLY_DEFINE_RELATIONS:
        raise ValueError("relations_mask must contain only documented FullyDefineSketch relation bits")
    warnings = []
    result = {"before_status": None, "after_status": None, "api_return": None,
              "fully_defined": False, "dimensions": [], "parametric_evidence": False,
              "status": "blocked", "warnings": warnings, "method": "FullyDefineSketch_relations_and_dimensions"}
    manager = _read(model, "SketchManager", warnings)
    sketch = _read(manager, "ActiveSketch", warnings) if manager is not None else None
    if sketch is None:
        result["reason"] = "No active sketch; no model operation performed"
        return result
    before = _integer(_read(sketch, "GetConstrainedStatus", warnings))
    result["before_status"] = before
    if before not in (2, 3):
        result["reason"] = "Sketch status is unavailable, over-defined or unsolved; no automatic repair attempted"
        return result
    try:
        is_3d = _member(sketch, "Is3D")
    except Exception:
        is_3d = None
    if is_3d is not False:
        result["reason"] = "Automatic full definition requires a confirmed 2D sketch"
        return result
    if before != SW_FULLY_CONSTRAINED:
        try:
            model.ClearSelection2(True)
            datum, datum_evidence = _origin_datum(model, manager, warnings)
            result["datum"] = datum_evidence
            api_return = _member(manager, "FullyDefineSketch", True, True, relations_mask,
                                 True, 1, datum, 1, datum, 0, 0)
            result["api_return"] = api_return if isinstance(api_return, (int, float, bool, str)) or api_return is None else repr(api_return)
        except Exception as exc:
            result["reason"] = f"FullyDefineSketch failed: {type(exc).__name__}: {exc}"
            result["after_status"] = _integer(_read(sketch, "GetConstrainedStatus", warnings))
            return result
    features, complete = _feature_tree(model, warnings)
    active_feature, name, owner = None, None, None
    for feature, feature_name, kind, feature_owner in features:
        if kind in SKETCH_FEATURE_TYPES:
            specific = _read(feature, "GetSpecificFeature2", warnings)
            if _same_object(specific, sketch):
                active_feature, name, owner = feature, feature_name, feature_owner
                break
    evidence = _sketch_evidence(sketch, active_feature, name, warnings, owner)
    result.update(evidence)
    result["fully_defined"] = (evidence["fully_defined"] and evidence["dimensions_complete"]
                               and (not require_driving_dimensions or evidence["driving_dimension_count"] > 0))
    result["after_status"] = evidence["constraint_status"]
    result["feature_traversal_complete"] = complete
    # Actual status and no Fix relations are necessary, but missing dimensions
    # must still be visible as a review limitation, never fabricated as driving.
    result["status"] = "pass" if result["fully_defined"] else "review_required"
    if not result["fully_defined"]:
        result["status"] = "blocked"
        result["reason"] = "Sketch lacks complete full-constraint, non-Fix or driving-dimension evidence"
    return result


def collect_sketch_constraint_status(model, *, feature_limit=2000):
    """Read every ordinary/3D sketch including absorbed Hole Wizard subfeatures.

    No activation, selection, sketch editing or rebuild is performed. A limited
    or failed traversal and unknown constraint/relationship data cannot pass.
    Generated Hole Wizard profile sketches may be fully defined by relations to
    their parent; their dimensions are reported, not invented or forced driving.
    """
    warnings = []
    features, complete = _feature_tree(model, warnings, feature_limit)
    sketches = []
    for feature, name, kind, owner in features:
        if kind not in SKETCH_FEATURE_TYPES:
            continue
        local_warnings = []
        sketch = _read(feature, "GetSpecificFeature2", local_warnings)
        if sketch is None:
            sketches.append({"name": name, "fully_defined": False, "constraint_status": None,
                             "warnings": local_warnings, "feature_type": kind})
            complete = False
            continue
        evidence = _sketch_evidence(sketch, feature, name, local_warnings, owner)
        evidence.update(feature_type=kind, warnings=local_warnings)
        sketches.append(evidence)
    all_defined = complete and bool(sketches) and all(
        item["fully_defined"] and item.get("dimensions_complete") is True for item in sketches)
    all_parametric = complete and bool(sketches) and all(item.get("parametric_evidence") is True for item in sketches)
    return {"all_fully_defined": all_defined, "status": "pass" if all_defined else "blocked",
            "all_parametric": all_parametric,
            "complete": complete, "sketches": sketches, "sketch_count": len(sketches),
            "warnings": warnings, "scope": "all ProfileFeature/3DProfileFeature including absorbed subfeatures"}
