"""Offline acceptance for the unified entry: measured gates and source isolation."""
from __future__ import annotations

from contextlib import nullcontext
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sw_modeling as modeling  # noqa: E402


def context(width=40.0):
    return {
        "document": {"id": "source-id", "title": "source", "path": "", "type": 1,
                     "configuration": "Default", "save_flag": False},
        "geometry": {"status": "available", "body_count": 1, "volume_mm3": width * 100,
                     "bbox_size_mm": [width, 10.0, 10.0], "bbox_mm": [0, 0, 0, width, 10, 10]},
        "features": [{"name": "Base", "type": "Extrusion", "error_code": 0}],
        "features_complete": True,
        "dimensions": {"Width@Sketch1": {"system_value": width / 1000,
                                             "driven_state": 2, "parameter_type": 0}},
        "dimensions_complete": True,
        "sketch_constraints": {"all_fully_defined": True, "all_parametric": True,
                               "sketch_count": 1, "complete": True},
        "selection": {"count": 0, "complete": True, "objects": []},
    }


def edit_request(source, values=(50.0,)):
    return {"schema_version": 1, "mode": "edit", "source": str(source),
            "operations": [{"id": f"width_{index}", "op": "set_dimension",
                            "params": {"name": "Width@Sketch1", "value_mm": value},
                            "expect": {"volume_mm3": value * 100}}
                           for index, value in enumerate(values)],
            "requirements": [{"volume_mm3": values[-1] * 100, "body_count": 1}]}


