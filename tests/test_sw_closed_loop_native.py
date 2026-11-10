"""Native ownership and source-protection tests using fake COM documents only."""
from __future__ import annotations

import copy
from contextlib import nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sw_closed_loop_native as native  # noqa: E402
from sw_plan_bridge import PlanValidationError  # noqa: E402


def minimal_plan():
    return {"schema_version": 1, "name": "isolated", "operations": [
        {"id": "profile", "op": "sketch_rectangle", "params": {
            "plane": "Front Plane", "cx_mm": 0, "cy_mm": 0, "width_mm": 20, "height_mm": 10}},
        {"id": "body", "op": "extrude_boss", "params": {"sketch_id": "profile", "depth_mm": 2}},
    ], "requirements": [{"body_count": 1}]}


class FakeDoc:
    def __init__(self, title, path="", dirty=False, doc_type=1):
        self.title, self.path, self.dirty, self.doc_type = title, path, dirty, doc_type
        self.configuration = "Default"
        self.writes = []
        self.app = None
        self.geometry = {"body_count": 1, "volume_mm3": 400,
                         "bbox_mm": [0, 0, 0, 20, 10, 2], "bbox_size_mm": [20, 10, 2]}

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return self.path

    def GetDependencies2(self, *_args):
        return []

    def GetNext(self):
        if self.app is None or self not in self.app.documents:
            return None
        index = self.app.documents.index(self) + 1
        return self.app.documents[index] if index < len(self.app.documents) else None

    def ForceRebuild3(self, top_only):
        self.writes.append(("rebuild", top_only))
        return True

    def ClearSelection2(self, all_marks):
        self.writes.append(("clear_selection", all_marks))


class FakeApp:
    def __init__(self, original):
        self.documents = [original]
        self.ActiveDoc = original
        self.closed = []
        self.activations = []
        self.created = []
        self.new_document_override = None
        original.app = self
        self.working_directory = "C:/original_working_directory"

    def GetCurrentWorkingDirectory(self):
        return self.working_directory

    def GetFirstDocument(self):
        return self.documents[0] if self.documents else None

    def GetDocuments(self):
        return list(self.documents)

    def NewDocument(self, _template, _paper_size, _width, _height):
        if self.new_document_override is not None:
            document = self.new_document_override()
        else:
            document = FakeDoc("NewTaskPart")
            document.app = self
            self.documents.append(document)
            self.created.append(document)
        self.ActiveDoc = document
        return document

    def GetOpenDocumentByName(self, path):
        return next((d for d in self.documents if d.path == path or d.title == path), None)

    def CloseDoc(self, title):
        self.closed.append(title)
        self.documents = [d for d in self.documents if d.title != title]
        if self.ActiveDoc and self.ActiveDoc.title == title:
            self.ActiveDoc = None

    def ActivateDoc3(self, title, use_user_preferences, rebuild_option, error):
        self.activations.append((title, use_user_preferences, rebuild_option))
        self.ActiveDoc = next((d for d in self.documents if d.title == title), None)
        return self.ActiveDoc


def doc_info(doc):
    return {"title": doc.title, "path": doc.path, "type": doc.doc_type,
            "save_flag": doc.dirty, "configuration": doc.configuration}


def session_info(app):
    return {"documents_complete": True, "documents": [doc_info(d) for d in app.documents],
            "active_document": doc_info(app.ActiveDoc) if app.ActiveDoc is not None else None}


