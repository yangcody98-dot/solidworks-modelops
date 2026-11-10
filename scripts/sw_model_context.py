"""Read-only SolidWorks snapshots for planning the next modeling operation.

This module never connects to SolidWorks, changes selections, resolves components,
rebuilds, or changes views. The caller supplies an existing COM document/session.
Unknown data stays ``None`` with a warning; it is never replaced with zero.

Geometry uses the same SI-to-mm convention as sw_review, but deliberately avoids
importing that module: its import initializes COM dependencies, and its broader
review entry points rebuild and change views. Only solid bodies are totaled here.
GetPartBox/GetBodyBox/GetBox bounds are approximate, not dimensional tolerances.
"""
from __future__ import annotations

import hashlib
import json
import math
import ntpath
from typing import Any


_MISSING = object()
_MAX_SESSION_DOCUMENTS = 4096  # Large assemblies can load >1000 part documents.


def _member(obj: Any, name: str, *args: Any) -> Any:
    """Support getters exposed as either methods or pywin32 properties."""
    value = getattr(obj, name)
    if not callable(value):
        return value
    if getattr(value, "_oleobj_", None) is not None:
        # CDispatch properties themselves are callable, but their default member
        # is not the getter we intend to read. Never invoke that default member.
        return value
    try:
        return value(*args)
    except Exception as exc:
        # A COM object returned by a property can look callable. Calling its
        # nonexistent default member must not discard the actual property value.
        message = str(exc)
        if not args and any(token in message for token in (
            "-2147352573", "Member not found", "找不到成员",
        )):
            return value
        raise


def _read(obj: Any, names: str | tuple[str, ...], warnings: list[str], label: str,
          *args: Any) -> Any:
    names = (names,) if isinstance(names, str) else names
    failures = []
    for name in names:
        try:
            return _member(obj, name, *args)
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    warnings.append(f"{label} unavailable ({'; '.join(failures)})")
    return _MISSING


def _text(value: Any, warnings: list[str], label: str) -> str | None:
    if value is _MISSING:
        return None
    if isinstance(value, str):
        return value
    warnings.append(f"{label} unavailable: expected text")
    return None


def _integer(value: Any, warnings: list[str], label: str) -> int | None:
    if value is _MISSING:
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    warnings.append(f"{label} unavailable: expected integer")
    return None


def _boolean(value: Any, warnings: list[str], label: str) -> bool | None:
    if value is _MISSING:
        return None
    if isinstance(value, (bool, int)) and value in (False, True, -1):
        return bool(value)
    warnings.append(f"{label} unavailable: expected boolean")
    return None


def _numbers(value: Any, length: int, warnings: list[str], label: str) -> list[float] | None:
    if value is _MISSING:
        return None
    try:
        if isinstance(value, (str, bytes)) or len(value) != length:
            raise ValueError(f"expected {length} coordinates")
        result = [float(item) for item in value]
        if not all(math.isfinite(item) for item in result):
            raise ValueError("non-finite value")
        return result
    except (TypeError, ValueError, OverflowError) as exc:
        warnings.append(f"{label} unavailable: {exc}")
        return None


def _bbox(value: Any, warnings: list[str], label: str) -> list[float] | None:
    result = _numbers(value, 6, warnings, label)
    if result is None:
        return None
    if any(result[index] > result[index + 3] for index in range(3)):
        warnings.append(f"{label} unavailable: minimum exceeds maximum")
        return None
    converted = [item * 1000.0 for item in result]
    if not all(math.isfinite(item) for item in converted):
        warnings.append(f"{label} unavailable: conversion overflow")
        return None
    return converted


