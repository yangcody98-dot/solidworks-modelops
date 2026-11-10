"""Validate a bounded CAD operation plan and adapt supported VibeCAD features.

This module has no COM imports and performs no CAD or filesystem mutations.
Plans are data, never executable Python/VBA. Unsupported legacy features cause a
preflight error, including features marked optional; they are not silently lost.
"""
from __future__ import annotations

import copy
import math
import re
from typing import Any


SUPPORTED_OPERATIONS = frozenset(
    {"sketch_rectangle", "sketch_circles", "extrude_boss", "extrude_cut"}
)
CONTEXT_PATHS = frozenset(
    {"geometry.bbox_size_mm.0", "geometry.bbox_size_mm.1", "geometry.bbox_size_mm.2",
     "geometry.volume_mm3", "geometry.body_count"}
)
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,95}$")


class PlanValidationError(ValueError):
    """An actionable preflight failure; no operation has been executed."""

    def __init__(self, issues: list[dict[str, str]]):
        self.issues = issues
        super().__init__("; ".join(f"{i['path']}: {i['message']}" for i in issues))


def _fail(code: str, path: str, message: str) -> None:
    raise PlanValidationError([{"code": code, "path": path, "message": message}])


def _object(value: Any, path: str) -> dict:
    if not isinstance(value, dict):
        _fail("invalid_type", path, "must be a JSON object")
    return value


def _keys(value: dict, allowed: set[str], required: set[str], path: str) -> None:
    extra, missing = set(value) - allowed, required - set(value)
    if extra:
        _fail("unsupported_field", path, f"unsupported fields: {sorted(extra, key=str)}")
    if missing:
        _fail("missing_field", path, f"missing fields: {sorted(missing)}")