def test_import_does_not_import_windows_or_native_adapters():
    script = r'''
import builtins, sys
sys.dont_write_bytecode = True
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'pythoncom', 'win32com', 'comtypes', 'sw_closed_loop_native'}:
        raise AssertionError('Unexpected CAD import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import sw_modeling
assert callable(sw_modeling.validate_request)
'''
    completed = subprocess.run([sys.executable, "-c", script, str(ROOT / "scripts")],
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("change", [
    lambda request: request.update(schema_version=True),
    lambda request: request.update(mode="execute_python"),
    lambda request: request.update(operations="set_dimension"),
    lambda request: request["operations"][0].update(op="shell"),
    lambda request: request["operations"][0]["params"].update(value_mm=float("nan")),
    lambda request: request["operations"][0]["params"].update(value_mm=float("inf")),
    lambda request: request["operations"][0]["params"].update(value_mm=True),
    lambda request: request["operations"][0]["params"].update(value_mm="50"),
    lambda request: request["operations"][0]["params"].update(name="D1@Sketch1@document"),
    lambda request: request.update(unrecognized="ignored?"),
    lambda request: request.update(requirements=[]),
])
def test_invalid_requests_fail_before_output_or_cad(tmp_path, monkeypatch, change):
    request = edit_request(tmp_path / "nonexistent.sldprt")
    change(request)
    def unexpected_cad():
        pytest.fail("Invalid input reached native CAD initialization")
    monkeypatch.setattr(modeling, "_native_backend_class", unexpected_cad)
    output = tmp_path / "output"
    with pytest.raises(ValueError):
        modeling.run_request(request, output)
    assert not output.exists()


@pytest.mark.parametrize("requirements", [[{}], [{"description": "should look right"}]])
def test_edit_requires_a_real_final_geometric_assertion(tmp_path, requirements):
    request = edit_request(tmp_path / "source.sldprt")
    request["requirements"] = requirements
    with pytest.raises(ValueError):
        modeling.validate_request(request)


class EditBackend:
    def __init__(self, *, wrong_readback_at=None, health_failure_at=None):
        self.state = context()
        self.calls = []
        self.wrong_readback_at = wrong_readback_at
        self.health_failure_at = health_failure_at

    def snapshot(self):
        return copy.deepcopy(self.state)

    def set_dimension(self, name, value):
        self.calls.append((name, value))
        self.state = context(value)
        if len(self.calls) == self.health_failure_at:
            self.state["features"][0]["error_code"] = 7
        return {"verified": len(self.calls) != self.wrong_readback_at,
                "after_mm": {"current": value if len(self.calls) != self.wrong_readback_at else value - 1}}


def test_execute_edits_checks_geometry_and_checkpoints_only_accepted_steps(tmp_path):
    request = modeling.validate_request(edit_request(tmp_path / "source.sldprt", (50, 60)))
    backend = EditBackend()
    saved = []
    outcome = modeling.execute_edits(request, backend, saved.append)
    assert outcome["status"] == "passed"
    assert saved == ["width_0", "width_1"]
    assert len(backend.calls) == 2
    assert outcome["final_context"]["geometry"]["volume_mm3"] == 6000
    assert all(check["passed"] for check in outcome["final_checks"])


@pytest.mark.parametrize("failure", ["readback", "feature_health", "geometry"])
def test_partial_edit_failure_stops_later_operations_and_preserves_last_good_checkpoint(tmp_path, failure):
    request = modeling.validate_request(edit_request(tmp_path / "source.sldprt", (50, 60, 70)))
    backend = EditBackend(wrong_readback_at=2 if failure == "readback" else None,
                          health_failure_at=2 if failure == "feature_health" else None)
    if failure == "geometry":
        request["operations"][1]["expect"]["volume_mm3"] = 12345
    saved = []
    outcome = modeling.execute_edits(request, backend, saved.append)
    assert outcome["status"] == "needs_revision"
    assert saved == ["width_0"]
    assert len(backend.calls) == 2
    assert outcome["steps"][0]["status"] == "passed"
    assert outcome["steps"][1]["status"] == "needs_revision"
    # The failing call did mutate geometry. The outer entry must recover it;
    # execute_edits must not pretend rollback or run the third change.
    assert outcome["final_context"]["geometry"]["volume_mm3"] == 6000


def test_final_requirements_cannot_be_replaced_by_successful_intermediate_checks(tmp_path):
    request = modeling.validate_request(edit_request(tmp_path / "source.sldprt"))
    request["requirements"] = [{"volume_mm3": 6000}]
    outcome = modeling.execute_edits(request, EditBackend(), lambda _label: None)
    assert outcome["steps"][0]["status"] == "passed"
    assert outcome["status"] == "needs_revision"
    assert any(not check["passed"] for check in outcome["final_checks"])


def test_restore_comparison_ignores_file_identity_but_checks_model_position():
    expected, actual = context(), context()
    actual["document"].update(path="another.sldprt", title="another", id="other-id")
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is True
    actual["geometry"]["bbox_mm"] = [1, 0, 0, 41, 10, 10]
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is False


@pytest.mark.parametrize("missing", ["geometry", "dimensions", "features", "sketch_constraints"])
def test_restore_comparison_rejects_missing_evidence_even_if_both_sides_lack_it(missing):
    expected, actual = context(), context()
    expected.pop(missing)
    actual.pop(missing)
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is False


@pytest.mark.parametrize("missing", ["driven_state", "parameter_type"])
def test_restore_comparison_rejects_missing_dimension_editability_evidence(missing):
    expected, actual = context(), context()
    expected["dimensions"]["Width@Sketch1"].pop(missing)
    actual["dimensions"]["Width@Sketch1"].pop(missing)
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is False


def test_restore_comparison_requires_known_sketch_count():
    expected, actual = context(), context()
    expected["sketch_constraints"].pop("sketch_count")
    actual["sketch_constraints"].pop("sketch_count")
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is False


@pytest.mark.parametrize("field,value", [("driven_state", True), ("parameter_type", False)])
def test_restore_does_not_accept_boolean_dimension_enums(field, value):
    expected, actual = context(), context()
    expected["dimensions"]["Width@Sketch1"][field] = int(value)
    actual["dimensions"]["Width@Sketch1"][field] = value
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is False


def test_restore_does_not_accept_boolean_sketch_count():
    expected, actual = context(), context()
    actual["sketch_constraints"]["sketch_count"] = True
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is False


def test_restore_comparison_rejects_unknown_feature_identity_and_errors():
    expected, actual = context(), context()
    for candidate in (expected, actual):
        candidate["features"] = [{"name": None, "type": None, "error_code": None}]
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is False


def test_restore_comparison_rejects_matching_failed_feature_states():
    expected, actual = context(), context()
    expected["features"][0]["error_code"] = 7
    actual["features"][0]["error_code"] = 7
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is False


def test_restore_comparison_rejects_changed_dimension_inventory():
    expected, actual = context(), context()
    actual["dimensions"]["Unexpected@Sketch1"] = {"system_value": 1.0, "driven_state": 2,
                                                    "parameter_type": 0}
    assert modeling.compare_checkpoint_context(expected, actual)["passed"] is False


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    """Inject only documented native seams, while retaining real checkpoint I/O."""
    source = tmp_path / "source.sldprt"
    initial = context()
    initial["document"]["path"] = str(source)
    source.write_text(json.dumps(initial), encoding="utf-8")
    original = SimpleNamespace(identity="original-proxy", state=copy.deepcopy(initial))
    state = SimpleNamespace(source=source, original=original, open_calls=0, close_calls=0,
                            dimension_calls=[], instances=[], delivery_calls=0, fault=None,
                            edit_failure_at=None, directory_reads=0, restores=0)

    def hash_file(path):
        path = Path(path)
        if not path.exists():
            return {"exists": False}
        data = path.read_bytes()
        return {"exists": True, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}

    class Backend:
        @classmethod
        def open_owned(cls, _sw, _documents, _originals, path):
            state.open_calls += 1
            if state.open_calls > 1 and state.fault == "recovery_open":
                raise RuntimeError("recovery open refused")
            instance = cls.__new__(cls)
            instance.path = Path(path)
            instance.state = json.loads(instance.path.read_text(encoding="utf-8"))
            instance.sketches = {"base": "Sketch1"}
            state.instances.append(instance)
            if state.open_calls > 1 and state.fault == "recovery_mismatch":
                instance.state["geometry"]["volume_mm3"] += 100
            return instance

        def snapshot(self):
            return copy.deepcopy(self.state)

        def set_dimension(self, name, value):
            state.dimension_calls.append((name, value))
            doc = self.state["document"]
            self.state = context(value)
            self.state["document"] = doc
            return {"verified": len(state.dimension_calls) != state.edit_failure_at,
                    "after_mm": {"current": value}}

        def save_working(self, path):
            assert Path(path) == self.path
            self.path.write_text(json.dumps(self.state), encoding="utf-8")

        def close(self):
            state.close_calls += 1
            if state.fault == "close":
                raise RuntimeError("close failed")

        def deliver(self, _output):
            state.delivery_calls += 1
            if state.fault == "source_context":
                state.original.state["selection"]["count"] = 1
            if state.fault == "source_file":
                source.write_bytes(b"unexpected source mutation")
            if state.fault == "source_identity":
                state.original.identity = "replaced-proxy"
            return {"review_evaluation": {"status": "fail" if state.fault == "delivery" else "pass"}}

    def session(_sw):
        return {"active_document": copy.deepcopy(initial["document"]),
                "documents": [copy.deepcopy(initial["document"])], "documents_complete": True}

    def validate_inventory(_before):
        if state.fault == "inventory":
            raise RuntimeError("inventory unavailable")

    def directory(_sw):
        state.directory_reads += 1
        return "changed" if state.fault == "working_directory" and state.directory_reads > 1 else "original"

    def restore_active(_sw, _active):
        state.restores += 1
        if state.fault == "active_restore":
            raise RuntimeError("activation failed")

    def protection(_before, _after, prior, current):
        passed = prior == current
        return {"passed": passed, "checks": [{"check": "file_hashes", "passed": passed}]}

    native = SimpleNamespace(
        _execution_lock=nullcontext, _attach=lambda: SimpleNamespace(RevisionNumber="fake-offline"),
        _helpers=lambda: (SimpleNamespace(get_com_member=lambda obj, name: getattr(obj, name)), None, None, None),
        capture_session_context=session, _validate_inventory=validate_inventory,
        _resolve_original_models=lambda _sw, _documents: [original],
        capture_model_context=lambda model: copy.deepcopy(model.state),
        _document_identity=lambda model: model.identity,
        _source_files=lambda _sw, _before: {str(source): hash_file(source)},
        _working_directory=directory, _hash_file=hash_file, _restore_active=restore_active,
        compare_protection=protection, _context_evidence=lambda candidate: copy.deepcopy(candidate),
    )
    monkeypatch.setattr(modeling, "_native_backend_class", lambda: (Backend, native))
    state.native = native
    return state


def test_run_edit_isolates_source_and_saves_real_immutable_checkpoints(tmp_path, runtime):
    before = runtime.source.read_bytes()
    report = modeling.run_request(edit_request(runtime.source), tmp_path / "out")
    assert report["task_succeeded"] is True
    assert report["status"] == "passed"
    assert report["source_protection"]["passed"] is True
    assert runtime.source.read_bytes() == before
    assert runtime.open_calls == runtime.close_calls == runtime.restores == 1
    assert runtime.delivery_calls == 1
    assert len(report["checkpoints"]) == 2
    assert all(Path(entry["model_path"]).is_file() for entry in report["checkpoints"])
    saved_report = json.loads((tmp_path / "out" / "modeling_report.json").read_text(encoding="utf-8"))
    assert saved_report["task_succeeded"] is True


def test_partial_native_edit_recovers_last_accepted_model_but_keeps_task_failed(tmp_path, runtime):
    runtime.edit_failure_at = 2
    report = modeling.run_request(edit_request(runtime.source, (50, 60, 70)), tmp_path / "out")
    assert report["status"] == "recovered"
    assert report["task_succeeded"] is False
    assert report["recovery"]["passed"] is True
    assert report["recovery"]["context"]["geometry"]["volume_mm3"] == 5000
    assert len(runtime.dimension_calls) == 2
    assert runtime.delivery_calls == 0
    assert runtime.open_calls == 2
    assert runtime.source.read_text(encoding="utf-8") == json.dumps(runtime.original.state)


@pytest.mark.parametrize("fault,code", [
    ("active_restore", "active_restore_failed"),
    ("source_context", "source_protection_failed"),
    ("source_file", "source_protection_failed"),
    ("source_identity", "source_protection_failed"),
    ("working_directory", "source_protection_failed"),
    ("close", "owned_close_failed"),
])
def test_late_protection_errors_never_leave_a_successful_task(tmp_path, runtime, fault, code):
    runtime.fault = fault
    report = modeling.run_request(edit_request(runtime.source), tmp_path / "out")
    assert report["status"] == "failed"
    assert report["task_succeeded"] is False
    assert code in {item.get("code") for item in report["feedback"]}


@pytest.mark.parametrize("fault", ["recovery_open", "recovery_mismatch"])
def test_failed_recovery_never_reports_recovered_or_delivers(tmp_path, runtime, fault):
    runtime.edit_failure_at = 1
    runtime.fault = fault
    report = modeling.run_request(edit_request(runtime.source), tmp_path / "out")
    assert report["status"] == "failed"
    assert report["task_succeeded"] is False
    assert "recovery_failed" in {item.get("code") for item in report["feedback"]}
    assert runtime.delivery_calls == 0
    assert report.get("recovery", {}).get("passed") is not True


def test_delivery_failure_recovers_and_does_not_claim_success(tmp_path, runtime):
    runtime.fault = "delivery"
    report = modeling.run_request(edit_request(runtime.source), tmp_path / "out")
    assert report["status"] == "recovered"
    assert report["task_succeeded"] is False
    assert "modeling_failed" in {item.get("code") for item in report["feedback"]}


def test_inventory_failure_is_reported_without_uninitialized_cleanup_errors(tmp_path, runtime):
    runtime.fault = "inventory"
    report = modeling.run_request(edit_request(runtime.source), tmp_path / "out")
    assert report["task_succeeded"] is False
    assert runtime.dimension_calls == []
    assert runtime.open_calls == 0
    assert not any("UnboundLocalError" in item.get("message", "") for item in report["feedback"])


def test_unsaved_source_is_not_copied_or_opened(tmp_path, runtime):
    original_capture = runtime.native.capture_session_context
    def unsaved(sw):
        result = original_capture(sw)
        result["documents"][0]["save_flag"] = True
        return result
    runtime.native.capture_session_context = unsaved
    report = modeling.run_request(edit_request(runtime.source), tmp_path / "out")
    assert report["task_succeeded"] is False
    assert runtime.open_calls == 0
    assert runtime.dimension_calls == []
    assert not list((tmp_path / "out").glob("working_*.sldprt"))


def test_source_changed_during_disk_copy_stops_before_native_open(tmp_path, runtime, monkeypatch):
    import sw_checkpoints
    original_copy = sw_checkpoints._copy_exclusive
    def changing_copy(source, target):
        result = original_copy(source, target)
        Path(source).write_bytes(b"source changed while copying")
        return result
    monkeypatch.setattr(sw_checkpoints, "_copy_exclusive", changing_copy)
    report = modeling.run_request(edit_request(runtime.source), tmp_path / "out")
    assert report["task_succeeded"] is False
    assert runtime.open_calls == runtime.delivery_calls == 0
    assert any("Source changed while copying" in item.get("message", "") for item in report["feedback"])
    assert report["source_protection"]["passed"] is False


@pytest.mark.parametrize("stage", ["backend_import", "attach"])
def test_native_initialization_errors_produce_failure_reports(tmp_path, runtime, monkeypatch, stage):
    def unavailable():
        raise RuntimeError("native unavailable")
    if stage == "backend_import":
        monkeypatch.setattr(modeling, "_native_backend_class", unavailable)
    else:
        runtime.native._attach = unavailable
    report = modeling.run_request(edit_request(runtime.source), tmp_path / "out")
    assert report["task_succeeded"] is False
    assert runtime.open_calls == 0
    assert runtime.delivery_calls == 0
    assert any("native unavailable" in item.get("message", "") for item in report["feedback"])
    assert (tmp_path / "out" / "modeling_report.json").is_file()


def test_unreadable_original_context_at_final_verification_is_a_failed_task(tmp_path, runtime):
    original_capture = runtime.native.capture_model_context
    calls = []
    def unavailable_after_initial(model):
        calls.append(model)
        if len(calls) > 1:
            raise RuntimeError("original context now unavailable")
        return original_capture(model)
    runtime.native.capture_model_context = unavailable_after_initial
    report = modeling.run_request(edit_request(runtime.source), tmp_path / "out")
    assert report["task_succeeded"] is False
    assert report["source_protection"]["passed"] is False
    assert "source_protection_error" in {item.get("code") for item in report["feedback"]}


def test_restore_reopens_and_verifies_geometry_before_checkpoint_or_delivery(tmp_path, runtime):
    origin = modeling.CheckpointStore(tmp_path / "origin")
    saved = origin.create(runtime.source, label="saved", context=runtime.original.state)
    request = {"schema_version": 1, "mode": "restore", "checkpoint_root": str(origin.root),
               "checkpoint_id": saved["id"]}
    report = modeling.run_request(request, tmp_path / "out")
    assert report["task_succeeded"] is True
    assert report["restore_validation"]["passed"] is True
    assert runtime.dimension_calls == []
    assert runtime.delivery_calls == 1


def test_corrupt_restore_checkpoint_is_rejected_before_native_open(tmp_path, runtime):
    origin = modeling.CheckpointStore(tmp_path / "origin")
    saved = origin.create(runtime.source, label="saved", context=runtime.original.state)
    Path(saved["model_path"]).write_bytes(b"tampered")
    request = {"schema_version": 1, "mode": "restore", "checkpoint_root": str(origin.root),
               "checkpoint_id": saved["id"]}
    report = modeling.run_request(request, tmp_path / "out")
    assert report["task_succeeded"] is False
    assert runtime.open_calls == 0
    assert runtime.delivery_calls == 0
    assert report["checkpoints"] == []