def _document(model: Any, warnings: list[str], label: str = "document") -> dict:
    document = {
        "id": None,
        "title": _text(_read(model, "GetTitle", warnings, f"{label}.title"), warnings, f"{label}.title"),
        "path": _text(_read(model, "GetPathName", warnings, f"{label}.path"), warnings, f"{label}.path"),
        "type": _integer(_read(model, "GetType", warnings, f"{label}.type"), warnings, f"{label}.type"),
        "save_flag": _boolean(_read(model, "GetSaveFlag", warnings, f"{label}.save_flag"), warnings, f"{label}.save_flag"),
        "configuration": None,
    }
    # Drawings have sheets instead of an active part/assembly configuration.
    if document["type"] != 3:
        manager = _read(model, "ConfigurationManager", warnings, f"{label}.configuration_manager")
        if manager is not _MISSING:
            configuration = _read(manager, "ActiveConfiguration", warnings, f"{label}.active_configuration")
            if configuration is not _MISSING:
                document["configuration"] = _text(
                    _read(configuration, "Name", warnings, f"{label}.configuration"),
                    warnings, f"{label}.configuration",
                )
    if document["path"] or document["title"]:
        # An observation identity, not a SolidWorks persistent-reference ID.
        identity = {
            "path": ntpath.normcase(ntpath.normpath(document["path"])) if document["path"] else None,
            "title": document["title"],
            "type": document["type"],
            "configuration": document["configuration"],
        }
        document["id"] = hashlib.sha256(
            json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()[:24]
    return document


def _features(model: Any, limit: int, warnings: list[str]) -> tuple[list[dict], bool]:
    result: list[dict] = []
    feature = _read(model, "FirstFeature", warnings, "features.first")
    seen = set()
    visited = []  # Keep proxies alive so Python cannot recycle their id values.
    while feature is not _MISSING and feature is not None:
        if len(result) >= limit:
            warnings.append(f"features truncated at feature_limit={limit}; top-level features only")
            return result, False
        if id(feature) in seen:
            warnings.append("features traversal stopped: repeated COM object")
            return result, False
        seen.add(id(feature))
        visited.append(feature)
        label = f"features[{len(result)}]"
        # GetErrorCode is a parameterless read-only API. GetErrorCode2 has a
        # by-ref Boolean; generated pywin32 wrappers may return (code, warning).
        error = _read(feature, ("GetErrorCode", "GetErrorCode2"), warnings, f"{label}.error_code")
        if isinstance(error, (tuple, list)) and error:
            error = error[0]
        result.append({
            "name": _text(_read(feature, "Name", warnings, f"{label}.name"), warnings, f"{label}.name"),
            "type": _text(_read(feature, ("GetTypeName2", "GetTypeName"), warnings, f"{label}.type"), warnings, f"{label}.type"),
            "error_code": _integer(error, warnings, f"{label}.error_code"),
        })
        feature = _read(feature, "GetNextFeature", warnings, f"{label}.next")
    return result, feature is None


def _selection(model: Any, warnings: list[str]) -> dict:
    result: dict = {"count": None, "objects": [], "complete": False}
    manager = _read(model, ("SelectionManager", "ISelectionManager"), warnings, "selection.manager")
    if manager is _MISSING:
        return result
    count = _integer(_read(manager, "GetSelectedObjectCount2", warnings, "selection.count", -1), warnings, "selection.count")
    if count is None:
        return result
    if count < 0:
        warnings.append("selection.count unavailable: negative count")
        return result
    result["count"] = count
    result["complete"] = True
    for index in range(1, count + 1):
        label = f"selection.objects[{index - 1}]"
        kind = _integer(_read(manager, "GetSelectedObjectType3", warnings, f"{label}.type", index, -1), warnings, f"{label}.type")
        selected = _read(manager, "GetSelectedObject6", warnings, f"{label}.object", index, -1)
        name = None
        if selected is not _MISSING and selected is not None:
            name = _text(_read(selected, ("Name2", "Name", "GetName"), warnings, f"{label}.name"), warnings, f"{label}.name")
        elif selected is None:
            warnings.append(f"{label}.object unavailable: returned None")
        if name is None or kind is None:
            result["complete"] = False
        result["objects"].append({"index": index, "type": kind, "name": name})
    return result


def _geometry(model: Any, document_type: int | None, warnings: list[str]) -> dict:
    result: dict = {
        "status": "unavailable", "scope": "solid_bodies", "bbox_mm": None,
        "bbox_size_mm": None, "bbox_approximate": True, "bbox_source": None,
        "volume_mm3": None, "body_count": None, "measured_body_count": 0, "bodies": [],
    }
    if document_type == 3:
        result["status"] = "not_applicable"
        return result
    if document_type not in (1, 2):
        warnings.append("geometry unavailable: document type is unknown or unsupported")
        return result
    if document_type == 2:
        result["scope"] = "assembly_bounds_only"
        result["bbox_mm"] = _bbox(_read(model, "GetBox", warnings, "geometry.bbox_mm", 0), warnings, "geometry.bbox_mm")
        result["bbox_source"] = "IAssemblyDoc.GetBox(0)" if result["bbox_mm"] is not None else None
        warnings.append("geometry assembly body_count/volume_mm3 not collected; components are not resolved or traversed")
    else:
        result["bbox_mm"] = _bbox(_read(model, "GetPartBox", warnings, "geometry.bbox_mm", True), warnings, "geometry.bbox_mm")
        if result["bbox_mm"] is not None:
            result["bbox_source"] = "IPartDoc.GetPartBox(True)"
        bodies = _read(model, "GetBodies2", warnings, "geometry.bodies", 0, False)
        if bodies is not _MISSING:
            if bodies is None:
                bodies = []  # A successful null SAFEARRAY means no solid bodies.
            if not isinstance(bodies, (list, tuple)):
                warnings.append("geometry.bodies unavailable: expected SAFEARRAY/list/tuple")
            else:
                result["body_count"] = len(bodies)
                for index, body in enumerate(bodies):
                    label = f"geometry.bodies[{index}]"
                    box = _bbox(_read(body, "GetBodyBox", warnings, f"{label}.bbox_mm"), warnings, f"{label}.bbox_mm")
                    mass = _read(body, "GetMassProperties", warnings, f"{label}.mass_properties", 1.0)
                    volume = None
                    if mass is not _MISSING:
                        try:
                            # IBody2.GetMassProperties: [COMx, COMy, COMz, volume,
                            # area, mass, ...]. SI volume m^3 -> mm^3, solid only.
                            if not isinstance(mass, (list, tuple)) or len(mass) < 4:
                                raise ValueError("expected at least four mass-property values")
                            volume = float(mass[3]) * 1_000_000_000.0
                            if not math.isfinite(volume) or volume < 0:
                                raise ValueError("non-finite or negative volume")
                        except (TypeError, ValueError, OverflowError) as exc:
                            warnings.append(f"{label}.volume_mm3 unavailable: {exc}")
                            volume = None
                    result["bodies"].append({"index": index, "bbox_mm": box, "volume_mm3": volume})
                    if volume is not None:
                        result["measured_body_count"] += 1
                if result["measured_body_count"] == len(bodies):
                    total = sum(body["volume_mm3"] for body in result["bodies"])
                    if math.isfinite(total):
                        result["volume_mm3"] = total
                    else:
                        warnings.append("geometry.volume_mm3 unavailable: total overflow")
                if result["bbox_mm"] is None and bodies and all(body["bbox_mm"] is not None for body in result["bodies"]):
                    boxes = [body["bbox_mm"] for body in result["bodies"]]
                    result["bbox_mm"] = [min(box[axis] for box in boxes) for axis in range(3)] + [max(box[axis] for box in boxes) for axis in range(3, 6)]
                    result["bbox_source"] = "union of IBody2.GetBodyBox() solid bounds"
    if result["bbox_mm"] is not None:
        box = result["bbox_mm"]
        result["bbox_size_mm"] = [box[axis + 3] - box[axis] for axis in range(3)]
    if result["body_count"] is not None and result["volume_mm3"] is not None and result["bbox_mm"] is not None:
        result["status"] = "available"
    elif result["bbox_mm"] is not None or result["body_count"] is not None:
        result["status"] = "partial"
    return result


def capture_model_context(model: Any, *, include_geometry: bool = True, feature_limit: int = 200) -> dict:
    """Capture an existing model without modifying its state.

    ``document.type`` and selection object ``type`` retain SolidWorks enum values.
    Features are top-level only. ``document.id`` is a stable hash of observed
    path/title/type/configuration, not a persistent CAD entity reference. All
    geometry lengths and solid volumes are normalized to mm and mm^3.
    """
    if isinstance(feature_limit, bool) or not isinstance(feature_limit, int) or feature_limit < 0:
        raise ValueError("feature_limit must be a non-negative integer")
    warnings: list[str] = []
    document = _document(model, warnings)
    features, complete = _features(model, feature_limit, warnings)
    selection = _selection(model, warnings)
    geometry = _geometry(model, document["type"], warnings) if include_geometry else {
        "status": "not_requested", "scope": "solid_bodies", "bbox_mm": None,
        "bbox_size_mm": None, "bbox_approximate": True, "bbox_source": None,
        "volume_mm3": None, "body_count": None, "measured_body_count": 0, "bodies": [],
    }
    return {"document": document, "units": {"length": "mm", "volume": "mm^3"},
            "features": features, "features_complete": complete, "feature_scope": "top_level",
            "selection": selection, "geometry": geometry, "warnings": warnings}


def capture_document_state(model: Any) -> dict:
    """Read metadata and selections only, without feature/geometry traversal.

    Suitable for protecting hundreds of background documents in a large
    assembly. This does not claim to verify their complete in-memory geometry.
    """
    warnings: list[str] = []
    return {"document": _document(model, warnings), "selection": _selection(model, warnings),
            "warnings": warnings, "scope": "document metadata and selection only"}


def capture_session_context(sw: Any) -> dict:
    """Return minimal metadata for open documents without activating any of them."""
    warnings: list[str] = []
    active = _read(sw, ("ActiveDoc", "IActiveDoc2"), warnings, "active_document")
    active_document = _document(active, warnings, "active_document") if active is not _MISSING and active is not None else None
    documents: list[dict] = []
    first = _read(sw, "GetFirstDocument", warnings, "documents.first")
    complete = False
    if first is _MISSING:
        items = _read(sw, "GetDocuments", warnings, "documents")
        if items is None:
            complete = True
        elif isinstance(items, (tuple, list)):
            for index, model in enumerate(items[:_MAX_SESSION_DOCUMENTS]):
                documents.append(_document(model, warnings, f"documents[{index}]"))
            complete = len(items) <= _MAX_SESSION_DOCUMENTS
            if not complete:
                warnings.append(f"documents truncated at {_MAX_SESSION_DOCUMENTS}")
        elif items is not _MISSING:
            warnings.append("documents unavailable: expected SAFEARRAY/list/tuple")
    else:
        model, seen = first, set()
        visited = []
        while model is not _MISSING and model is not None:
            if len(documents) >= _MAX_SESSION_DOCUMENTS or id(model) in seen:
                warnings.append("documents traversal stopped: repeated COM object or document limit")
                break
            seen.add(id(model))
            visited.append(model)
            documents.append(_document(model, warnings, f"documents[{len(documents)}]"))
            model = _read(model, "GetNext", warnings, "documents.next")
        else:
            complete = model is None
    return {"active_document": active_document, "documents": documents,
            "documents_complete": complete, "warnings": warnings}
