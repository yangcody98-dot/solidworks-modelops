"""Observe -> execute -> measure -> bounded feedback, with no implicit CAD writes.

The engine accepts an operation plan, not arbitrary Python or natural-language code.
Native writes are isolated in sw_closed_loop_native and always target a new part.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

try:
    from .sw_plan_bridge import compile_design_plan, resolve_context_bindings, validate_operation_plan
except ImportError:
    from sw_plan_bridge import compile_design_plan, resolve_context_bindings, validate_operation_plan


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def check_expectations(context: dict, expected: dict) -> list[dict]:
    """Check measured values; unavailable evidence never counts as a pass."""
    geometry = context.get("geometry", {})
    checks = []
    for key in ("body_count", "volume_mm3"):
        if key not in expected:
            continue
        actual, target = geometry.get(key), expected[key]
        tolerance = expected.get("volume_tolerance_mm3", 0.01) if key == "volume_mm3" else 0
        passed = _finite(actual) and abs(actual - target) <= tolerance
        checks.append({"check": key, "expected": target, "actual": actual, "passed": passed})
    if "bbox_size_mm" in expected:
        actual = geometry.get("bbox_size_mm")
        target = expected["bbox_size_mm"]
        tolerance = expected.get("bbox_tolerance_mm", 0.05)
        passed = (isinstance(actual, (list, tuple)) and len(actual) == 3
                  and all(_finite(a) and abs(a - b) <= tolerance for a, b in zip(actual, target)))
        checks.append({"check": "bbox_size_mm", "expected": target, "actual": actual, "passed": passed})
    if expected.get("feature_ok"):
        errors = [f for f in context.get("features", []) if f.get("error_code") not in (None, 0)]
        known = [f for f in context.get("features", []) if f.get("error_code") is not None]
        checks.append({"check": "feature_ok", "passed": context.get("features_complete") is True and bool(known) and len(known) == len(context.get("features", [])) and not errors,
                       "errors": errors, "checked_features": len(known)})
    if expected.get("holes"):
        # This uses B-Rep cylinder evidence; it does not claim to prove through/blind state.
        try:
            from .sw_review import validate_hole_positions
        except ImportError:
            from sw_review import validate_hole_positions
        measurement = geometry.get("hole_measurements")
        if measurement is None:
            checks.append({"check": "holes", "passed": False, "reason": "hole evidence unavailable"})
        else:
            tolerance = expected.get("hole_tolerance_mm", 0.05)
            result = validate_hole_positions(measurement, expected["holes"],
                position_tolerance_mm=tolerance, diameter_tolerance_mm=tolerance)
            checks.append({"check": "holes", "passed": result.get("status") == "pass", "detail": result})
    return checks


def mutation_signature(context: dict) -> dict:
    """Only evidence used to decide whether retrying could duplicate a feature."""
    g = context.get("geometry", {})
    return {"features": [(f.get("name"), f.get("type")) for f in context.get("features", [])],
            "body_count": g.get("body_count"), "volume_mm3": g.get("volume_mm3"),
            "bbox_mm": g.get("bbox_mm")}


def _unchanged_for_retry(before, after):
    a, b = mutation_signature(before), mutation_signature(after)
    # Missing volume/body evidence cannot prove a failed operation was non-mutating.
    return (a["body_count"] is not None and a["volume_mm3"] is not None
            and a == b and before.get("features_complete") is True and after.get("features_complete") is True)


def execute_plan(plan: dict, backend, *, source_context=None, event_sink=None) -> dict:
    """Run a validated plan on an owned backend. Stop on first unresolved failure.

    backend supplies snapshot(), execute(operation), rebuild(). A caller-provided
    backend is intended for unit tests; the public CLI creates only new native parts.
    Retries are restricted to one predeclared cut-direction alternative and only
    after measured evidence shows the failed attempt created no geometry/features.
    """
    plan = compile_design_plan(plan)
    report = {"schema_version": 1, "status": "running", "name": plan.get("name"),
              "steps": [], "source_context": source_context, "feedback": [], "final_checks": []}
    completed = []
    retry_used = False
    for operation in plan["operations"]:
        before = backend.snapshot()
        step = {"id": operation["id"], "op": operation["op"], "before": before, "attempts": []}
        report["steps"].append(step)
        try:
            resolved = copy.deepcopy(operation)
            resolved["params"] = resolve_context_bindings(operation["params"], before, source_context)
            resolved["expect"] = resolve_context_bindings(operation.get("expect", {}), before, source_context)
            # Validate values after resolving the current context, retaining prior references.
            prefix = {"schema_version": 1, "name": plan.get("name", "closed_loop"),
                      "operations": completed + [resolved], "requirements": []}
            validate_operation_plan(prefix, allow_bindings=False, allow_prefix=True)
        except Exception as exc:
            step["status"] = "needs_revision"
            report["feedback"].append({"step": operation["id"], "code": "invalid_context_binding",
                                       "message": str(exc), "action": "Supply measured context or explicit valid parameters."})
            report["status"] = "needs_revision"
            break
        alternatives = [{}] + resolved.get("fallback_params", [])
        for attempt_index, alternative in enumerate(alternatives):
            action = copy.deepcopy(resolved)
            action["params"].update(alternative)
            attempt = {"number": attempt_index + 1, "parameters": action["params"], "checks": []}
            step["attempts"].append(attempt)
            try:
                result = backend.execute(action)
                attempt["result"] = result
                rebuild_ok = backend.rebuild()
                after = backend.snapshot()
                checks = [{"check": "created", "passed": result.get("created") is True},
                          {"check": "rebuild", "passed": rebuild_ok is True}]
                checks.extend(check_expectations(after, resolved.get("expect", {})))
                if operation["op"] in {"extrude_boss", "extrude_cut"}:
                    old = before.get("geometry", {}).get("volume_mm3")
                    new = after.get("geometry", {}).get("volume_mm3")
                    if operation["op"] == "extrude_boss":
                        ok = _finite(old) and _finite(new) and new > old + 1e-6
                    else:
                        ok = _finite(old) and _finite(new) and new < old - 1e-6 and new > 0
                    checks.append({"check": "material_change", "before_mm3": old, "after_mm3": new, "passed": ok})
                attempt.update({"after": after, "checks": checks})
                passed = all(c["passed"] for c in checks)
            except Exception as exc:
                attempt["exception"] = f"{type(exc).__name__}: {exc}"
                after = backend.snapshot()
                attempt["after"] = after
                passed = False
            attempt["passed"] = passed
            if event_sink:
                event_sink(copy.deepcopy({"step": operation["id"], "attempt": attempt}))
            if passed:
                step["status"] = "passed"
                completed_action = copy.deepcopy(action)
                completed_action.pop("fallback_params", None)
                completed.append(completed_action)
                break
            can_retry = (not retry_used and attempt_index == 0 and len(alternatives) == 2
                         and operation["op"] == "extrude_cut"
                         and not attempt.get("result", {}).get("created")
                         and _unchanged_for_retry(before, after))
            if can_retry:
                retry_used = True
                report["feedback"].append({"step": operation["id"], "code": "retry_declared_direction",
                    "message": "No new geometry or feature detected; try the plan's one alternate cut direction."})
                continue
            step["status"] = "needs_revision"
            report["feedback"].append({"step": operation["id"], "code": "operation_or_measurement_failed",
                "message": attempt.get("exception", "Measured result did not satisfy the plan."),
                "failed_checks": [c for c in attempt["checks"] if not c["passed"]],
                "action": "Inspect the context and revise the plan. No later operations were executed."})
            break
        if step.get("status") != "passed":
            report["status"] = "needs_revision"
            break
    report["final_context"] = backend.snapshot()
    if report["status"] == "running":
        for requirement in plan.get("requirements", []):
            try:
                requirement = resolve_context_bindings(requirement, report["final_context"], source_context)
                report["final_checks"].extend(check_expectations(report["final_context"], requirement))
            except Exception as exc:
                report["final_checks"].append({"check": "requirement_binding", "passed": False, "message": str(exc)})
        report["status"] = "passed" if all(c["passed"] for c in report["final_checks"]) else "needs_revision"
        if report["status"] != "passed":
            report["feedback"].append({"code": "final_requirements_failed", "action": "Revise the plan; no delivery was exported."})
    report["engineering_review_required"] = True
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate", help="Offline plan validation; no CAD connection")
    check.add_argument("--plan", required=True)
    observe = commands.add_parser("observe", help="Read active model without changing it")
    observe.add_argument("--out", required=True)
    run = commands.add_parser("run", help="Execute in a NEW part; never write the source model")
    run.add_argument("--plan", required=True)
    run.add_argument("--out-dir", required=True, help="Must not already exist")
    args = parser.parse_args(argv)
    if args.command == "validate":
        plan = compile_design_plan(json.loads(Path(args.plan).read_text(encoding="utf-8-sig")))
        print(json.dumps({"status": "valid", "operations": len(plan["operations"])}, ensure_ascii=False))
        return 0
    try:
        from .sw_closed_loop_native import observe_active, run_native
    except ImportError:
        from sw_closed_loop_native import observe_active, run_native
    if args.command == "observe":
        output = Path(args.out)
        if output.exists():
            raise FileExistsError(output)
        data = observe_active()
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        print(json.dumps({"status": "observed", "output": str(output.resolve())}, ensure_ascii=False))
        return 0
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8-sig"))
    result = run_native(plan, Path(args.out_dir))
    print(json.dumps({"status": result["status"], "report": str(Path(args.out_dir).resolve() / "run_report.json")}, ensure_ascii=False))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
