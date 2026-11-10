"""Reopen an exported STEP in an isolated owned document and compare real geometry."""
from __future__ import annotations

import math
import ntpath
from pathlib import Path


def compare_step_context(context, reopened, *, position_tolerance_mm=0.05, volume_tolerance_mm3=0.1):
    old, new = context.get("geometry", {}), reopened.get("geometry", {})
    required = ("volume_mm3", "bbox_mm", "body_count")
    if any(g.get(k) is None for g in (old, new) for k in required):
        details = {"imported_type": reopened.get("document", {}).get("type"),
                   "geometry": {k: new.get(k) for k in required}, "warnings": reopened.get("warnings", [])}
        raise RuntimeError(f"Geometry evidence is incomplete for STEP comparison: {details}")
    checks = {
        "solid_count": new["body_count"] == old["body_count"] and new["body_count"] > 0,
        "volume": math.isfinite(new["volume_mm3"]) and math.isfinite(old["volume_mm3"])
                  and abs(new["volume_mm3"] - old["volume_mm3"]) <= volume_tolerance_mm3,
        "bounds_and_position": len(old["bbox_mm"]) == len(new["bbox_mm"]) == 6
              and all(math.isfinite(a) and math.isfinite(b) and abs(a - b) <= position_tolerance_mm
                      for a, b in zip(old["bbox_mm"], new["bbox_mm"])),
    }
    result = {"passed": all(checks.values()), "checks": checks, "reopened": reopened,
              "reader": "SolidWorks LoadFile4; separate imported document",
              "position_tolerance_mm": position_tolerance_mm, "volume_tolerance_mm3": volume_tolerance_mm3}
    if not result["passed"]:
        raise RuntimeError(f"STEP geometry differs from native part: {checks}")
    return result


