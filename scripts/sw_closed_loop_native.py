"""Native adapter for the closed loop. Only newly created parts are writable.

Source documents are observed, hashed, and checked again; never saved, rebuilt,
resolved, closed, or selected by this adapter. Native calls run serially.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import ntpath
from pathlib import Path
import tempfile
import uuid

try:
    from .sw_model_context import capture_document_state, capture_model_context, capture_session_context
    from .sw_closed_loop import execute_plan
    from .sw_plan_bridge import compile_design_plan
except ImportError:
    from sw_model_context import capture_document_state, capture_model_context, capture_session_context
    from sw_closed_loop import execute_plan
    from sw_plan_bridge import compile_design_plan


def _helpers():
    try:
        from . import sw_connect, sw_part, sw_review, sw_export
    except ImportError:
        import sw_connect, sw_part, sw_review, sw_export
    return sw_connect, sw_part, sw_review, sw_export


def _attach():
    c, _, _, _ = _helpers()
    c.pythoncom.CoInitialize()
    # Never launch another SolidWorks instance when the user's session is absent.
    try:
        app = c.win32com_client.GetActiveObject("SldWorks.Application")
        return c.win32com_client.dynamic.DumbDispatch(app._oleobj_, "SldWorks.Application")
    except Exception as exc:
        raise RuntimeError("Open SolidWorks before observing or running a plan.") from exc


@contextmanager
def _execution_lock():
    import msvcrt
    lock_path = Path(tempfile.gettempdir()) / "codex-sw-closed-loop.lock"
    with lock_path.open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Another closed-loop CAD task is running.") from exc
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def _hash_file(path):
    target = Path(path)
    if not target.is_file():
        return {"exists": False}
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for data in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(data)
    stat = target.stat()
    return {"exists": True, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "sha256": digest.hexdigest()}


def _source_files(sw, session):
    c, _, _, _ = _helpers()
    paths = {doc["path"] for doc in session["documents"] if doc.get("path")}
    # Open file paths are already covered above. Enumerate the active source's
    # recursive references once, rather than rewalking the same assembly graph
    # for every loaded part. Unenumerated dependencies are not claimed protected.
    active = session.get("active_document") or {}
    for path in [active.get("path") or active.get("title")]:
        if not path:
            continue
        doc = sw.GetOpenDocumentByName(path)
        if doc is None:
            continue
        try:
            dependencies = c.get_com_member(doc, "GetDependencies2", True, False, False) or []
            for dependency in dependencies:
                candidate = Path(str(dependency))
                if candidate.is_absolute() and candidate.is_file():
                    paths.add(str(candidate))
        except Exception:
            # Open document hashes still provide scoped evidence; don't claim all references.
            pass
    return {path: _hash_file(path) for path in sorted(paths)}


def _document_identity(model):
    """Use canonical IUnknown identity, not a document's mutable name or path."""
    if model is None:
        raise RuntimeError("Document identity is unavailable")
    ole = getattr(model, "_oleobj_", None)
    if ole is None:
        # Pure Python backends are used by offline tests; retain the object too.
        return ("python", id(model))
    c, _, _, _ = _helpers()
    try:
        return ("com", ole.QueryInterface(c.pythoncom.IID_IUnknown))
    except Exception as exc:
        raise RuntimeError("Cannot establish canonical COM document identity") from exc


def _validate_inventory(session):
    documents = session.get("documents", [])
    if session.get("documents_complete") is not True or any(
        not isinstance(d.get("path"), str) or not d.get("title")
        or d.get("type") not in (1, 2, 3) or d.get("save_flag") is None
        for d in documents
    ):
        raise RuntimeError("Original document inventory is incomplete; no CAD writes performed")


