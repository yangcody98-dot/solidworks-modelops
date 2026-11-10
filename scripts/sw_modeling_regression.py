"""Repeatable native create/edit/recovery benchmark with independent geometry oracles.

``validate`` is offline. ``run`` requires an open SolidWorks session and creates
only new files below a new output directory. The final checkpoint is reopened by
a fresh Python process, so an in-memory backend cannot make that case pass.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUITE = ROOT / "examples" / "modeling_regression_suite.json"
_ACTIONS = ("create", "edit", "failed_edit", "restore")
_IDS = ("create_plate", "edit_thickness", "recover_failed_edit", "restore_checkpoint")


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _keys(value, allowed, required, label):
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    if set(value) - set(allowed) or set(required) - set(value):
        raise ValueError(f"{label} has missing or unsupported fields")


def validate_suite(suite: dict) -> dict:
    """Validate benchmark inputs without importing a CAD module or touching CAD."""
    _keys(suite, {"schema_version", "name", "description", "fixture", "tolerances", "cases"},
          {"schema_version", "name", "fixture", "tolerances", "cases"}, "suite")
    if type(suite["schema_version"]) is not int or suite["schema_version"] != 1:
        raise ValueError("Only suite schema_version=1 is supported")
    if not isinstance(suite["name"], str) or not suite["name"].strip():
        raise ValueError("suite.name must be nonempty text")
    fixture = suite["fixture"]
    sizes = {"width_mm", "height_mm", "initial_thickness_mm", "edited_thickness_mm", "rejected_thickness_mm"}
    _keys(fixture, sizes | {"holes"}, sizes | {"holes"}, "fixture")
    if any(not _finite(fixture[k]) or fixture[k] <= 0 for k in sizes):
        raise ValueError("Fixture dimensions must be finite and positive")
    if len({fixture[k] for k in ("initial_thickness_mm", "edited_thickness_mm", "rejected_thickness_mm")}) != 3:
        raise ValueError("Initial, edited and rejected thicknesses must differ")
    holes = fixture["holes"]
    if not isinstance(holes, list) or len(holes) != 4:
        raise ValueError("This benchmark requires exactly four holes")
    for index, hole in enumerate(holes):
        _keys(hole, {"x_mm", "y_mm", "radius_mm"}, {"x_mm", "y_mm", "radius_mm"}, "hole")
        if not all(_finite(hole[k]) for k in hole) or hole["radius_mm"] <= 0:
            raise ValueError("Hole coordinates must be finite and radii positive")
        if (abs(hole["x_mm"]) + hole["radius_mm"] >= fixture["width_mm"] / 2
                or abs(hole["y_mm"]) + hole["radius_mm"] >= fixture["height_mm"] / 2):
            raise ValueError("Holes must lie strictly inside the plate")
        for other in holes[:index]:
            if math.hypot(hole["x_mm"] - other["x_mm"], hole["y_mm"] - other["y_mm"]) <= hole["radius_mm"] + other["radius_mm"]:
                raise ValueError("Benchmark holes must not overlap or touch")
    tolerances = suite["tolerances"]
    allowed = {"volume_mm3", "bounds_mm", "hole_position_mm", "hole_diameter_mm"}
    _keys(tolerances, allowed, allowed, "tolerances")
    if any(not _finite(v) or v <= 0 for v in tolerances.values()):
        raise ValueError("Tolerances must be finite and positive")
    cases = suite["cases"]
    if not isinstance(cases, list) or len(cases) != len(_ACTIONS):
        raise ValueError("The suite requires create, edit, failed_edit and restore cases")
    for index, case in enumerate(cases):
        required = {"id", "action", "expected_status"} | ({"source_case"} if index else set())
        _keys(case, required, required, "case")
        if case["id"] != _IDS[index] or case["action"] != _ACTIONS[index]:
            raise ValueError("The benchmark case ids and dependency order are fixed")
        if case["expected_status"] != ("recovered" if index == 2 else "passed"):
            raise ValueError("An expected failed edit must recover; other cases must pass")
        if index and case["source_case"] != ("create_plate" if index == 1 else "edit_thickness"):
            raise ValueError("Case source must refer to its declared accepted predecessor")
    # Reject non-JSON metadata and NaN anywhere, including optional description.
    return json.loads(json.dumps(suite, allow_nan=False))


def oracle(suite: dict, thickness_mm: float) -> dict:
    """Analytic result for a rectangle minus four disjoint through cylinders."""
    fixture, tolerance = suite["fixture"], suite["tolerances"]
    area = fixture["width_mm"] * fixture["height_mm"]
    area -= sum(math.pi * hole["radius_mm"] ** 2 for hole in fixture["holes"])
    return {"body_count": 1,
            "bbox_size_mm": [fixture["width_mm"], fixture["height_mm"], thickness_mm],
            "bbox_tolerance_mm": tolerance["bounds_mm"],
            "volume_mm3": area * thickness_mm,
            "volume_tolerance_mm3": tolerance["volume_mm3"],
            "holes": [{"diameter_mm": 2 * h["radius_mm"], "position_mm": [h["x_mm"], h["y_mm"], 0]}
                      for h in fixture["holes"]],
            "hole_tolerance_mm": min(tolerance["hole_position_mm"], tolerance["hole_diameter_mm"])}


def create_request(suite: dict) -> dict:
    fixture = suite["fixture"]
    thickness = fixture["initial_thickness_mm"]
    plan = {"schema_version": 1, "name": suite["name"], "operations": [
        {"id": "outline", "op": "sketch_rectangle", "params": {
            "plane": "Front Plane", "cx_mm": 0, "cy_mm": 0,
            "width_mm": fixture["width_mm"], "height_mm": fixture["height_mm"]}},
        {"id": "stock", "op": "extrude_boss", "params": {"sketch_id": "outline", "depth_mm": thickness},
         "expect": {"body_count": 1, "volume_mm3": fixture["width_mm"] * fixture["height_mm"] * thickness,
                    "volume_tolerance_mm3": suite["tolerances"]["volume_mm3"]}},
        {"id": "hole_sketch", "op": "sketch_circles", "params": {
            "plane": "Front Plane", "circles": copy.deepcopy(fixture["holes"])}},
        {"id": "holes", "op": "extrude_cut", "params": {
            "sketch_id": "hole_sketch", "depth_mm": thickness, "through_all": True, "reverse": False},
         "fallback_params": [{"reverse": True}], "expect": oracle(suite, thickness)},
    ], "requirements": [oracle(suite, thickness)]}
    return {"schema_version": 1, "mode": "create", "plan": plan}


def _hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path, data):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)


def _boss_dimension(report):
    for step in report.get("steps", []):
        if step.get("id") != "stock" or step.get("op") != "extrude_boss":
            continue
        attempts = [a for a in step.get("attempts", []) if a.get("passed") is True]
        result = attempts[-1].get("result", {}) if attempts else step.get("result", {})
        name = result.get("feature_name")
        if isinstance(name, str) and name and "@" not in name and not any(ord(c) < 32 for c in name):
            return "D1@" + name
    raise ValueError("Creation report has no accepted stock extrusion feature name")


def _checkpoint(report):
    checkpoints = report.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        raise ValueError("An accepted model needs a persisted checkpoint")
    value = checkpoints[-1]
    if not isinstance(value, dict) or not value.get("id") or not value.get("manifest_path"):
        raise ValueError("Checkpoint id and manifest_path evidence is missing")
    manifest = Path(value["manifest_path"])
    if not manifest.is_file() or manifest.stat().st_size == 0:
        raise ValueError("Checkpoint manifest is missing or empty")
    return value, manifest.parent.parent


def _axis_distance(point, origin, axis):
    if not all(isinstance(v, (list, tuple)) and len(v) == 3 and all(_finite(x) for x in v)
               for v in (point, origin, axis)):
        return math.inf
    length = math.sqrt(sum(x * x for x in axis))
    if length <= 1e-12:
        return math.inf
    direction = [x / length for x in axis]
    delta = [a - b for a, b in zip(point, origin)]
    projection = sum(a * b for a, b in zip(delta, direction))
    return math.sqrt(sum((a - projection * b) ** 2 for a, b in zip(delta, direction)))


def geometry_checks(context, expected, suite):
    """Check independent B-Rep/geometry evidence; missing evidence always fails."""
    geometry = context.get("geometry", {}) if isinstance(context, dict) else {}
    actual_bounds, actual_volume = geometry.get("bbox_size_mm"), geometry.get("volume_mm3")
    checks = [
        {"name": "body_count", "passed": type(geometry.get("body_count")) is int and geometry["body_count"] == 1},
        {"name": "analytic_volume", "expected": expected["volume_mm3"], "actual": actual_volume,
         "passed": _finite(actual_volume) and abs(actual_volume - expected["volume_mm3"]) <= expected["volume_tolerance_mm3"]},
        {"name": "bounds", "expected": expected["bbox_size_mm"], "actual": actual_bounds,
         "passed": isinstance(actual_bounds, (list, tuple)) and len(actual_bounds) == 3
             and all(_finite(a) and abs(a - b) <= expected["bbox_tolerance_mm"] for a, b in zip(actual_bounds, expected["bbox_size_mm"]))},
    ]
    measurement = geometry.get("hole_measurements")
    actual_holes = measurement.get("holes", []) if isinstance(measurement, dict) else []
    checks.append({"name": "exact_hole_count", "expected": 4, "actual": len(actual_holes),
                   "passed": len(actual_holes) == 4})
    used = set()
    for index, hole in enumerate(expected["holes"]):
        candidates = []
        for actual_index, actual in enumerate(actual_holes):
            if actual_index in used or not isinstance(actual, dict):
                continue
            diameter = actual.get("diameter_mm")
            axis = actual.get("axis")
            error = _axis_distance(hole["position_mm"], actual.get("position_mm"), axis)
            # These are through holes along Z. A tilted axis crossing the expected
            # point cannot stand in for the specified plate-normal hole.
            normal = (isinstance(axis, (list, tuple)) and len(axis) == 3 and all(_finite(v) for v in axis)
                      and abs(axis[0]) <= 1e-6 and abs(axis[1]) <= 1e-6 and abs(abs(axis[2]) - 1) <= 1e-6)
            if (_finite(diameter) and normal
                    and abs(diameter - hole["diameter_mm"]) <= suite["tolerances"]["hole_diameter_mm"]
                    and error <= suite["tolerances"]["hole_position_mm"]):
                candidates.append((error, actual_index))
        match = min(candidates) if candidates else None
        if match:
            used.add(match[1])
        checks.append({"name": f"hole_{index + 1}_axis_and_diameter", "passed": match is not None})
    return checks


def _delivery_checks(report):
    delivery = report.get("delivery", {})
    constraints = delivery.get("sketch_constraints", {})
    paths = [delivery.get("native"), delivery.get("step")]
    files_ok = all(isinstance(p, str) and Path(p).is_file() and Path(p).stat().st_size > 0 for p in paths)
    return [{"name": "native_and_step_files", "passed": files_ok},
            {"name": "fully_defined_parametric_sketches", "passed": constraints.get("all_fully_defined") is True
                and constraints.get("all_parametric") is True},
            {"name": "step_reopen", "passed": delivery.get("step_reopen_validation", {}).get("passed") is True}]


def _failed_edit_context(report):
    for step in report.get("steps", []):
        if step.get("id") != "reject_wrong_volume":
            continue
        if isinstance(step.get("after"), dict):
            return step["after"]
        attempts = step.get("attempts", [])
        if attempts and isinstance(attempts[-1].get("after"), dict):
            return attempts[-1]["after"]
    return None


def _isolated_restore(request, output):
    """Use a fresh interpreter; no arbitrary code is read from the request."""
    request_path = output.parent / "restore_child_request.json"
    response_path = output.parent / "restore_child_result.json"
    _write_json(request_path, request)
    code = ("import json,os,sys;from pathlib import Path;"
            "sys.path.insert(0,sys.argv[1]);from sw_modeling import run_request;"
            "request=json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'));"
            "report=run_request(request,Path(sys.argv[3]));"
            "report['_regression_process']={'pid':os.getpid(),'parent_pid':os.getppid()};"
            "Path(sys.argv[4]).write_text(json.dumps(report,ensure_ascii=False,allow_nan=False),encoding='utf-8')")
    result = subprocess.run([sys.executable, "-c", code, str(ROOT / "scripts"), str(request_path), str(output), str(response_path)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600, cwd=ROOT)
    if result.returncode != 0 or not response_path.is_file():
        raise RuntimeError(f"Independent checkpoint restore failed ({result.returncode}): {result.stderr[-2000:]}")
    return json.loads(response_path.read_text(encoding="utf-8"))


def run_suite(suite: dict, out_dir: Path, *, runner: Callable | None = None,
              isolated_runner: Callable | None = None) -> dict:
    """Run serial native cases, or use explicitly injected backends for offline tests."""
    suite = validate_suite(suite)
    output = Path(out_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    _write_json(output / "suite.json", suite)
    native_execution = runner is None and isolated_runner is None
    if runner is None:
        try:
            from .sw_modeling import run_request
        except ImportError:
            from sw_modeling import run_request
        runner = run_request
    if isolated_runner is None:
        isolated_runner = _isolated_restore
    summary = {"schema_version": 1, "name": suite["name"], "passed": False,
               "execution": "native" if native_execution else "injected_test_backend", "cases": [],
               "engineering_review_required": True}
    reports = {}
    dimension = None
    for case in suite["cases"]:
        entry = {"id": case["id"], "action": case["action"], "passed": False, "checks": []}
        summary["cases"].append(entry)
        source_hash = None
        source = None
        try:
            if case["action"] == "create":
                request = create_request(suite)
                expected = oracle(suite, suite["fixture"]["initial_thickness_mm"])
            else:
                predecessor = reports[case["source_case"]]
                source = Path(predecessor["delivery"]["native"]).resolve()
                source_hash = _hash(source)
                expected = oracle(suite, suite["fixture"]["edited_thickness_mm"])
                if case["action"] == "restore":
                    checkpoint, checkpoint_root = _checkpoint(predecessor)
                    request = {"schema_version": 1, "mode": "restore", "checkpoint_root": str(checkpoint_root),
                               "checkpoint_id": checkpoint["id"], "requirements": [expected]}
                else:
                    failed = case["action"] == "failed_edit"
                    thickness = suite["fixture"]["rejected_thickness_mm" if failed else "edited_thickness_mm"]
                    target = oracle(suite, thickness)
                    if failed:
                        target["volume_mm3"] += max(1000, target["volume_tolerance_mm3"] * 100)
                    request = {"schema_version": 1, "mode": "edit", "source": str(source),
                               "operations": [{"id": "reject_wrong_volume" if failed else "change_thickness", "op": "set_dimension",
                                               "params": {"name": dimension, "value_mm": thickness}, "expect": target}],
                               "requirements": [target]}
            _write_json(output / (case["id"] + "_request.json"), request)
            invoke = isolated_runner if case["action"] == "restore" else runner
            report = invoke(copy.deepcopy(request), output / case["id"])
            if not isinstance(report, dict):
                raise ValueError("Modeling API returned no report object")
            _write_json(output / (case["id"] + "_result.json"), report)
            entry["actual_status"] = report.get("status")
            checks = entry["checks"]
            checks.append({"name": "expected_status", "expected": case["expected_status"],
                           "actual": report.get("status"), "passed": report.get("status") == case["expected_status"]})
            checks.append({"name": "source_protection", "passed": report.get("source_protection", {}).get("passed") is True})
            if case["action"] == "failed_edit":
                recovery = report.get("recovery", {})
                context = recovery.get("context") or recovery.get("final_context")
                recovery_path = recovery.get("native")
                ids = {item.get("id") for item in report.get("checkpoints", []) if isinstance(item, dict)}
                checks.append({"name": "checkpoint_recovered", "passed": recovery.get("passed") is True
                               and bool(recovery.get("checkpoint_id")) and recovery.get("checkpoint_id") in ids
                               and isinstance(recovery_path, str)
                               and Path(recovery_path).is_file() and Path(recovery_path).stat().st_size > 0})
                failed_checks = geometry_checks(_failed_edit_context(report),
                    oracle(suite, suite["fixture"]["rejected_thickness_mm"]), suite)
                for check in failed_checks:
                    check["name"] = "failed_edit_" + check["name"]
                checks.extend(failed_checks)
                recovered_checks = geometry_checks(context, expected, suite)
                for check in recovered_checks:
                    check["name"] = "recovered_" + check["name"]
                checks.extend(recovered_checks)
            else:
                checks.extend(geometry_checks(report.get("final_context"), expected, suite))
                checks.extend(_delivery_checks(report))
                _checkpoint(report)
                if case["action"] == "create":
                    dimension = _boss_dimension(report)
                    entry["discovered_dimension"] = dimension
                if case["action"] == "restore" and native_execution:
                    process = report.get("_regression_process", {})
                    checks.append({"name": "independent_process", "passed": type(process.get("pid")) is int
                                   and process["pid"] != os.getpid() and process.get("parent_pid") == os.getpid()})
            if source is not None:
                checks.append({"name": "source_disk_unchanged", "path": str(source),
                               "passed": _hash(source) == source_hash})
            entry["passed"] = bool(checks) and all(c["passed"] for c in checks)
            reports[case["id"]] = report
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
            if source is not None and source_hash is not None:
                entry["checks"].append({"name": "source_disk_unchanged", "passed": source.is_file() and _hash(source) == source_hash})
        if not entry["passed"]:
            # Later cases depend on accepted native files and checkpoints.
            break
    summary["passed"] = len(summary["cases"]) == len(suite["cases"]) and all(c["passed"] for c in summary["cases"])
    _write_json(output / "regression_summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate", help="Validate the benchmark without connecting to CAD")
    validate.add_argument("--suite", default=str(DEFAULT_SUITE))
    run = subparsers.add_parser("run", help="Run new, isolated native CAD fixtures serially")
    run.add_argument("--suite", default=str(DEFAULT_SUITE))
    run.add_argument("--out-dir", required=True, help="Must not already exist")
    args = parser.parse_args(argv)
    suite = validate_suite(json.loads(Path(args.suite).read_text(encoding="utf-8-sig")))
    if args.command == "validate":
        print(json.dumps({"status": "valid", "name": suite["name"], "cases": len(suite["cases"]),
                          "initial_oracle": oracle(suite, suite["fixture"]["initial_thickness_mm"])}, ensure_ascii=False))
        return 0
    report = run_suite(suite, Path(args.out_dir))
    print(json.dumps({"passed": report["passed"], "cases": len(report["cases"]),
                      "report": str(Path(args.out_dir).resolve() / "regression_summary.json")}, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