def _string(value: Any, path: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        _fail("invalid_string", path, "must be a nonempty string of at most 200 characters")
    if any(ord(c) < 32 for c in value):
        _fail("invalid_string", path, "control characters are not allowed")
    if identifier and not _ID.fullmatch(value):
        _fail("invalid_id", path, "use a letter followed by letters, digits, '_' or '-' (max 96)")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail("invalid_boolean", path, "must be true or false")
    return value


def _binding(value: dict, path: str) -> dict:
    sources = set(value) & {"from_context", "from_source"}
    if len(sources) != 1:
        _fail("invalid_binding", path, "exactly one of from_context/from_source is required")
    source = next(iter(sources))
    _keys(value, {source, "scale", "offset_mm"}, {source}, path)
    if not isinstance(value[source], str) or value[source] not in CONTEXT_PATHS:
        _fail("unsupported_binding", path, f"context path is not allowed: {value[source]!r}")
    result = copy.deepcopy(value)
    result["scale"] = _number(value.get("scale", 1), path + ".scale", allow_bindings=False)
    result["offset_mm"] = _number(value.get("offset_mm", 0), path + ".offset_mm", allow_bindings=False)
    return result


def _number(value: Any, path: str, *, positive: bool = False,
            nonnegative: bool = False, integer: bool = False,
            allow_bindings: bool = True) -> float | int | dict:
    if isinstance(value, dict) and allow_bindings:
        return _binding(value, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail("invalid_number", path, "must be a finite number" + ("; unresolved bindings are not allowed" if not allow_bindings else ""))
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or (positive and value <= 0) or (nonnegative and value < 0):
        _fail("invalid_number", path, "must be finite" + (" and positive" if positive else " and nonnegative" if nonnegative else ""))
    if integer and int(value) != value:
        _fail("invalid_integer", path, "must be an integer")
    return int(value) if integer else float(value)


def _vector(value: Any, path: str, size: int, *, positive: bool = False,
            allow_bindings: bool = True) -> list:
    if not isinstance(value, list) or len(value) != size:
        _fail("invalid_vector", path, f"must contain exactly {size} numbers")
    return [_number(v, f"{path}.{i}", positive=positive, allow_bindings=allow_bindings)
            for i, v in enumerate(value)]


def _json_data(value: Any, path: str) -> Any:
    """Reject opaque objects and nonfinite metadata; retain data without interpreting it."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, (int, float)):
        _number(value, path, allow_bindings=False)
        return value
    if isinstance(value, list):
        return [_json_data(item, f"{path}.{i}") for i, item in enumerate(value)]
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return {key: _json_data(item, f"{path}.{key}") for key, item in value.items()}
    _fail("invalid_json", path, "must be JSON-compatible data")


def _expect(value: Any, path: str, allow_bindings: bool) -> dict:
    value = _object(value, path)
    allowed = {"body_count", "bbox_size_mm", "bbox_tolerance_mm", "volume_mm3",
               "volume_tolerance_mm3", "feature_ok", "holes", "hole_tolerance_mm", "description"}
    _keys(value, allowed, set(), path)
    result = {}
    for key, item in value.items():
        item_path = f"{path}.{key}"
        if key == "description":
            result[key] = _string(item, item_path)
        elif key == "feature_ok":
            result[key] = _boolean(item, item_path)
            if not result[key]:
                _fail("invalid_expectation", item_path, "a successful plan must require feature_ok=true")
        elif key == "bbox_size_mm":
            result[key] = _vector(item, item_path, 3, positive=True, allow_bindings=allow_bindings)
        elif key == "holes":
            if not isinstance(item, list) or not item:
                _fail("invalid_holes", item_path, "must contain at least one expected hole")
            holes = []
            for index, hole in enumerate(item):
                hp = f"{item_path}.{index}"
                _object(hole, hp)
                _keys(hole, {"diameter_mm", "position_mm"}, {"diameter_mm", "position_mm"}, hp)
                holes.append({"diameter_mm": _number(hole["diameter_mm"], hp + ".diameter_mm", positive=True, allow_bindings=allow_bindings),
                              "position_mm": _vector(hole["position_mm"], hp + ".position_mm", 3, allow_bindings=allow_bindings)})
            result[key] = holes
        else:
            result[key] = _number(item, item_path, integer=key == "body_count", nonnegative=True, allow_bindings=allow_bindings)
    if "volume_tolerance_mm3" in result and "volume_mm3" not in result:
        _fail("invalid_expectation", path, "volume_tolerance_mm3 requires volume_mm3")
    if "bbox_tolerance_mm" in result and "bbox_size_mm" not in result:
        _fail("invalid_expectation", path, "bbox_tolerance_mm requires bbox_size_mm")
    if "hole_tolerance_mm" in result and "holes" not in result:
        _fail("invalid_expectation", path, "hole_tolerance_mm requires holes")
    return result


def validate_operation_plan(plan: dict, *, allow_bindings: bool = True, allow_prefix: bool = False) -> dict:
    """Return a normalized copy, or raise PlanValidationError before any CAD write.

    Set ``allow_bindings=False`` after resolving numeric values from actual model
    snapshots. Units are always mm and mm^3. Unknown operations/fields are errors.
    ``requirements`` is a list of final geometry expectation objects. Set
    ``allow_prefix=True`` only for checking an already-validated plan's executed
    prefix; this permits the initial sketch before any solid has been created.
    """
    plan = _object(plan, "plan")
    allowed = {"schema_version", "name", "operations", "requirements", "source_bindings", "assumptions", "metadata"}
    _keys(plan, allowed, {"schema_version", "name", "operations"}, "plan")
    if type(plan["schema_version"]) is not int or plan["schema_version"] != 1:
        _fail("unsupported_version", "plan.schema_version", "only schema_version=1 is supported")
    result = {"schema_version": 1, "name": _string(plan["name"], "plan.name"), "operations": [], "requirements": []}
    operations = plan["operations"]
    if not isinstance(operations, list) or not operations:
        _fail("invalid_operations", "plan.operations", "must contain at least one operation")
    ids: set[str] = set()
    sketches: set[str] = set()
    solid_seen = False
    for i, operation in enumerate(operations):
        path = f"plan.operations.{i}"
        operation = _object(operation, path)
        _keys(operation, {"id", "op", "params", "expect", "fallback_params"}, {"id", "op", "params"}, path)
        identifier = _string(operation["id"], path + ".id", identifier=True)
        if identifier in ids:
            _fail("duplicate_id", path + ".id", f"duplicate operation id: {identifier}")
        ids.add(identifier)
        op = operation["op"]
        if not isinstance(op, str) or op not in SUPPORTED_OPERATIONS:
            _fail("unsupported_operation", path + ".op", f"unsupported operation: {op!r}")
        params = _object(operation["params"], path + ".params")
        pp = path + ".params"
        normalized = {}
        if op in {"sketch_rectangle", "sketch_circles"}:
            if op == "sketch_rectangle":
                required = {"plane", "cx_mm", "cy_mm", "width_mm", "height_mm"}
                _keys(params, required, required, pp)
                for key in required - {"plane"}:
                    normalized[key] = _number(params[key], pp + "." + key, positive=key in {"width_mm", "height_mm"}, allow_bindings=allow_bindings)
            else:
                _keys(params, {"plane", "circles"}, {"plane", "circles"}, pp)
                circles = params["circles"]
                if not isinstance(circles, list) or not circles:
                    _fail("invalid_circles", pp + ".circles", "must contain at least one circle")
                normalized["circles"] = []
                for j, circle in enumerate(circles):
                    cp = f"{pp}.circles.{j}"
                    _object(circle, cp)
                    _keys(circle, {"x_mm", "y_mm", "radius_mm"}, {"x_mm", "y_mm", "radius_mm"}, cp)
                    normalized["circles"].append({key: _number(circle[key], cp + "." + key, positive=key == "radius_mm", allow_bindings=allow_bindings) for key in ("x_mm", "y_mm", "radius_mm")})
            normalized["plane"] = _string(params["plane"], pp + ".plane")
            sketches.add(identifier)
        else:
            allowed_params = {"sketch_id", "depth_mm"} | ({"through_all", "reverse"} if op == "extrude_cut" else set())
            _keys(params, allowed_params, {"sketch_id", "depth_mm"}, pp)
            sketch_id = _string(params["sketch_id"], pp + ".sketch_id", identifier=True)
            if sketch_id not in sketches:
                _fail("invalid_reference", pp + ".sketch_id", "must reference an earlier sketch operation")
            normalized = {"sketch_id": sketch_id, "depth_mm": _number(params["depth_mm"], pp + ".depth_mm", positive=True, allow_bindings=allow_bindings)}
            if op == "extrude_cut":
                if not solid_seen:
                    _fail("invalid_sequence", path, "a cut requires an earlier boss operation in this new-part plan")
                normalized["through_all"] = _boolean(params.get("through_all", False), pp + ".through_all")
                normalized["reverse"] = _boolean(params.get("reverse", False), pp + ".reverse")
            else:
                solid_seen = True
        out = {"id": identifier, "op": op, "params": normalized,
               "expect": _expect(operation.get("expect", {}), path + ".expect", allow_bindings)}
        if "fallback_params" in operation:
            fallbacks = operation["fallback_params"]
            if op != "extrude_cut" or not isinstance(fallbacks, list) or len(fallbacks) != 1:
                _fail("unsupported_fallback", path + ".fallback_params", "only one explicit cut-direction fallback is supported")
            fallback = _object(fallbacks[0], path + ".fallback_params.0")
            _keys(fallback, {"reverse"}, {"reverse"}, path + ".fallback_params.0")
            reverse = _boolean(fallback["reverse"], path + ".fallback_params.0.reverse")
            if reverse == normalized["reverse"]:
                _fail("invalid_fallback", path + ".fallback_params", "fallback must use the opposite cut direction")
            out["fallback_params"] = [{"reverse": reverse}]
        result["operations"].append(out)
    if not solid_seen and not allow_prefix:
        _fail("invalid_sequence", "plan.operations", "a deliverable part requires at least one boss operation")
    requirements = plan.get("requirements", [])
    if not isinstance(requirements, list):
        _fail("invalid_requirements", "plan.requirements", "must be a list of geometry expectation objects")
    for i, requirement in enumerate(requirements):
        normalized = _expect(requirement, f"plan.requirements.{i}", allow_bindings)
        if not set(normalized) - {"description"}:
            _fail("empty_requirement", f"plan.requirements.{i}", "must contain a measurable expectation")
        result["requirements"].append(normalized)
    for key in ("source_bindings", "assumptions", "metadata"):
        if key in plan:
            result[key] = _json_data(plan[key], "plan." + key)
    return result


def resolve_context_bindings(value: Any, context: dict, source: dict | None = None) -> Any:
    """Resolve only numeric whitelist paths; fail on missing/unavailable evidence.

    Call the validator again with allow_bindings=False on resolved operations.
    A ``from_context`` path reads the preceding actual snapshot. ``from_source``
    reads the initial read-only reference snapshot. No eval or attribute access.
    """
    if isinstance(value, list):
        return [resolve_context_bindings(item, context, source) for item in value]
    if not isinstance(value, dict):
        return copy.deepcopy(value)
    if set(value) & {"from_context", "from_source"}:
        binding = _binding(value, "binding")
        source_key = "from_source" if "from_source" in binding else "from_context"
        evidence = source if source_key == "from_source" else context
        path = binding[source_key]
        current: Any = evidence
        for segment in path.split("."):
            try:
                if isinstance(current, dict):
                    current = current[segment]
                elif isinstance(current, list) and segment.isdigit():
                    current = current[int(segment)]
                else:
                    raise KeyError(segment)
            except (KeyError, IndexError, TypeError):
                _fail("missing_context", path, f"{source_key} has no measured value for {path}")
        number = _number(current, path, allow_bindings=False)
        result = number * binding["scale"] + binding["offset_mm"]
        return _number(result, path, allow_bindings=False)
    return {key: resolve_context_bindings(item, context, source) for key, item in value.items()}


def compile_design_plan(plan: dict) -> dict:
    """Compile a supported legacy feature plan or validate a new operation plan.

    Legacy support is intentionally limited to a centered rectangular base plate
    and explicit circular through holes. Required and optional unsupported
    geometry is rejected alike. Lifecycle instructions cannot close documents.
    The untouched legacy planner remains available for more complex proposals.
    """
    plan = _object(plan, "plan")
    if "operations" in plan or "schema_version" in plan:
        return validate_operation_plan(plan)
    if type(plan.get("plan_version")) is not int or plan["plan_version"] != 1:
        _fail("unsupported_version", "plan.plan_version", "only legacy plan_version=1 is supported")
    parameters = _object(plan.get("parameters"), "plan.parameters")
    if parameters.get("unit") != "mm":
        _fail("unsupported_units", "plan.parameters.unit", "legacy dimensions must explicitly use mm")
    features = plan.get("features")
    if not isinstance(features, list) or not features:
        _fail("invalid_features", "plan.features", "must contain at least one feature")
    supported = {"base_plate", "through_hole_pattern", "through_hole"}
    issues = []
    for i, feature in enumerate(features):
        if not isinstance(feature, dict) or feature.get("type") not in supported:
            kind = feature.get("type") if isinstance(feature, dict) else feature
            issues.append({"code": "unsupported_feature", "path": f"plan.features.{i}",
                           "message": f"{kind!r} is not implemented by the bounded executor; revise the plan explicitly or use the existing specialist workflow"})
    lifecycle = {"new_part", "base_plate", "through_holes", "save_export_review"}
    sequence = plan.get("operation_sequence", [])
    if not isinstance(sequence, list) or any(not isinstance(item, str) for item in sequence):
        _fail("invalid_sequence", "plan.operation_sequence", "must be a list of strings")
    for i, action in enumerate(sequence):
        if action not in lifecycle:
            issues.append({"code": "unsupported_legacy_action", "path": f"plan.operation_sequence.{i}",
                           "message": f"{action!r} is not executed or silently skipped; existing documents are never closed by a plan"})
    if issues:
        raise PlanValidationError(issues)
    # These legacy requirements describe output/inspection machinery not geometry.
    # Keep them in metadata so the runner/reviewer can report them explicitly.
    ops = []
    depth = None
    for i, feature in enumerate(features):
        path = f"plan.features.{i}"
        params = _object(feature.get("params"), path + ".params")
        kind = feature["type"]
        feature_id = f"feature_{i + 1}"
        if kind == "base_plate":
            if i != 0 or depth is not None:
                _fail("invalid_sequence", path, "exactly one base_plate must be the first feature")
            _keys(params, {"length", "width", "thickness"}, {"length", "width", "thickness"}, path + ".params")
            length = _number(params["length"], path + ".params.length", positive=True, allow_bindings=False)
            width = _number(params["width"], path + ".params.width", positive=True, allow_bindings=False)
            depth = _number(params["thickness"], path + ".params.thickness", positive=True, allow_bindings=False)
            ops.extend([
                {"id": feature_id + "_sketch", "op": "sketch_rectangle", "params": {"plane": "Front Plane", "cx_mm": 0, "cy_mm": 0, "width_mm": length, "height_mm": width}},
                {"id": feature_id, "op": "extrude_boss", "params": {"sketch_id": feature_id + "_sketch", "depth_mm": depth},
                 "expect": {"body_count": 1, "bbox_size_mm": [length, width, depth], "volume_mm3": length * width * depth, "feature_ok": True}},
            ])
        else:
            if depth is None:
                _fail("invalid_sequence", path, "through holes require a preceding base_plate")
            if kind == "through_hole":
                _keys(params, {"diameter", "position_xy"}, {"diameter", "position_xy"}, path + ".params")
                diameter = _number(params["diameter"], path + ".params.diameter", positive=True, allow_bindings=False)
                positions = [_vector(params["position_xy"], path + ".params.position_xy", 2, allow_bindings=False)]
            else:
                _keys(params, {"fastener", "clearance_diameter", "positions_xy"}, {"clearance_diameter", "positions_xy"}, path + ".params")
                diameter = _number(params["clearance_diameter"], path + ".params.clearance_diameter", positive=True, allow_bindings=False)
                if not isinstance(params["positions_xy"], list) or not params["positions_xy"]:
                    _fail("invalid_holes", path + ".params.positions_xy", "must contain explicit hole positions")
                positions = [_vector(p, f"{path}.params.positions_xy.{j}", 2, allow_bindings=False) for j, p in enumerate(params["positions_xy"])]
            # Reject duplicate/overlapping circles and holes outside the stock;
            # otherwise a cut can succeed while failing the stated hole intent.
            for j, (x, y) in enumerate(positions):
                if abs(x) + diameter / 2 >= length / 2 or abs(y) + diameter / 2 >= width / 2:
                    _fail("hole_outside_stock", path + f".params.positions.{j}", "hole must lie wholly inside the rectangular stock")
                if any(math.hypot(x - px, y - py) <= diameter for px, py in positions[:j]):
                    _fail("overlapping_holes", path, "holes overlap or touch; revise explicit positions")
            circles = [{"x_mm": x, "y_mm": y, "radius_mm": diameter / 2} for x, y in positions]
            ops.extend([
                {"id": feature_id + "_sketch", "op": "sketch_circles", "params": {"plane": "Front Plane", "circles": circles}},
                {"id": feature_id, "op": "extrude_cut", "params": {"sketch_id": feature_id + "_sketch", "depth_mm": depth, "through_all": True, "reverse": False},
                 "expect": {"body_count": 1, "feature_ok": True, "holes": [{"diameter_mm": diameter, "position_mm": [x, y, 0]} for x, y in positions]},
                 "fallback_params": [{"reverse": True}]},
            ])
    result = {"schema_version": 1, "name": str(plan.get("part_family") or "VibeCADPart"),
              "operations": ops, "requirements": [], "assumptions": copy.deepcopy(plan.get("assumptions", [])),
              "metadata": {"source_format": "vibecad_design_plan_v1", "source_brief": plan.get("source_brief", ""),
                           "legacy_parameters": copy.deepcopy(parameters), "legacy_review_plan": copy.deepcopy(plan.get("review_plan", {})),
                           "legacy_features": copy.deepcopy(features),
                           "notice": "Only geometric features are compiled; material and custom properties are reference metadata, not assigned CAD properties."}}
    return validate_operation_plan(result)