def _resolve_original_models(sw, documents):
    """Retain original COM references, including loaded internal/unsaved docs.

    Some loaded assembly documents appear in GetDocuments but cannot be found
    by GetOpenDocumentByName. Build one lightweight metadata index on the first
    failed lookup; ambiguous/missing matches still block all CAD writes.
    """
    models = []
    identities, identity_set = [], set()
    enumerated = None

    def metadata_key(info):
        return tuple(info.get(key) for key in ("path", "title", "type"))

    def enumerated_matches(info):
        nonlocal enumerated
        if enumerated is None:
            try:
                getter = sw.GetDocuments
                items = getter() if callable(getter) else getter
            except Exception as exc:
                raise RuntimeError("Cannot enumerate loaded original documents") from exc
            if items is None:
                items = []
            if not isinstance(items, (list, tuple)):
                raise RuntimeError("Loaded document enumeration must be a SAFEARRAY/list/tuple")
            enumerated = {}
            for candidate in items:
                current = capture_document_state(candidate)["document"]
                if (not isinstance(current.get("path"), str) or not current.get("title")
                        or current.get("type") not in (1, 2, 3)):
                    raise RuntimeError("Loaded document metadata is incomplete during inventory")
                enumerated.setdefault(metadata_key(current), []).append(candidate)
        matches = enumerated.get(metadata_key(info), [])
        if len(matches) != 1:
            raise RuntimeError(f"Cannot uniquely identify original document: {info['title']} "
                               f"(enumerated matches={len(matches)})")
        return matches[0]

    for info in documents:
        try:
            model = sw.GetOpenDocumentByName(info["path"] or info["title"])
        except Exception:
            model = None
        if model is None:
            model = enumerated_matches(info)
        current = capture_document_state(model)["document"]
        if any(current.get(key) != info.get(key) for key in ("path", "title", "type")):
            raise RuntimeError("Original document identity changed during inventory")
        identity = _document_identity(model)  # Canonical IUnknown, never metadata alone.
        try:
            duplicate = identity in identity_set
        except TypeError:
            # Retain equality checks for an unhashable COM proxy implementation.
            duplicate = identity in identities
        if duplicate:
            raise RuntimeError("Original document inventory contains duplicate identities")
        try:
            identity_set.add(identity)
        except TypeError:
            pass
        identities.append(identity)
        models.append(model)
    return models


def _context_evidence(context):
    if context is None:
        return None
    document = context.get("document", {})
    return {
        "document": {key: document.get(key) for key in
                     ("path", "title", "type", "configuration", "save_flag")},
        "geometry": context.get("geometry"),
        "features": context.get("features"),
        "features_complete": context.get("features_complete"),
        "selection": context.get("selection"),
    }


def _working_directory(sw):
    try:
        c, _, _, _ = _helpers()
        value = c.get_com_member(sw, "GetCurrentWorkingDirectory")
        if not isinstance(value, str):
            raise RuntimeError("working-directory getter returned no string")
        return {"available": True, "path": value}
    except Exception as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}


def compare_protection(before, after, file_before, file_after):
    """Compare original docs only; additional task-owned documents are irrelevant."""
    checks = []
    index = {(d.get("path"), d.get("title")): d for d in after["documents"]}
    for doc in before["documents"]:
        current = index.get((doc.get("path"), doc.get("title")))
        keys = ("path", "title", "type", "configuration", "save_flag")
        checks.append({"document": doc.get("path") or doc.get("title"),
                       "passed": current is not None and all(current.get(k) == doc.get(k) for k in keys),
                       "before": doc, "after": current})
    for path, old in file_before.items():
        checks.append({"file": path, "passed": old == file_after.get(path),
                       "before": old, "after": file_after.get(path)})
    active_keys = ("path", "title", "type", "configuration")
    old_active, new_active = before.get("active_document"), after.get("active_document")
    active_ok = (old_active is None and new_active is None) or (
        old_active is not None and new_active is not None
        and all(old_active.get(k) == new_active.get(k) for k in active_keys))
    checks.append({"check": "original_active_document_restored", "passed": active_ok})
    passed = before.get("documents_complete") is True and after.get("documents_complete") is True and all(c["passed"] for c in checks)
    return {"passed": passed, "file_count": len(file_before), "document_count": len(before["documents"]), "checks": checks}


def _restore_active(sw, original):
    if not original:
        return
    c, _, _, _ = _helpers()
    error = c.VARIANT(c.pythoncom.VT_BYREF | c.pythoncom.VT_I4, 0)
    # swDontRebuildActiveDoc=1. Do not use 0 (user decision/rebuild prompt).
    active = sw.ActivateDoc3(original["title"], False, 1, error)
    if active is None:
        raise RuntimeError(f"Could not restore active document: {original['title']} (code {error.value})")