@pytest.fixture
def environment(monkeypatch, tmp_path):
    source_path = tmp_path / "source.sldprt"
    source_path.write_bytes(b"existing model bytes must stay unchanged")
    original = FakeDoc("Source", str(source_path), dirty=True)
    app = FakeApp(original)

    def member(obj, name, *args):
        value = getattr(obj, name)
        return value(*args) if callable(value) else value

    def new_document(sw, doc_type):
        assert doc_type == "part"
        return sw.NewDocument("fake_part.prtdot", 0, 0, 0)

    connect = SimpleNamespace(
        get_com_member=member, new_document=new_document, mm=lambda x: x / 1000,
        find_template=lambda _app, kind: "fake_part.prtdot",
        VARIANT=lambda _kind, value: SimpleNamespace(value=value),
        pythoncom=SimpleNamespace(VT_BYREF=0x4000, VT_I4=3),
    )
    monkeypatch.setattr(native, "_helpers", lambda: (connect, SimpleNamespace(), SimpleNamespace(), SimpleNamespace()))
    monkeypatch.setattr(native, "_attach", lambda: app)
    monkeypatch.setattr(native, "_execution_lock", nullcontext)
    monkeypatch.setattr(native, "capture_session_context", session_info)
    monkeypatch.setattr(native, "capture_document_state", lambda doc: {
        "document": doc_info(doc), "selection": {"count": 0, "objects": [], "complete": True},
        "warnings": [], "scope": "document metadata and selection only"})
    monkeypatch.setattr(native, "capture_model_context", lambda doc, **_kw: {
        "document": doc_info(doc), "geometry": copy.deepcopy(doc.geometry), "features": [], "features_complete": True,
        "selection": {"count": 0, "objects": [], "complete": True}})
    return SimpleNamespace(app=app, source=original, source_path=source_path, connect=connect)


def test_valid_source_state_ignores_task_owned_additional_document(environment):
    app = environment.app
    before = session_info(app)
    files = {str(environment.source_path): native._hash_file(environment.source_path)}
    app.documents.append(FakeDoc("task_owned"))
    report = native.compare_protection(before, session_info(app), files, copy.deepcopy(files))
    assert report["passed"] is True
    assert report["document_count"] == 1
    assert report["file_count"] == 1


@pytest.mark.parametrize("changed", ["dirty", "configuration", "closed", "active", "file", "inventory"])
def test_source_change_is_a_protection_failure(environment, changed):
    app, doc = environment.app, environment.source
    before = session_info(app)
    files = {str(environment.source_path): native._hash_file(environment.source_path)}
    if changed == "dirty":
        doc.dirty = False
    elif changed == "configuration":
        doc.configuration = "Changed"
    elif changed == "closed":
        app.documents = []
    elif changed == "active":
        app.ActiveDoc = FakeDoc("other")
    elif changed == "file":
        environment.source_path.write_bytes(b"unexpected replacement")
    after = session_info(app)
    if changed == "inventory":
        after["documents_complete"] = False
    files_after = {str(environment.source_path): native._hash_file(environment.source_path)}
    assert native.compare_protection(before, after, files, files_after)["passed"] is False


def test_new_document_fallback_to_existing_source_is_rejected_before_writes(environment):
    environment.connect.new_document = lambda *_args: environment.source
    environment.app.new_document_override = lambda: environment.source
    with pytest.raises(RuntimeError):
        native.NativePartBackend(environment.app, session_info(environment.app)["documents"])
    assert environment.source.writes == []
    assert environment.app.closed == []


def test_saved_or_nonpart_document_cannot_become_owned_target(environment):
    environment.connect.new_document = lambda *_args: FakeDoc("not_new", "C:/already_saved.sldprt")
    environment.app.new_document_override = lambda: FakeDoc("not_new", "C:/already_saved.sldprt")
    with pytest.raises(RuntimeError):
        native.NativePartBackend(environment.app, session_info(environment.app)["documents"])
    environment.connect.new_document = lambda *_args: FakeDoc("assembly", doc_type=2)
    environment.app.new_document_override = lambda: FakeDoc("assembly", doc_type=2)
    with pytest.raises(RuntimeError):
        native.NativePartBackend(environment.app, session_info(environment.app)["documents"])


def test_switching_active_document_blocks_before_model_write(environment):
    backend = native.NativePartBackend(environment.app, session_info(environment.app)["documents"])
    own = backend.model
    environment.app.ActiveDoc = environment.source
    with pytest.raises(RuntimeError, match="Active document changed"):
        backend.execute(minimal_plan()["operations"][0])
    with pytest.raises(RuntimeError, match="Active document changed"):
        backend.rebuild()
    assert environment.source.writes == own.writes == []
    backend.close()
    assert environment.app.closed == ["NewTaskPart"]
    assert environment.source in environment.app.documents