def validate_step_against_context(sw, path, context, protected_documents):
    try:
        from . import sw_connect as c
        from .sw_model_context import capture_model_context
    except ImportError:
        import sw_connect as c
        from sw_model_context import capture_model_context
    protected_titles = {d["title"].casefold() for d in protected_documents}
    protected_paths = {ntpath.normcase(ntpath.normpath(d["path"]))
                       for d in protected_documents if d.get("path")}

    def identity(model):
        if model is None:
            raise RuntimeError("STEP document COM identity is unavailable")
        try:
            return model._oleobj_.QueryInterface(c.pythoncom.IID_IUnknown)
        except Exception as exc:
            raise RuntimeError("Cannot establish STEP document canonical COM identity") from exc

    def location(model):
        title = c.get_com_member(model, "GetTitle")
        document_path = c.get_com_member(model, "GetPathName")
        if not isinstance(title, str) or not title or not isinstance(document_path, str):
            raise RuntimeError("STEP import title/path evidence is unavailable")
        if (title.casefold() in protected_titles or
                (document_path and ntpath.normcase(ntpath.normpath(document_path)) in protected_paths)):
            raise RuntimeError("STEP import identity collides with a protected document")
        return title, document_path

    documents = c.get_com_member(sw, "GetDocuments")
    if not documents and protected_documents:
        raise RuntimeError("Original document identities are unavailable before STEP import")
    existing = list(documents or [])
    existing_identities = [identity(doc) for doc in existing]
    # Include every currently open document, not only the caller's protection list.
    for doc in existing:
        title = c.get_com_member(doc, "GetTitle")
        document_path = c.get_com_member(doc, "GetPathName")
        if not isinstance(title, str) or not title or not isinstance(document_path, str):
            raise RuntimeError("Original document title/path is unavailable before STEP import")
        protected_titles.add(title.casefold())
        if document_path:
            protected_paths.add(ntpath.normcase(ntpath.normpath(document_path)))
    imported = None
    imported_identity = None
    owned = False
    original_directory = c.get_com_member(sw, "GetCurrentWorkingDirectory")
    if not isinstance(original_directory, str) or not original_directory or not ntpath.isabs(original_directory):
        raise RuntimeError("Original SolidWorks working directory is unavailable before STEP import")
    import_directory = str(Path(path).resolve().parent)
    directory_change_attempted = False
    result = None

    def directory_matches(actual, expected):
        return (isinstance(actual, str) and bool(actual)
                and ntpath.normcase(ntpath.normpath(actual)) == ntpath.normcase(ntpath.normpath(expected)))

    try:
        # Imported child documents can inherit this directory as their proposed save path.
        # Change application state only, limiting all such paths to this run's output.
        directory_change_attempted = True
        if not c.get_com_member(sw, "SetCurrentWorkingDirectory", import_directory):
            raise RuntimeError("Could not set the STEP import working directory")
        if not directory_matches(c.get_com_member(sw, "GetCurrentWorkingDirectory"), import_directory):
            raise RuntimeError("STEP import working-directory readback differs from the output directory")
        data = sw.GetImportFileData(str(path))
        if data is None:
            raise RuntimeError("STEP importer returned no import data")
        error = c.VARIANT(c.pythoncom.VT_BYREF | c.pythoncom.VT_I4, 0)
        # Same verified LoadFile4 signature used by sw_connect; no template/export preference changes.
        imported = sw.LoadFile4(str(Path(path).resolve()), "r", data, error)
        if imported is None:
            raise RuntimeError(f"STEP reopen failed: {error.value}")
        imported_identity = identity(imported)
        if imported_identity in existing_identities:
            raise RuntimeError("STEP import returned an already-open document")
        # Establish ownership with minimal reads before richer context capture can fail.
        location(imported)
        owned = True
        reopened = capture_model_context(imported)
        info = reopened["document"]
        if info["type"] == 2:
            # SW may import a single-part STEP as an assembly. Traverse only this
            # task-owned imported assembly, never resolve/modify source components.
            components = c.get_com_member(imported, "GetComponents", False)
            if not components:
                raise RuntimeError("Imported STEP assembly has no readable components")
            parts = []
            for component in components:
                model = c.get_com_member(component, "GetModelDoc2")
                if model is None:
                    raise RuntimeError("Imported STEP component is unloaded; complete geometry cannot be verified")
                if identity(model) in existing_identities:
                    raise RuntimeError("Imported STEP component reuses an already-open document; independent evidence unavailable")
                child = capture_model_context(model)
                if child["document"]["type"] == 2:
                    continue  # GetComponents(False) already includes descendants.
                g = child["geometry"]
                if child["document"]["type"] != 1 or g.get("volume_mm3") is None or g.get("body_count") is None:
                    raise RuntimeError("Imported STEP component has incomplete solid evidence")
                transform = c.get_com_member(component, "Transform2")
                values = c.get_com_member(transform, "ArrayData") if transform is not None else None
                if (values is None or len(values) < 13 or not math.isfinite(float(values[12]))
                        or abs(float(values[12]) - 1) > 1e-9):
                    raise RuntimeError("Imported component transform has unknown/nonunit scale")
                parts.append({"name": str(c.get_com_member(component, "Name2")), "geometry": g})
            if not parts:
                raise RuntimeError("Imported STEP assembly contains no measured solid parts")
            reopened["geometry"].update({"body_count": sum(p["geometry"]["body_count"] for p in parts),
                "volume_mm3": sum(p["geometry"]["volume_mm3"] for p in parts),
                "scope": "loaded components of task-owned STEP import", "component_measurements": parts})
        result = compare_step_context(context, reopened)
        return result
    finally:
        cleanup_error = None
        try:
            if owned:
                title, document_path = location(imported)
                if identity(imported) != imported_identity or imported_identity in existing_identities:
                    raise RuntimeError("STEP cleanup refused: imported document identity changed")
                # CloseDoc uses a title, so the current title lookup must identify this exact
                # owned COM object even when a full path is also available.
                by_title = sw.GetOpenDocumentByName(title)
                if by_title is None:
                    # Unsaved imported assemblies are not always found by this API.
                    # Enumerate the live document set, requiring a unique title and identity.
                    matches = [doc for doc in (c.get_com_member(sw, "GetDocuments") or [])
                               if c.get_com_member(doc, "GetTitle") == title]
                    by_title = matches[0] if len(matches) == 1 else None
                if by_title is None or identity(by_title) != imported_identity:
                    raise RuntimeError("STEP cleanup refused: title no longer identifies the owned import")
                if document_path:
                    by_path = sw.GetOpenDocumentByName(document_path)
                    if by_path is None and c.get_com_member(by_title, "GetPathName") == document_path:
                        by_path = by_title
                    if by_path is None or identity(by_path) != imported_identity:
                        raise RuntimeError("STEP cleanup refused: path no longer identifies the owned import")
                sw.CloseDoc(title)
        except Exception as exc:
            cleanup_error = exc
            raise
        finally:
            # Never let an import/measurement/CloseDoc failure skip restoration.
            if directory_change_attempted:
                try:
                    if not c.get_com_member(sw, "SetCurrentWorkingDirectory", original_directory):
                        raise RuntimeError("SetCurrentWorkingDirectory returned false")
                    restored = c.get_com_member(sw, "GetCurrentWorkingDirectory")
                    if not directory_matches(restored, original_directory):
                        raise RuntimeError(f"readback differs from original directory: {restored!r}")
                except Exception as exc:
                    prior = f"; document cleanup also failed: {cleanup_error}" if cleanup_error is not None else ""
                    raise RuntimeError(f"STEP working-directory restoration failed: {exc}{prior}") from exc
                if result is not None:
                    result["import_working_directory"] = {
                        "before": original_directory, "temporary": import_directory,
                        "after": restored, "restored": True,
                    }