class NativePartBackend:
    """Owns a newly created part, never accepts a source document as write target."""

    def __init__(self, sw, original_documents, original_models=None):
        self.sw = sw
        self.c, self.part, self.review, self.export = _helpers()
        _validate_inventory({"documents_complete": True, "documents": original_documents})
        self.protected_docs = [dict(document) for document in original_documents]
        self.protected = {(d.get("path"), d.get("title")) for d in original_documents}
        self.protected_titles = {d["title"].casefold() for d in original_documents}
        self.original_models = (list(original_models) if original_models is not None
                                else _resolve_original_models(sw, original_documents))
        self.protected_identities = [_document_identity(model) for model in self.original_models]
        self.model = None
        self.sketches = {}
        self.owned_path = ""
        candidate = sw.NewDocument(self.c.find_template(sw, "part"), 0, 0, 0)
        if candidate is None:
            raise RuntimeError("NewDocument returned no new part; source writes blocked.")
        identity = _document_identity(candidate)
        info = capture_model_context(candidate, include_geometry=False)["document"]
        if (identity in self.protected_identities or str(info.get("title", "")).casefold() in self.protected_titles
                or not info.get("title") or info.get("path") != "" or info.get("type") != 1):
            raise RuntimeError("NewDocument did not return a distinct unsaved part; source writes blocked.")
        self.model = candidate
        self.identity = identity
        self.initial_title = info["title"]

    def _owned_metadata(self):
        if self.model is None:
            raise RuntimeError("No task-owned document")
        identity = _document_identity(self.model)
        path = self.c.get_com_member(self.model, "GetPathName")
        title = self.c.get_com_member(self.model, "GetTitle")
        invalid = {"identity_changed": identity != self.identity,
                   "source_identity": identity in self.protected_identities,
                   "metadata_unavailable": not isinstance(path, str) or not isinstance(title, str) or not title,
                   "source_title": isinstance(title, str) and title.casefold() in self.protected_titles,
                   "source_location": (path, title) in self.protected,
                   "path_changed": bool(path and ntpath.normcase(ntpath.normpath(path)) !=
                                        ntpath.normcase(ntpath.normpath(self.owned_path)))}
        if any(invalid.values()):
            raise RuntimeError("Write target is not the task-owned part: " +
                               ", ".join(key for key, value in invalid.items() if value))
        return path, title

    def ensure_owned(self):
        self._owned_metadata()
        active = self.c.get_com_member(self.sw, "ActiveDoc")
        if active is None or _document_identity(active) != self.identity:
            raise RuntimeError("Active document changed; stopped before writing to another model")

    def snapshot(self):
        data = capture_model_context(self.model)
        data["geometry"]["hole_measurements"] = self.review.collect_geometry_measurements(self.model)
        return data

    def execute(self, operation):
        self.ensure_owned()
        p, op = operation["params"], operation["op"]
        if op in ("sketch_rectangle", "sketch_circles"):
            self.model.ClearSelection2(True)
            with self.part.sketch(self.model, p["plane"]) as sketch_name:
                if op == "sketch_rectangle":
                    created = self.part.sketch_rectangle(self.model, self.c.mm(p["cx_mm"]), self.c.mm(p["cy_mm"]),
                        self.c.mm(p["width_mm"]), self.c.mm(p["height_mm"]))
                    ok = created is not None and created is not False
                else:
                    circles = [self.part.sketch_circle(self.model, self.c.mm(circle["x_mm"]), self.c.mm(circle["y_mm"]),
                               self.c.mm(circle["radius_mm"])) for circle in p["circles"]]
                    ok = all(circle is not None and circle is not False for circle in circles)
                constraints = None
                if ok:
                    try:
                        from .sw_sketch_constraints import fully_define_active_sketch
                    except ImportError:
                        from sw_sketch_constraints import fully_define_active_sketch
                    constraints = fully_define_active_sketch(self.model)
                    if not constraints.get("fully_defined") or not constraints.get("parametric_evidence"):
                        raise RuntimeError(f"Sketch requires driving dimensions/relations: {constraints}")
            if ok:
                self.sketches[operation["id"]] = sketch_name
            return {"created": ok, "feature_name": sketch_name, "sketch_constraints": constraints}
        sketch_name = self.sketches[p["sketch_id"]]
        if op == "extrude_boss":
            feature = self.part.extrude_boss(self.model, sketch_name, self.c.mm(p["depth_mm"]))
        elif op == "extrude_cut":
            depth = 0 if p.get("through_all") else self.c.mm(p["depth_mm"])
            feature = self.part.extrude_cut(self.model, sketch_name, depth, reverse=p.get("reverse", False))
        else:
            raise ValueError(f"Unsupported operation: {op}")
        return {"created": feature is not None and feature is not False,
                "feature_name": str(feature.Name) if feature is not None else None}

    def rebuild(self):
        self.ensure_owned()
        return bool(self.model.ForceRebuild3(False))

    def deliver(self, output):
        self.ensure_owned()
        try:
            from .sw_sketch_constraints import collect_sketch_constraint_status
        except ImportError:
            from sw_sketch_constraints import collect_sketch_constraint_status
        sketch_constraints = collect_sketch_constraint_status(self.model)
        if not sketch_constraints.get("all_fully_defined") or not sketch_constraints.get("all_parametric"):
            raise RuntimeError("Sketch definition/parametric evidence failed; no model delivery saved")
        basename = "model_" + uuid.uuid4().hex[:12]
        native = output / (basename + ".sldprt")
        step = output / (basename + "_exchange.step")
        if native.exists() or step.exists():
            raise FileExistsError("Refusing to replace delivery files")
        if not self.c.save_document(self.model, str(native)):
            raise RuntimeError("Native SaveAs failed")
        self.owned_path = str(self.c.get_com_member(self.model, "GetPathName") or "")
        if Path(self.owned_path).resolve() != native.resolve():
            raise RuntimeError("Saved model path differs from the output target")
        self.ensure_owned()
        if not self.export.export_to_step(self.model, str(step)):
            raise RuntimeError("STEP export failed")
        for path in (native, step):
            if not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"Missing or empty output: {path}")
        try:
            from .sw_closed_loop_step import validate_step_against_context
        except ImportError:
            from sw_closed_loop_step import validate_step_against_context
        native_context = self.snapshot()
        try:
            step_evidence = validate_step_against_context(self.sw, step, native_context,
                self.protected_docs + [native_context["document"]])
        finally:
            _restore_active(self.sw, native_context["document"])
        self.ensure_owned()
        report, report_path = self.review.run_review(self.model, str(output / "review"), basename="model",
            expected_outputs=[str(native), str(step)])
        return {"native": str(native), "step": str(step), "review_report": str(report_path),
                "review_evaluation": report.get("evaluation"),
                "step_reopen_validation": step_evidence,
                "sketch_constraints": sketch_constraints,
                "files": {str(p): _hash_file(p) for p in (native, step)}}

    def close(self):
        if self.model is not None:
            try:
                path, title = self._owned_metadata()
            except RuntimeError:
                # Never close a document whose identity/path is no longer task-owned.
                return
            target = self.sw.GetOpenDocumentByName(path or title)
            if target is None and not path:
                # GetOpenDocumentByName may not resolve unsaved parts. Enumerate
                # and require the exact owned COM identity before closing by title.
                candidates = [doc for doc in (self.c.get_com_member(self.sw, "GetDocuments") or [])
                              if _document_identity(doc) == self.identity
                              and self.c.get_com_member(doc, "GetTitle") == title]
                target = candidates[0] if len(candidates) == 1 else None
            if target is None or _document_identity(target) != self.identity:
                raise RuntimeError("Close target no longer identifies the task-owned part")
            self.sw.CloseDoc(title)
            self.model = None