def test_owned_path_drift_blocks_and_does_not_close_foreign_document(environment):
    backend = native.NativePartBackend(environment.app, session_info(environment.app)["documents"])
    backend.model.path = str(environment.source_path)
    with pytest.raises(RuntimeError, match="not the task-owned part"):
        backend.ensure_owned()
    backend.close()
    assert environment.app.closed == []


def test_unsupported_plan_rejected_before_attach_create_or_output(monkeypatch, tmp_path):
    monkeypatch.setattr(native, "_attach", lambda: pytest.fail("unsupported plan must not attach"))
    plan = minimal_plan()
    plan["operations"][1]["op"] = "unsupported_fillet"
    output = tmp_path / "no_output"
    with pytest.raises(PlanValidationError):
        native.run_native(plan, output)
    assert not output.exists()


def test_native_failure_restores_active_document_without_rebuilding_source(environment, monkeypatch, tmp_path):
    def fail_execution(*_args, **_kwargs):
        raise RuntimeError("deliberate fake backend failure")
    monkeypatch.setattr(native, "execute_plan", fail_execution)
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert report["source_protection"]["passed"] is True
    assert environment.source.writes == []
    assert environment.app.ActiveDoc is environment.source
    assert environment.app.closed == ["NewTaskPart"]
    assert environment.app.activations == [("Source", False, 1)]
    assert (tmp_path / "run" / "run_report.json").is_file()


def test_run_reports_protection_failure_even_when_execution_only_needs_revision(environment, monkeypatch, tmp_path):
    def changed_source(*_args, **_kwargs):
        environment.source.dirty = False
        return {"status": "needs_revision", "feedback": []}
    monkeypatch.setattr(native, "execute_plan", changed_source)
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert report["source_protection"]["passed"] is False


def test_original_document_fallback_run_never_saves_rebuilds_or_closes_source(environment, tmp_path):
    environment.connect.new_document = lambda *_args: environment.source
    environment.app.new_document_override = lambda: environment.source
    before = environment.source_path.read_bytes()
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert report["source_protection"]["passed"] is True
    assert environment.source_path.read_bytes() == before
    assert environment.source.writes == []
    assert environment.app.closed == []


def test_incomplete_inventory_blocks_before_creating_document(environment, monkeypatch, tmp_path):
    def incomplete(app):
        result = session_info(app)
        result["documents_complete"] = False
        return result
    monkeypatch.setattr(native, "capture_session_context", incomplete)
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert (tmp_path / "run" / "run_report.json").is_file()
    assert environment.app.created == []
    assert environment.source.writes == []


def test_foreign_active_object_with_identical_title_and_path_is_rejected(environment):
    backend = native.NativePartBackend(environment.app, session_info(environment.app)["documents"])
    impostor = FakeDoc(backend.model.title, backend.model.path)
    environment.app.ActiveDoc = impostor
    with pytest.raises(RuntimeError):
        backend.rebuild()
    assert impostor.writes == backend.model.writes == []


def test_original_identity_cannot_become_owned_by_changing_title_and_path(environment):
    original_info = session_info(environment.app)["documents"]
    def return_renamed_original():
        environment.source.title = "PretendNewPart"
        environment.source.path = ""
        return environment.source
    environment.app.new_document_override = return_renamed_original
    with pytest.raises(RuntimeError):
        native.NativePartBackend(environment.app, original_info)
    assert environment.source.writes == []
    assert environment.app.closed == []


def test_close_failure_does_not_skip_active_restore_or_report(environment, monkeypatch, tmp_path):
    monkeypatch.setattr(native, "execute_plan", lambda *_a, **_kw: {"status": "needs_revision", "feedback": []})
    def broken_close(_title):
        raise RuntimeError("test task close failure")
    monkeypatch.setattr(environment.app, "CloseDoc", broken_close)
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert environment.app.ActiveDoc is environment.source
    assert environment.app.activations == [("Source", False, 1)]
    assert (tmp_path / "run" / "run_report.json").is_file()


def test_source_geometry_change_detected_even_when_dirty_flag_and_file_are_unchanged(environment, monkeypatch, tmp_path):
    def change_geometry(*_args, **_kwargs):
        environment.source.geometry["volume_mm3"] = 399
        return {"status": "needs_revision", "feedback": []}
    monkeypatch.setattr(native, "execute_plan", change_geometry)
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert report["source_protection"]["passed"] is False
    assert environment.source.dirty is True


