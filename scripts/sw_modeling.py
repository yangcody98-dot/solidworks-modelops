"""Unified, measured create/edit/restore interface for task-owned SW part copies.

JSON requests are data. Imports and validation work without Windows or COM.
Native operations reuse the existing serial closed-loop adapter. Source parts
are disk snapshots, never the write target. A recovered task is still a failure.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import redirect_stdout
import json
import math
from pathlib import Path
import re
import sys
import uuid

try:
    from .sw_checkpoints import CheckpointStore
    from .sw_closed_loop import check_expectations, execute_plan
    from .sw_plan_bridge import compile_design_plan, _expect
except ImportError:
    from sw_checkpoints import CheckpointStore
    from sw_closed_loop import check_expectations, execute_plan
    from sw_plan_bridge import compile_design_plan, _expect


def _object(value, keys, required, label):
    if not isinstance(value, dict) or set(value) - set(keys) or set(required) - set(value):
        raise ValueError(f"Invalid fields in {label}; allowed: {sorted(keys)}")
    return value


def _finite(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def _requirements(values):
    if not isinstance(values, list):
        raise ValueError("requirements must be an array")
    result = [_expect(v, f"requirements[{i}]", False) for i, v in enumerate(values)]
    if any(not set(v).intersection({"body_count", "volume_mm3", "bbox_size_mm", "holes"}) for v in result):
        raise ValueError("Each requirement must contain measurable geometry acceptance")
    return result


def validate_request(request):
    """Validate before creating output files, attaching to CAD, or reading sources."""
    try:
        encoded = json.dumps(request, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("Request must contain finite JSON data") from exc
    if len(encoded) > 2_000_000:
        raise ValueError("Request exceeds 2 MB")
    if not isinstance(request, dict) or type(request.get("schema_version")) is not int or request["schema_version"] != 1:
        raise ValueError("schema_version must be integer 1")
    value = copy.deepcopy(request)
    mode = value.get("mode")
    if mode == "create":
        _object(value, {"schema_version", "mode", "plan"}, {"plan"}, "create request")
        value["plan"] = compile_design_plan(value["plan"])
        requirements = value["plan"].get("requirements", [])
        if not requirements or any(not set(v).intersection({"body_count", "volume_mm3", "bbox_size_mm", "holes"}) for v in requirements):
            raise ValueError("create requires explicit final geometry requirements")
    elif mode == "edit":
        _object(value, {"schema_version", "mode", "source", "operations", "requirements"},
                {"source", "operations", "requirements"}, "edit request")
        source = value["source"]
        if not isinstance(source, str) or not Path(source).is_absolute() or Path(source).suffix.lower() != ".sldprt":
            raise ValueError("source must be an absolute .sldprt path")
        operations = value["operations"]
        if not isinstance(operations, list) or not 1 <= len(operations) <= 128:
            raise ValueError("edit requires 1..128 operations")
        ids = set()
        for operation in operations:
            _object(operation, {"id", "op", "params", "expect"}, {"id", "op", "params"}, "edit operation")
            identifier = operation["id"]
            if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", identifier) or identifier in ids:
                raise ValueError("Operation IDs must be unique identifiers")
            ids.add(identifier)
            if operation["op"] != "set_dimension":
                raise ValueError("edit currently supports only set_dimension")
            params = _object(operation["params"], {"name", "value_mm"}, {"name", "value_mm"}, "dimension parameters")
            if not isinstance(params["name"], str) or not re.fullmatch(r"[^@\r\n]+@[^@\r\n]+", params["name"]):
                raise ValueError("Use the exact dimension@feature name, without a document suffix")
            if not _finite(params["value_mm"]) or params["value_mm"] <= 0:
                raise ValueError("value_mm must be a finite positive number")
            operation["expect"] = _expect(operation.get("expect", {}), "operation.expect", False)
        value["requirements"] = _requirements(value["requirements"])
        if not value["requirements"]:
            raise ValueError("edit requires explicit final geometry requirements")
    elif mode == "restore":
        _object(value, {"schema_version", "mode", "checkpoint_root", "checkpoint_id", "requirements"},
                {"checkpoint_root", "checkpoint_id"}, "restore request")
        root = value["checkpoint_root"]
        if not isinstance(root, str) or not Path(root).is_absolute():
            raise ValueError("checkpoint_root must be absolute")
        if not isinstance(value["checkpoint_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", value["checkpoint_id"]):
            raise ValueError("Invalid checkpoint_id")
        value["requirements"] = _requirements(value.get("requirements", []))
    else:
        raise ValueError("mode must be create, edit, or restore")
    return value


def compare_checkpoint_context(expected, actual):
    """Compare independent reopened geometry and editable state, ignoring filenames."""
    a, b = expected.get("geometry", {}), actual.get("geometry", {})
    checks = check_expectations(actual, {k: a[k] for k in ("body_count", "volume_mm3", "bbox_size_mm")
                                        if a.get(k) is not None})
    complete = all(a.get(k) is not None and b.get(k) is not None for k in ("body_count", "volume_mm3"))
    complete = complete and all(type(g.get("body_count")) is int and g["body_count"] >= 0
                                and _finite(g.get("volume_mm3")) and g["volume_mm3"] >= 0 for g in (a, b))
    if a.get("body_count", 0):
        complete = complete and a.get("bbox_mm") is not None and b.get("bbox_mm") is not None
        bounds = a.get("bbox_mm") or []
        other = b.get("bbox_mm") or []
        checks.append({"check": "bounds_and_position", "passed": len(bounds) == len(other) == 6
                       and all(_finite(x) and _finite(y) and abs(x-y) <= .05 for x, y in zip(bounds, other))})
    checks.append({"check": "geometry_evidence", "passed": bool(complete)})
    def features(context):
        return [(f.get("name"), f.get("type"), f.get("error_code")) for f in context.get("features", [])]
    def known_features(context):
        return all(isinstance(name, str) and bool(name) and isinstance(kind, str) and bool(kind)
                   and type(error) is int and error == 0 for name, kind, error in features(context))
    checks.append({"check": "features", "passed": expected.get("features_complete") is True
                   and actual.get("features_complete") is True and bool(features(expected))
                   and known_features(expected) and known_features(actual)
                   and features(expected) == features(actual)})
    checks.append({"check": "configuration", "passed": bool(expected.get("document", {}).get("configuration"))
                   and expected["document"]["configuration"] == actual.get("document", {}).get("configuration")})
    expected_dimensions = expected.get("dimensions", {})
    actual_dimensions = actual.get("dimensions", {})
    checks.append({"check": "dimension_inventory", "passed":
                   expected.get("dimensions_complete") is True and actual.get("dimensions_complete") is True
                   and bool(expected_dimensions) and set(expected_dimensions) == set(actual_dimensions)})
    for name, evidence in expected_dimensions.items():
        observed = actual.get("dimensions", {}).get(name, {})
        checks.append({"check": "dimension", "dimension": name, "passed":
                       _finite(evidence.get("system_value")) and _finite(observed.get("system_value"))
                       and abs(evidence["system_value"] - observed["system_value"]) <= 1e-9
                       and type(evidence.get("driven_state")) is int and evidence["driven_state"] in (1, 2)
                       and type(observed.get("driven_state")) is int
                       and evidence.get("driven_state") == observed.get("driven_state")
                       and type(evidence.get("parameter_type")) is int and evidence["parameter_type"] in (0, 1, 2)
                       and type(observed.get("parameter_type")) is int
                       and evidence.get("parameter_type") == observed.get("parameter_type")})
    old, new = expected.get("sketch_constraints", {}), actual.get("sketch_constraints", {})
    checks.append({"check": "sketch_constraints", "passed":
                   old.get("all_fully_defined") is True and old.get("all_parametric") is True
                   and new.get("all_fully_defined") is True and new.get("all_parametric") is True
                   and old.get("complete") is True and new.get("complete") is True
                   and type(old.get("sketch_count")) is int and old["sketch_count"] > 0
                   and type(new.get("sketch_count")) is int
                   and old.get("sketch_count") == new.get("sketch_count")})
    return {"passed": bool(checks) and all(c["passed"] for c in checks), "checks": checks}


def execute_edits(request, backend, checkpoint):
    """Transactional operation decisions, injectable for offline behavioral tests."""
    result = {"status": "running", "steps": [], "final_checks": [], "feedback": []}
    for operation in request["operations"]:
        step = {"id": operation["id"], "op": operation["op"], "before": backend.snapshot()}
        result["steps"].append(step)
        try:
            evidence = backend.set_dimension(operation["params"]["name"], operation["params"]["value_mm"])
            context = backend.snapshot()
            checks = [{"check": "dimension_readback", "passed": evidence.get("verified") is True}]
            checks.extend(check_expectations(context, operation.get("expect", {})))
            checks.extend(_part_health(context))
            step.update(result=evidence, after=context, checks=checks)
            if not all(c["passed"] for c in checks):
                raise RuntimeError("Edit failed measured acceptance")
            checkpoint(operation["id"])
            step["status"] = "passed"
        except Exception as exc:
            step.update(status="needs_revision", error=f"{type(exc).__name__}: {exc}")
            result["status"] = "needs_revision"
            result["feedback"].append({"step": operation["id"], "message": step["error"]})
            break
    result["final_context"] = backend.snapshot()
    if result["status"] == "running":
        for expected in request["requirements"]:
            result["final_checks"].extend(check_expectations(result["final_context"], expected))
        result["status"] = "passed" if all(c["passed"] for c in result["final_checks"]) else "needs_revision"
    return result


def _part_health(context):
    g = context.get("geometry", {})
    sketches = context.get("sketch_constraints", {})
    return [
        {"check": "solid_part", "passed": isinstance(g.get("body_count"), int) and g["body_count"] > 0
         and _finite(g.get("volume_mm3")) and g["volume_mm3"] > 0},
        {"check": "parametric_sketches", "passed": sketches.get("all_fully_defined") is True
         and sketches.get("all_parametric") is True},
        *check_expectations(context, {"feature_ok": True}),
    ]


def _native_backend_class():
    # Keep all COM initialization behind the native entry, including on Linux CI.
    try:
        from . import sw_closed_loop_native as native
        from . import sw_sketch_constraints as constraints
        from .sw_document_data import update_dimension_mm
    except ImportError:
        import sw_closed_loop_native as native
        import sw_sketch_constraints as constraints
        from sw_document_data import update_dimension_mm

    class ModelBackend(native.NativePartBackend):
        @classmethod
        def open_owned(cls, sw, documents, originals, path):
            self = cls.__new__(cls)
            self.sw = sw
            self.c, self.part, self.review, self.export = native._helpers()
            self.protected_docs = copy.deepcopy(documents)
            self.protected = {(d.get("path"), d.get("title")) for d in documents}
            self.protected_titles = {d["title"].casefold() for d in documents}
            self.original_models = list(originals)
            self.protected_identities = [native._document_identity(m) for m in originals]
            self.model, self.sketches = None, {}
            self.owned_path = str(Path(path).resolve())
            if sw.GetOpenDocumentByName(self.owned_path) is not None:
                raise RuntimeError("Owned copy is already open; refusing to adopt a user document")
            model = self.c.open_document(sw, self.owned_path, silent=True)
            identity = native._document_identity(model)
            info = native.capture_model_context(model, include_geometry=False)["document"]
            if identity in self.protected_identities or info.get("type") != 1 or info.get("path") != self.owned_path:
                raise RuntimeError("Owned copy identity/path/type is invalid")
            if str(info.get("title", "")).casefold() in self.protected_titles:
                raise RuntimeError("Owned copy title collides with a source document")
            self.model, self.identity, self.initial_title = model, identity, info["title"]
            self.ensure_owned()
            names = list(self.c.get_com_member(model, "GetConfigurationNames") or [])
            dependencies = self.c.get_com_member(model, "GetDependencies2", True, False, False)
            if len(names) != 1 or dependencies:
                self.close()
                raise RuntimeError("This version edits/restores only single-configuration parts without external dependencies")
            return self

        def snapshot(self):
            context = super().snapshot()
            context["sketch_constraints"] = constraints.collect_sketch_constraint_status(self.model)
            dimensions = {}
            dimensions_complete = context.get("features_complete") is True
            for feature_info in context.get("features", []):
                feature = self.model.FeatureByName(feature_info["name"])
                warnings = []
                values, complete, _ = constraints._dimensions(feature, warnings)
                dimensions_complete = dimensions_complete and complete
                for value in values:
                    name = "@".join(value["name"].split("@")[:2])
                    parameter = self.model.Parameter(name)
                    value["parameter_type"] = int(self.c.get_com_member(parameter, "GetType"))
                    value["name"] = name
                    dimensions[name] = value
            # Sketches absorbed into solid features may not be in the top-level list.
            for sketch in context["sketch_constraints"].get("sketches", []):
                for value in sketch.get("dimensions", []):
                    name = "@".join(value["name"].split("@")[:2])
                    if name not in dimensions:
                        value = copy.deepcopy(value)
                        value["parameter_type"] = int(self.c.get_com_member(self.model.Parameter(name), "GetType"))
                        value["name"] = name
                        dimensions[name] = value
            context["dimensions"] = dimensions
            context["dimensions_complete"] = dimensions_complete and context["sketch_constraints"].get("complete") is True
            return context

        def set_dimension(self, name, value):
            self.ensure_owned()
            dimension = self.model.Parameter(name)
            if dimension is None:
                raise LookupError(f"Dimension not found: {name}")
            # Official IDimension.GetType: swDimensionParamTypeDoubleLinear=0.
            if self.c.get_com_member(dimension, "GetType") != 0:
                raise ValueError("Only linear dimensions may be edited in millimetres")
            if self.c.get_com_member(dimension, "DrivenState") != 2:
                raise ValueError("Dimension must be driving")
            evidence = update_dimension_mm(self.model, name, value, rebuild=True, save=False)
            observed = evidence.get("after_mm", {}).get("current")
            evidence["verified"] = evidence.get("success") is True and _finite(observed) and abs(observed-value) <= 1e-6
            return evidence

        def save_working(self, path):
            self.ensure_owned()
            path = Path(path).resolve()
            if self.owned_path:
                if Path(self.owned_path).resolve() != path:
                    raise RuntimeError("Working path cannot change during checkpoint save")
                ok = self.c.save_document(self.model)
            else:
                if path.exists():
                    raise FileExistsError(path)
                ok = self.c.save_document(self.model, str(path))
                self.owned_path = str(self.c.get_com_member(self.model, "GetPathName"))
            # SolidWorks Save3 can normalize a .sldprt suffix to .SLDPRT.
            actual_path = str(self.c.get_com_member(self.model, "GetPathName"))
            if Path(actual_path).resolve() == path:
                self.owned_path = actual_path
            if not ok or Path(self.owned_path).resolve() != path or not path.is_file() or not path.stat().st_size:
                raise RuntimeError("Working model save failed")
            self.ensure_owned()

    return ModelBackend, native


def run_request(request, out_dir):
    request = validate_request(request)
    output = Path(out_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": 1, "mode": request["mode"], "status": "failed", "steps": [],
              "checkpoints": [], "feedback": [], "engineering_review_required": True}
    checkpoint_store = CheckpointStore(output / "checkpoints")
    backend = sw = before = None
    original_models, original_contexts, original_identities, original_readers, hashes = [], [], [], [], {}
    working = None

    def write(name, data):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    def fail(code, exc):
        report["status"] = "failed"
        report["feedback"].append({"code": code, "message": f"{type(exc).__name__}: {exc}"})

    write("request.json", request)
    try:
        ModelBackend, native = _native_backend_class()
        with native._execution_lock():
            try:
                sw = native._attach()
                c, _, _, _ = native._helpers()
                before = native.capture_session_context(sw)
                native._validate_inventory(before)
                write("progress.json", {"phase": "protecting_source_documents", "documents": len(before["documents"])})
                original_models = native._resolve_original_models(sw, before["documents"])
                active_id = (before.get("active_document") or {}).get("id")
                lightweight = getattr(native, "capture_document_state", native.capture_model_context)
                original_readers = [native.capture_model_context if info.get("id") == active_id else lightweight
                                    for info in before["documents"]]
                original_contexts = [reader(m) for reader, m in zip(original_readers, original_models)]
                original_identities = [native._document_identity(m) for m in original_models]
                hashes = native._source_files(sw, before)
                working = native._working_directory(sw)
                write("progress.json", {"phase": "executing", "documents": len(before["documents"])})
                report["solidworks_revision"] = str(c.get_com_member(sw, "RevisionNumber"))
                mode = request["mode"]
                working_path = output / ("working_" + uuid.uuid4().hex[:12] + ".sldprt")
                if mode == "create":
                    backend = ModelBackend(sw, before["documents"], original_models=original_models)
                elif mode == "edit":
                    source = Path(request["source"]).resolve()
                    source_hash = native._hash_file(source)
                    if not source_hash.get("exists") or source_hash.get("size", 0) <= 0:
                        raise FileNotFoundError(source)
                    hashes[str(source)] = source_hash
                    for document in before["documents"]:
                        if document.get("path") and Path(document["path"]).resolve() == source and document.get("save_flag"):
                            raise RuntimeError("Source has unsaved changes; save it before editing its disk snapshot")
                    # The same checked exclusive copy primitive is used for input isolation.
                    try:
                        from .sw_checkpoints import _copy_exclusive
                    except ImportError:
                        from sw_checkpoints import _copy_exclusive
                    _copy_exclusive(source, working_path)
                    if native._hash_file(source) != source_hash:
                        raise RuntimeError("Source changed while copying")
                    backend = ModelBackend.open_owned(sw, before["documents"], original_models, working_path)
                else:
                    origin = CheckpointStore(Path(request["checkpoint_root"]))
                    saved = origin.get(request["checkpoint_id"])
                    origin.restore(saved["id"], working_path)
                    backend = ModelBackend.open_owned(sw, before["documents"], original_models, working_path)
                    evidence = compare_checkpoint_context(saved["context"], backend.snapshot())
                    report["restore_validation"] = evidence
                    if not evidence["passed"]:
                        raise RuntimeError("Restored checkpoint differs from its verified state")

                def checkpoint(label):
                    backend.save_working(working_path)
                    entry = checkpoint_store.create(working_path, label=label, context=backend.snapshot(),
                              metadata={"mode": mode, "sketches": dict(backend.sketches)})
                    entry["root"] = str(checkpoint_store.root)
                    report["checkpoints"].append(entry)
                    write("progress.json", {"phase": "checkpoint_saved", "label": label, "checkpoint_id": entry["id"]})
                    return entry

                if mode == "create":
                    def record(event):
                        with (output / "events.jsonl").open("a", encoding="utf-8") as handle:
                            handle.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")
                        if event["attempt"].get("passed"):
                            checkpoint(event["step"])
                    source_context = native.capture_model_context(c.get_com_member(sw, "ActiveDoc"))
                    if before.get("active_document"):
                        active_index = next((i for i, ctx in enumerate(original_contexts)
                                             if ctx["document"].get("id") == before["active_document"].get("id")), None)
                        source_context = original_contexts[active_index] if active_index is not None else None
                    else:
                        source_context = None
                    outcome = execute_plan(request["plan"], backend, source_context=source_context, event_sink=record)
                    report.update({k: v for k, v in outcome.items() if k not in {"feedback", "schema_version"}})
                    report["feedback"].extend(outcome.get("feedback", []))
                elif mode == "edit":
                    health = _part_health(backend.snapshot())
                    if not all(item["passed"] for item in health):
                        raise RuntimeError("Source part lacks healthy geometry or fully defined parametric sketches")
                    checkpoint("before_edit")
                    outcome = execute_edits(request, backend, checkpoint)
                    report.update({k: v for k, v in outcome.items() if k != "feedback"})
                    report["feedback"].extend(outcome.get("feedback", []))
                else:
                    checkpoint("restored_checkpoint")
                    report["final_context"] = backend.snapshot()
                    checks = [c for req in request["requirements"] for c in check_expectations(report["final_context"], req)]
                    report["final_checks"] = checks
                    report["status"] = "passed" if all(item["passed"] for item in checks) else "needs_revision"

                if report["status"] == "passed":
                    report["final_context"] = backend.snapshot()
                    if not all(c["passed"] for c in _part_health(report["final_context"])):
                        raise RuntimeError("Final part health failed")
                    report["delivery"] = backend.deliver(output)
                    if report["delivery"].get("review_evaluation", {}).get("status") not in {"pass", "warn"}:
                        raise RuntimeError("Delivery review failed")
            except Exception as exc:
                fail("modeling_failed", exc)
            finally:
                if backend is not None and report["status"] != "passed" and report["checkpoints"]:
                    try:
                        backend.close()
                        last = checkpoint_store.get(report["checkpoints"][-1]["id"])
                        recovered_path = output / ("recovered_" + uuid.uuid4().hex[:12] + ".sldprt")
                        checkpoint_store.restore(last["id"], recovered_path)
                        backend = ModelBackend.open_owned(sw, before["documents"], original_models, recovered_path)
                        context = backend.snapshot()
                        evidence = compare_checkpoint_context(last["context"], context)
                        report["recovery"] = {**evidence, "checkpoint_id": last["id"], "native": str(recovered_path), "context": context}
                        if not evidence["passed"]:
                            raise RuntimeError("Recovery geometry/parameters differ from checkpoint")
                        report["status"] = "recovered"
                        report["task_succeeded"] = False
                    except Exception as exc:
                        fail("recovery_failed", exc)
                if backend is not None:
                    try:
                        backend.close()
                    except Exception as exc:
                        fail("owned_close_failed", exc)
                if sw is not None and before is not None:
                    try:
                        native._restore_active(sw, before.get("active_document"))
                    except Exception as exc:
                        fail("active_restore_failed", exc)
                    checks = []
                    try:
                        after = native.capture_session_context(sw)
                        protection = native.compare_protection(before, after, hashes,
                                                              {p: native._hash_file(p) for p in hashes})
                        checks.extend(protection["checks"])
                        for model, original, identity, reader in zip(original_models, original_contexts, original_identities, original_readers):
                            checks.append({"check": "original_model_unchanged", "document": original["document"],
                                           "passed": native._document_identity(model) == identity
                                           and native._context_evidence(original) == native._context_evidence(reader(model))})
                        now = native._working_directory(sw)
                        if working is not None:
                            checks.append({"check": "working_directory_restored", "passed": working == now})
                        report["source_protection"] = {"passed": protection["passed"] and all(c["passed"] for c in checks), "checks": checks,
                            "scope": "all original COM identities, document metadata, selections and enumerated disk files; original active model geometry/features only; no claim about unenumerated dependencies"}
                        if not report["source_protection"]["passed"]:
                            fail("source_protection_failed", RuntimeError("Original document/file state changed or is unavailable"))
                    except Exception as exc:
                        report["source_protection"] = {"passed": False, "checks": checks}
                        fail("source_protection_error", exc)
    except Exception as exc:
        fail("session_failed", exc)
    report["task_succeeded"] = report["status"] == "passed"
    write("modeling_report.json", report)
    return report


def inspect_source(source):
    """Read a saved part without changing its active document, geometry or selections."""
    ModelBackend, native = _native_backend_class()
    with native._execution_lock():
        sw = native._attach()
        path = str(Path(source).resolve())
        model = sw.GetOpenDocumentByName(path)
        if model is None:
            raise ValueError("Open the source in SolidWorks first; inspect never opens or activates files")
        c, _, _, _ = native._helpers()
        if c.get_com_member(model, "GetType") != 1:
            raise ValueError("inspect supports parts only")
        proxy = ModelBackend.__new__(ModelBackend)
        proxy.model, proxy.c = model, c
        _, proxy.part, proxy.review, proxy.export = native._helpers()
        return proxy.snapshot()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "run"):
        p = commands.add_parser(name)
        p.add_argument("--request", required=True)
        if name == "run":
            p.add_argument("--out-dir", required=True)
    p = commands.add_parser("inspect")
    p.add_argument("--source", required=True)
    p = commands.add_parser("checkpoints")
    p.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "checkpoints":
            value = CheckpointStore(args.root).list()
        elif args.command == "inspect":
            with redirect_stdout(sys.stderr):
                value = inspect_source(args.source)
        else:
            request = json.loads(Path(args.request).read_text(encoding="utf-8-sig"))
            value = validate_request(request)
            if args.command == "run":
                with redirect_stdout(sys.stderr):
                    report = run_request(value, args.out_dir)
                value = {"status": report["status"], "task_succeeded": report["task_succeeded"],
                         "report": str(Path(args.out_dir).resolve() / "modeling_report.json")}
        print(json.dumps(value, ensure_ascii=False, allow_nan=False))
        return 0 if args.command != "run" or value["task_succeeded"] else 2
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