def observe_active():
    with _execution_lock():
        sw = _attach()
        c, _, _, _ = _helpers()
        session = capture_session_context(sw)
        model = c.get_com_member(sw, "ActiveDoc")
        return {"session": session, "model": capture_model_context(model) if model is not None else None}


def run_native(plan, output: Path):
    plan = compile_design_plan(plan)  # Fail unsupported operations before any CAD writes.
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    _write_json(output / "plan.json", plan)
    report = {"status": "failed", "feedback": []}
    sw = backend = before = source = source_context = None
    files_before, working_before = {}, None
    creation_attempted = False

    def record_failure(code, exc):
        report["status"] = "failed"
        report.setdefault("feedback", []).append({"code": code, "message": f"{type(exc).__name__}: {exc}"})

    try:
        with _execution_lock():
            try:
                sw = _attach()
                c, _, _, _ = _helpers()
                before = capture_session_context(sw)
                _validate_inventory(before)
                original_models = _resolve_original_models(sw, before["documents"])
                files_before = _source_files(sw, before)
                source = c.get_com_member(sw, "ActiveDoc")
                if source is not None and _document_identity(source) not in [
                    _document_identity(model) for model in original_models
                ]:
                    raise RuntimeError("Active source is absent from original document inventory")
                source_context = capture_model_context(source) if source is not None else None
                working_before = _working_directory(sw)
                _write_json(output / "source_before.json", {"session": before, "context": source_context,
                            "files": files_before, "working_directory": working_before})
                creation_attempted = True
                backend = NativePartBackend(sw, before["documents"], original_models=original_models)

                def record(event):
                    with (output / "events.jsonl").open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(event, ensure_ascii=False, allow_nan=False) + "\n")

                report = execute_plan(plan, backend, source_context=source_context, event_sink=record)
                try:
                    report["solidworks_revision"] = str(c.get_com_member(sw, "RevisionNumber"))
                except Exception:
                    report["solidworks_revision"] = None
                if report["status"] == "passed":
                    report["delivery"] = backend.deliver(output)
                    evaluation = report["delivery"].get("review_evaluation") or {}
                    if evaluation.get("status") not in {"pass", "warn"}:
                        report["status"] = "needs_revision"
                        report.setdefault("feedback", []).append({"code": "delivery_review_failed", "detail": evaluation})
            except Exception as exc:
                record_failure("native_error", exc)
            finally:
                # Each recovery action is independent: failure to close must not skip activation.
                if backend is not None:
                    try:
                        backend.close()
                    except Exception as exc:
                        record_failure("close_failed", exc)
                if sw is not None and before is not None and creation_attempted:
                    try:
                        _restore_active(sw, before.get("active_document"))
                    except Exception as exc:
                        record_failure("restore_failed", exc)

                after, context_after, working_after, files_after = None, None, None, {}
                if sw is not None:
                    try:
                        after = capture_session_context(sw)
                    except Exception as exc:
                        record_failure("source_snapshot_failed", exc)
                    if source is not None:
                        try:
                            context_after = capture_model_context(source)
                        except Exception as exc:
                            record_failure("source_context_failed", exc)
                    working_after = _working_directory(sw)
                for path in files_before:
                    try:
                        files_after[path] = _hash_file(path)
                    except Exception as exc:
                        record_failure("source_hash_failed", exc)
                        files_after[path] = {"error": f"{type(exc).__name__}: {exc}"}

                protection = {"passed": False, "checks": [], "reason": "Original inventory unavailable"}
                if before is not None and after is not None:
                    try:
                        protection = compare_protection(before, after, files_before, files_after)
                        if source is not None:
                            evidence_before, evidence_after = _context_evidence(source_context), _context_evidence(context_after)
                            protection["checks"].append({"check": "original_model_context_unchanged",
                                "passed": evidence_before is not None and evidence_before == evidence_after,
                                "scope": "captured original active model fields",
                                "before": evidence_before, "after": evidence_after})
                            active_after = c.get_com_member(sw, "ActiveDoc")
                            protection["checks"].append({"check": "original_active_identity_restored",
                                "passed": active_after is not None and
                                          _document_identity(source) == _document_identity(active_after)})
                        if working_before is not None and working_before.get("available"):
                            protection["checks"].append({"check": "original_working_directory_unchanged",
                                "passed": bool(working_after and working_after.get("available")
                                               and working_before["path"] == working_after.get("path")),
                                "before": working_before, "after": working_after})
                        protection["passed"] = protection["passed"] and all(
                            check["passed"] for check in protection["checks"])
                    except Exception as exc:
                        record_failure("source_comparison_failed", exc)
                        protection = {"passed": False, "checks": [], "reason": str(exc)}
                report["source_protection"] = protection
                if not protection["passed"]:
                    report["status"] = "failed"
                try:
                    _write_json(output / "source_after.json", {"session": after, "context": context_after,
                                "files": files_after, "working_directory": working_after})
                except Exception as exc:
                    record_failure("source_report_failed", exc)
    except Exception as exc:
        record_failure("session_failed", exc)
    finally:
        # Even attach/preflight/cleanup failures produce a report when the output is writable.
        _write_json(output / "run_report.json", report)
    return report