def test_post_session_capture_failure_still_restores_and_writes_report(environment, monkeypatch, tmp_path):
    calls = 0
    def unreliable_session(app):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("post-run inventory unavailable")
        return session_info(app)
    monkeypatch.setattr(native, "capture_session_context", unreliable_session)
    monkeypatch.setattr(native, "execute_plan", lambda *_a, **_kw: {"status": "needs_revision", "feedback": []})
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert report["source_protection"]["passed"] is False
    assert any(f["code"] == "source_snapshot_failed" for f in report["feedback"])
    assert environment.app.ActiveDoc is environment.source
    assert (tmp_path / "run" / "run_report.json").is_file()


def test_post_hash_failure_still_writes_protection_failure_report(environment, monkeypatch, tmp_path):
    calls = 0
    original_hash = native._hash_file
    def unreliable_hash(path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("post-run hash unavailable")
        return original_hash(path)
    monkeypatch.setattr(native, "_hash_file", unreliable_hash)
    monkeypatch.setattr(native, "execute_plan", lambda *_a, **_kw: {"status": "needs_revision", "feedback": []})
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert report["source_protection"]["passed"] is False
    assert any(f["code"] == "source_hash_failed" for f in report["feedback"])
    assert environment.app.ActiveDoc is environment.source
    assert (tmp_path / "run" / "run_report.json").is_file()


@pytest.mark.parametrize("evaluation", [None, {}, {"status": "fail"}, {"status": "unknown"}])
def test_missing_or_failed_delivery_review_cannot_pass(environment, monkeypatch, tmp_path, evaluation):
    monkeypatch.setattr(native, "execute_plan", lambda *_a, **_kw: {"status": "passed", "feedback": []})
    monkeypatch.setattr(native.NativePartBackend, "deliver", lambda *_a: {"review_evaluation": evaluation})
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "needs_revision"
    assert report["source_protection"]["passed"] is True
    assert report["feedback"][0]["code"] == "delivery_review_failed"


def test_attach_failure_is_reported_without_creating_a_document(environment, monkeypatch, tmp_path):
    def attach_failure():
        raise RuntimeError("SolidWorks unavailable")
    monkeypatch.setattr(native, "_attach", attach_failure)
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert (tmp_path / "run" / "run_report.json").is_file()
    assert environment.app.created == []


def test_working_directory_change_is_not_claimed_unchanged(environment, monkeypatch, tmp_path):
    def changed_working_directory(*_a, **_kw):
        environment.app.working_directory = "C:/unexpected_directory"
        return {"status": "needs_revision", "feedback": []}
    monkeypatch.setattr(native, "execute_plan", changed_working_directory)
    report = native.run_native(minimal_plan(), tmp_path / "run")
    assert report["status"] == "failed"
    assert any(c.get("check") == "original_working_directory_unchanged" and c["passed"] is False
               for c in report["source_protection"]["checks"])


def test_unsaved_owned_part_can_close_via_live_identity_when_name_lookup_returns_none(environment, monkeypatch):
    app = environment.app
    backend = native.NativePartBackend(app, [doc_info(environment.source)])
    owned = backend.model
    monkeypatch.setattr(app, "GetOpenDocumentByName", lambda _name: None)
    backend.close()
    assert owned.title in app.closed
    assert environment.source in app.documents
    assert environment.source.writes == []


def test_loaded_internal_document_is_uniquely_resolved_without_name_lookup(environment, monkeypatch):
    app = environment.app
    internal = FakeDoc("InternalAssembly", "C:/loaded/internal.sldasm", doc_type=2)
    internal.app = app
    app.documents.append(internal)
    expected = [doc_info(environment.source), doc_info(internal)]
    lookup = app.GetOpenDocumentByName
    monkeypatch.setattr(app, "GetOpenDocumentByName", lambda name: None if name == internal.path else lookup(name))
    monkeypatch.setattr(native, "capture_model_context", lambda *_a, **_kw: pytest.fail("Must not scan original features/geometry"))
    models = native._resolve_original_models(app, expected)
    assert models == [environment.source, internal]
    assert internal.writes == environment.source.writes == []
    assert app.created == app.closed == app.activations == []


def test_failed_lookups_share_one_enumeration_index(environment, monkeypatch):
    app = environment.app
    internal = [FakeDoc(f"Internal{i}", f"C:/loaded/internal{i}.sldasm", doc_type=2) for i in range(4)]
    app.documents.extend(internal)
    calls = []
    def enumerate_once():
        calls.append("GetDocuments")
        return tuple(app.documents)
    monkeypatch.setattr(app, "GetOpenDocumentByName", lambda _name: None)
    monkeypatch.setattr(app, "GetDocuments", enumerate_once)
    assert native._resolve_original_models(app, [doc_info(doc) for doc in app.documents]) == app.documents
    assert calls == ["GetDocuments"]


def test_duplicate_enumerated_metadata_is_rejected_instead_of_selecting_first(environment, monkeypatch):
    app = environment.app
    duplicate = FakeDoc(environment.source.title, environment.source.path)
    app.documents.append(duplicate)
    monkeypatch.setattr(app, "GetOpenDocumentByName", lambda _name: None)
    with pytest.raises(RuntimeError, match="uniquely identify.*matches=2"):
        native._resolve_original_models(app, [doc_info(environment.source)])
    assert app.created == app.closed == app.activations == []


def test_missing_enumerated_document_is_rejected(environment, monkeypatch):
    monkeypatch.setattr(environment.app, "GetOpenDocumentByName", lambda _name: None)
    monkeypatch.setattr(environment.app, "GetDocuments", lambda: [])
    with pytest.raises(RuntimeError, match="uniquely identify.*matches=0"):
        native._resolve_original_models(environment.app, [doc_info(environment.source)])
    assert environment.app.created == []


def test_nonmatching_nonnull_name_lookup_still_blocks_inventory(environment, monkeypatch):
    impostor = FakeDoc("Different", "C:/other.sldprt")
    monkeypatch.setattr(environment.app, "GetOpenDocumentByName", lambda _name: impostor)
    with pytest.raises(RuntimeError, match="identity changed"):
        native._resolve_original_models(environment.app, [doc_info(environment.source)])
    assert environment.app.created == []


def test_enumerated_fallback_keeps_canonical_identity_validation(environment, monkeypatch):
    monkeypatch.setattr(environment.app, "GetOpenDocumentByName", lambda _name: None)
    def identity_unavailable(_model):
        raise RuntimeError("Cannot establish canonical COM document identity")
    monkeypatch.setattr(native, "_document_identity", identity_unavailable)
    with pytest.raises(RuntimeError, match="canonical COM"):
        native._resolve_original_models(environment.app, [doc_info(environment.source)])
    assert environment.app.created == []


def test_duplicate_original_com_identity_is_rejected_even_when_metadata_matches(environment):
    info = doc_info(environment.source)
    with pytest.raises(RuntimeError, match="duplicate identities"):
        native._resolve_original_models(environment.app, [info, dict(info)])


def test_unhashable_canonical_identity_keeps_duplicate_guard(environment, monkeypatch):
    monkeypatch.setattr(native, "_document_identity", lambda _model: ("com", ["same-IUnknown"]))
    info = doc_info(environment.source)
    with pytest.raises(RuntimeError, match="duplicate identities"):
        native._resolve_original_models(environment.app, [info, dict(info)])


@pytest.mark.parametrize("items", [123, "not documents"])
def test_malformed_fallback_enumeration_is_rejected(environment, monkeypatch, items):
    monkeypatch.setattr(environment.app, "GetOpenDocumentByName", lambda _name: None)
    monkeypatch.setattr(environment.app, "GetDocuments", lambda: items)
    with pytest.raises(RuntimeError, match="SAFEARRAY"):
        native._resolve_original_models(environment.app, [doc_info(environment.source)])


@pytest.mark.parametrize("reported_path", [
    "C:/ModelOps/working_uuid.SLDPRT",
    "c:/modelops/WORKING_UUID.sldprt",
    r"c:\ModelOps\working_uuid.SLDPRT",
])
def test_owned_saved_path_accepts_windows_case_and_separator_normalization(environment, reported_path):
    backend = native.NativePartBackend(environment.app, [doc_info(environment.source)])
    backend.owned_path = "C:/ModelOps/working_uuid.sldprt"
    backend.model.path = reported_path
    assert backend._owned_metadata() == (reported_path, backend.model.title)
    backend.ensure_owned()
    assert backend.model.writes == environment.source.writes == []


@pytest.mark.parametrize("reported_path", [
    "C:/ModelOps/another.SLDPRT",
    "C:/Other/working_uuid.SLDPRT",
])
def test_owned_saved_path_still_rejects_a_different_windows_file(environment, reported_path):
    backend = native.NativePartBackend(environment.app, [doc_info(environment.source)])
    backend.owned_path = "C:/ModelOps/working_uuid.sldprt"
    backend.model.path = reported_path
    with pytest.raises(RuntimeError, match="path_changed"):
        backend.ensure_owned()
    backend.close()
    assert environment.app.closed == []
    assert backend.model.writes == environment.source.writes == []


def test_source_files_hashes_all_open_paths_but_walks_active_dependencies_only_once(environment, monkeypatch, tmp_path):
    app = environment.app
    backgrounds = []
    for index in range(4):
        path = tmp_path / f"background_{index}.sldprt"
        path.write_bytes(f"background {index}".encode())
        background = FakeDoc(f"Background{index}", str(path))
        backgrounds.append(background)
        app.documents.append(background)
    app.documents.append(FakeDoc("UnsavedBackground"))
    dependency = tmp_path / "active_recursive_dependency.sldprt"
    dependency.write_bytes(b"referenced but not loaded")
    dependency_calls, lookup_calls, hash_calls = [], [], []
    def active_dependencies(*args):
        dependency_calls.append(args)
        # SOLIDWORKS may interleave a display name and path, and repeat paths.
        return ["ReferencedPart", str(dependency), str(dependency), str(environment.source_path)]
    monkeypatch.setattr(environment.source, "GetDependencies2", active_dependencies)
    def forbidden_background_walk(*_args):
        pytest.fail("Background documents must not recursively enumerate the assembly graph")
    for background in backgrounds:
        monkeypatch.setattr(background, "GetDependencies2", forbidden_background_walk)
    lookup = app.GetOpenDocumentByName
    def counted_lookup(path):
        lookup_calls.append(path)
        return lookup(path)
    monkeypatch.setattr(app, "GetOpenDocumentByName", counted_lookup)
    original_hash = native._hash_file
    def counted_hash(path):
        hash_calls.append(str(path))
        return original_hash(path)
    monkeypatch.setattr(native, "_hash_file", counted_hash)
    result = native._source_files(app, session_info(app))
    expected = {str(environment.source_path), str(dependency), *(doc.path for doc in backgrounds)}
    assert set(result) == expected
    assert set(hash_calls) == expected and len(hash_calls) == len(expected)
    assert all(value["exists"] and value["size"] > 0 and len(value["sha256"]) == 64 for value in result.values())
    assert dependency_calls == [(True, False, False)]
    assert lookup_calls == [str(environment.source_path)]
    assert app.created == app.closed == app.activations == []
    assert environment.source.writes == []


def test_source_files_without_active_document_still_hashes_every_saved_open_file(environment, monkeypatch):
    session = session_info(environment.app)
    session["active_document"] = None
    def forbidden_lookup(_name):
        pytest.fail("No active source exists to enumerate dependencies")
    monkeypatch.setattr(environment.app, "GetOpenDocumentByName", forbidden_lookup)
    result = native._source_files(environment.app, session)
    assert set(result) == {str(environment.source_path)}
    assert result[str(environment.source_path)] == native._hash_file(environment.source_path)


def test_active_dependency_failure_preserves_hashes_of_open_files(environment, monkeypatch):
    def unavailable(*_args):
        raise RuntimeError("dependency enumeration unavailable")
    monkeypatch.setattr(environment.source, "GetDependencies2", unavailable)
    result = native._source_files(environment.app, session_info(environment.app))
    assert set(result) == {str(environment.source_path)}
    assert result[str(environment.source_path)] == native._hash_file(environment.source_path)
    assert environment.app.created == environment.app.closed == environment.app.activations == []
