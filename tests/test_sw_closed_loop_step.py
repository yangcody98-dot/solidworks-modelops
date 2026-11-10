"""STEP evidence and document ownership checks, entirely with fake COM objects."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sw_closed_loop_step as step  # noqa: E402


def context(*, title="Imported", path="", doc_type=1):
    return {"document": {"title": title, "path": path, "type": doc_type},
            "geometry": {"body_count": 1, "volume_mm3": 200.0,
                         "bbox_mm": [-5.0, -5.0, 0.0, 5.0, 5.0, 2.0]},
            "warnings": []}


def test_matching_solid_geometry_passes():
    original = context()
    result = step.compare_step_context(original, copy.deepcopy(original))
    assert result["passed"] is True
    assert all(result["checks"].values())


@pytest.mark.parametrize("change", ["wireframe", "volume", "position", "count", "nan_volume", "nan_bbox"])
def test_incorrect_or_nonfinite_step_geometry_is_rejected(change):
    original, reopened = context(), context()
    geometry = reopened["geometry"]
    if change == "wireframe":
        geometry.update(body_count=0, volume_mm3=0)
    elif change == "volume":
        geometry["volume_mm3"] += 1
    elif change == "position":
        # Keep size identical: a displaced STEP must still fail.
        geometry["bbox_mm"][0] += 1
        geometry["bbox_mm"][3] += 1
    elif change == "count":
        geometry["body_count"] = 2
    elif change == "nan_volume":
        geometry["volume_mm3"] = float("nan")
    else:
        geometry["bbox_mm"][0] = float("nan")
    with pytest.raises(RuntimeError, match="differs"):
        step.compare_step_context(original, reopened)


@pytest.mark.parametrize("side", ["native", "reopened"])
@pytest.mark.parametrize("field", ["body_count", "volume_mm3", "bbox_mm"])
def test_missing_geometry_evidence_is_not_a_pass(side, field):
    original, reopened = context(), context()
    (original if side == "native" else reopened)["geometry"][field] = None
    with pytest.raises(RuntimeError, match="incomplete"):
        step.compare_step_context(original, reopened)


class FakeOle:
    def __init__(self, identity):
        self.identity = identity

    def QueryInterface(self, _iid):
        return self.identity


class FakeDoc:
    def __init__(self, title, *, identity=None, path="", doc_type=1):
        self.title, self.path, self.doc_type = title, path, doc_type
        self._oleobj_ = FakeOle(object() if identity is None else identity)
        self.components = []

    def GetTitle(self):
        return self.title

    def GetPathName(self):
        return self.path

    def GetComponents(self, top_level_only):
        assert top_level_only is False
        return self.components


class FakeApp:
    def __init__(self, source, imported):
        self.documents = [source]
        self.imported = imported
        self.closed = []
        self.working_directory = "C:\\existing\\"
        self.directory_changes = []
        self.load_directories = []

    def GetCurrentWorkingDirectory(self):
        return self.working_directory

    def SetCurrentWorkingDirectory(self, directory):
        self.directory_changes.append(directory)
        self.working_directory = directory.rstrip("/\\") + "\\"
        return True

    def GetDocuments(self):
        return list(self.documents)

    def GetImportFileData(self, _path):
        return object()

    def LoadFile4(self, _path, arg, _data, _error):
        assert arg == "r"
        self.load_directories.append(self.working_directory)
        if self.imported not in self.documents:
            self.documents.append(self.imported)
        return self.imported

    def GetOpenDocumentByName(self, value):
        return next((doc for doc in self.documents if value in (doc.title, doc.path)), None)

    def CloseDoc(self, title):
        target = next((doc for doc in self.documents if doc.title == title), None)
        self.closed.append(target)
        if target is not None:
            self.documents.remove(target)


@pytest.fixture
def importer(monkeypatch):
    source = FakeDoc("Original", path="C:/existing/Original.sldprt")
    imported = FakeDoc("Imported")
    app = FakeApp(source, imported)

    def member(obj, name, *args):
        value = getattr(obj, name)
        return value(*args) if callable(value) else value

    connect = SimpleNamespace(get_com_member=member,
        VARIANT=lambda _kind, value: SimpleNamespace(value=value),
        pythoncom=SimpleNamespace(VT_BYREF=0x4000, VT_I4=3, IID_IUnknown="IUnknown"))

    def capture(doc):
        return context(title=doc.title, path=doc.path, doc_type=doc.doc_type)

    context_module = SimpleNamespace(capture_model_context=capture)
    monkeypatch.setitem(sys.modules, "sw_connect", connect)
    monkeypatch.setitem(sys.modules, "sw_model_context", context_module)
    protected = [capture(source)["document"]]
    return SimpleNamespace(app=app, source=source, imported=imported, connect=connect,
                           context_module=context_module, protected=protected)


def validate(importer, tmp_path):
    return step.validate_step_against_context(importer.app, tmp_path / "unique_exchange.step",
                                               context(title="Native"), importer.protected)


def test_success_closes_only_the_separate_imported_document(importer, tmp_path):
    assert validate(importer, tmp_path)["passed"] is True
    assert importer.app.closed == [importer.imported]
    assert importer.app.documents == [importer.source]


def test_existing_com_identity_is_rejected_even_with_different_wrapper_and_name(importer, tmp_path):
    importer.imported._oleobj_.identity = importer.source._oleobj_.identity
    importer.imported.title = "AnAliasWithAnotherTitle"
    with pytest.raises(RuntimeError, match="already-open"):
        validate(importer, tmp_path)
    assert importer.app.closed == []
    assert importer.source in importer.app.documents


@pytest.mark.parametrize("field", ["title", "path"])
def test_protected_name_or_path_collision_never_closes_source(importer, tmp_path, field):
    setattr(importer.imported, field, getattr(importer.source, field))
    with pytest.raises(RuntimeError, match="protected"):
        validate(importer, tmp_path)
    assert importer.app.closed == []
    assert importer.source in importer.app.documents


def test_failed_geometry_validation_still_closes_owned_import(importer, tmp_path):
    capture = importer.context_module.capture_model_context

    def wrong_volume(doc):
        result = capture(doc)
        result["geometry"]["volume_mm3"] = 300
        return result

    importer.context_module.capture_model_context = wrong_volume
    with pytest.raises(RuntimeError, match="differs"):
        validate(importer, tmp_path)
    assert importer.app.closed == [importer.imported]
    assert importer.source in importer.app.documents


def test_context_capture_failure_closes_only_new_import(importer, tmp_path):
    def unavailable(_doc):
        raise RuntimeError("fake context read failed")

    importer.context_module.capture_model_context = unavailable
    with pytest.raises(RuntimeError, match="fake context read failed"):
        validate(importer, tmp_path)
    assert importer.app.closed == [importer.imported]
    assert importer.source in importer.app.documents


def test_close_rechecks_import_identity_when_title_changes(importer, tmp_path, monkeypatch):
    compare = step.compare_step_context

    def title_changed_before_cleanup(*args, **kwargs):
        result = compare(*args, **kwargs)
        importer.imported.title = importer.source.title
        return result

    monkeypatch.setattr(step, "compare_step_context", title_changed_before_cleanup)
    try:
        validate(importer, tmp_path)
    except RuntimeError:
        pass  # A safe refusal to close is expected when the title becomes ambiguous.
    assert importer.source not in importer.app.closed
    assert importer.source in importer.app.documents


def test_imported_assembly_unloaded_component_is_rejected_without_resolve(importer, tmp_path):
    importer.imported.doc_type = 2
    importer.imported.components = [SimpleNamespace(GetModelDoc2=lambda: None)]
    with pytest.raises(RuntimeError, match="unloaded"):
        validate(importer, tmp_path)
    assert importer.app.closed == [importer.imported]
    assert importer.source in importer.app.documents


def test_loaded_component_reusing_source_cannot_supply_independent_evidence(importer, tmp_path):
    importer.imported.doc_type = 2
    importer.imported.components = [SimpleNamespace(GetModelDoc2=lambda: importer.source)]
    with pytest.raises(RuntimeError, match="already-open"):
        validate(importer, tmp_path)
    assert importer.app.closed == [importer.imported]
    assert importer.source in importer.app.documents


@pytest.mark.parametrize("scale", [2.0, float("nan")])
def test_imported_assembly_nonunit_or_unknown_scale_is_rejected(importer, tmp_path, scale):
    child = FakeDoc("ImportedChild")
    importer.imported.doc_type = 2
    importer.imported.components = [SimpleNamespace(GetModelDoc2=lambda: child,
        Transform2=SimpleNamespace(ArrayData=[1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0, 0, 0, 0, scale]),
        Name2="ImportedChild-1")]
    with pytest.raises(RuntimeError, match="scale"):
        validate(importer, tmp_path)
    assert importer.app.closed == [importer.imported]


def test_new_loaded_imported_part_components_supply_independent_evidence(importer, tmp_path):
    child = FakeDoc("ImportedChild")
    importer.imported.doc_type = 2
    importer.imported.components = [SimpleNamespace(GetModelDoc2=lambda: child,
        Transform2=SimpleNamespace(ArrayData=[1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0]),
        Name2="ImportedChild-1")]
    result = validate(importer, tmp_path)
    assert result["passed"] is True
    assert result["reopened"]["geometry"]["body_count"] == 1
    assert importer.app.closed == [importer.imported]


def test_unknown_existing_inventory_prevents_import(importer, tmp_path):
    importer.app.GetDocuments = lambda: None
    with pytest.raises(RuntimeError, match="unavailable before STEP import"):
        validate(importer, tmp_path)
    assert importer.app.documents == [importer.source]
    assert importer.app.closed == []


def test_cleanup_refuses_different_com_object_resolved_by_same_title(importer, tmp_path, monkeypatch):
    compare = step.compare_step_context
    other = FakeDoc(importer.imported.title)

    def switch_title_lookup(*args, **kwargs):
        result = compare(*args, **kwargs)
        importer.app.documents.insert(0, other)
        return result

    monkeypatch.setattr(step, "compare_step_context", switch_title_lookup)
    with pytest.raises(RuntimeError, match="cleanup refused"):
        validate(importer, tmp_path)
    assert importer.app.closed == []
    assert importer.source in importer.app.documents


def test_missing_named_lookup_uses_unique_enumerated_identity_for_cleanup(importer, tmp_path):
    importer.imported.path = str(tmp_path / "Imported.sldasm")
    importer.app.GetOpenDocumentByName = lambda _name: None
    assert validate(importer, tmp_path)["passed"] is True
    assert importer.app.closed == [importer.imported]
    assert importer.app.documents == [importer.source]


def test_import_uses_output_directory_and_restores_original_with_readback(importer, tmp_path):
    original = importer.app.working_directory
    result = validate(importer, tmp_path)
    assert importer.app.directory_changes == [str(tmp_path.resolve()), original]
    assert importer.app.load_directories == [str(tmp_path.resolve()) + "\\"]
    assert importer.app.working_directory == original
    assert result["import_working_directory"]["restored"] is True
    assert result["import_working_directory"]["after"] == original


def test_close_failure_still_restores_original_working_directory(importer, tmp_path):
    original = importer.app.working_directory

    def fail_close(_title):
        raise RuntimeError("fake CloseDoc failure")

    importer.app.CloseDoc = fail_close
    with pytest.raises(RuntimeError, match="fake CloseDoc failure"):
        validate(importer, tmp_path)
    assert importer.app.working_directory == original
    assert importer.app.directory_changes[-1] == original
    assert importer.source in importer.app.documents


@pytest.mark.parametrize("failure", ["false", "readback", "exception"])
def test_working_directory_restore_failure_is_explicit(importer, tmp_path, failure):
    original = importer.app.working_directory
    setter = importer.app.SetCurrentWorkingDirectory

    def fail_restore(directory):
        if directory == original:
            if failure == "exception":
                raise RuntimeError("fake restore exception")
            if failure == "false":
                return False
            return True  # Misleading success: leave the temporary directory in place.
        return setter(directory)

    importer.app.SetCurrentWorkingDirectory = fail_restore
    with pytest.raises(RuntimeError, match="working-directory restoration failed"):
        validate(importer, tmp_path)
    assert importer.app.closed == [importer.imported]
    assert importer.source in importer.app.documents


def test_failed_initial_directory_set_is_restored_without_import(importer, tmp_path):
    original = importer.app.working_directory
    setter = importer.app.SetCurrentWorkingDirectory

    def failed_set(directory):
        success = setter(directory)
        return success if directory == original else False

    importer.app.SetCurrentWorkingDirectory = failed_set
    with pytest.raises(RuntimeError, match="Could not set"):
        validate(importer, tmp_path)
    assert importer.app.load_directories == []
    assert importer.app.working_directory == original
    assert importer.app.documents == [importer.source]


def test_unknown_original_working_directory_prevents_import_and_setter(importer, tmp_path):
    importer.app.GetCurrentWorkingDirectory = lambda: None
    with pytest.raises(RuntimeError, match="working directory is unavailable"):
        validate(importer, tmp_path)
    assert importer.app.load_directories == []
    assert importer.app.directory_changes == []


def test_combined_cleanup_and_directory_restore_failure_reports_both(importer, tmp_path):
    original = importer.app.working_directory
    setter = importer.app.SetCurrentWorkingDirectory

    def fail_close(_title):
        raise RuntimeError("fake CloseDoc failure")

    def fail_restore(directory):
        return False if directory == original else setter(directory)

    importer.app.CloseDoc = fail_close
    importer.app.SetCurrentWorkingDirectory = fail_restore
    with pytest.raises(RuntimeError, match="restoration failed.*cleanup also failed.*fake CloseDoc failure"):
        validate(importer, tmp_path)
    assert importer.source in importer.app.documents
