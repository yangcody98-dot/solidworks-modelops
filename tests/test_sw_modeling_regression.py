"""The benchmark refuses weak evidence even when a backend says 'passed'."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sw_modeling_regression as regression


def suite():
    return json.loads(regression.DEFAULT_SUITE.read_text(encoding="utf-8"))


def measured_context(thickness):
    # Independent fixture measurement, not a call to the production oracle.
    holes = [{"diameter_mm": 6.0, "position_mm": [x, y, thickness / 2], "axis": [0.0, 0.0, 1.0]}
             for x, y in [(-40, -20), (40, -20), (-40, 20), (40, 20)]]
    return {"geometry": {"body_count": 1, "bbox_size_mm": [100, 60, thickness],
                         "volume_mm3": 100 * 60 * thickness - 4 * math.pi * 3**2 * thickness,
                         "hole_measurements": {"holes": holes}}}


class FixtureRunner:
    """Creates ordinary files only; never imports a SolidWorks module."""
    def __init__(self, corrupt=None):
        self.requests = []
        self.corrupt = corrupt

    def __call__(self, request, output):
        self.requests.append(copy.deepcopy(request))
        output.mkdir()
        mode = request["mode"]
        failed_edit = mode == "edit" and request["operations"][0]["id"] == "reject_wrong_volume"
        thickness = 8 if mode == "create" else 12
        context = measured_context(thickness)
        model = output / "model.sldprt"
        model.write_bytes(f"native test fixture thickness={thickness}".encode())
        step = output / "model.step"
        step.write_bytes(b"STEP test fixture")
        checkpoint_root = output / "checkpoints"
        checkpoint_id = "0123456789abcdef" + str(len(self.requests))
        checkpoint_folder = checkpoint_root / checkpoint_id
        checkpoint_folder.mkdir(parents=True)
        checkpoint_model = checkpoint_folder / "model.sldprt"
        checkpoint_model.write_bytes(model.read_bytes())
        manifest = checkpoint_folder / "manifest.json"
        manifest.write_text(json.dumps({"id": checkpoint_id}), encoding="utf-8")
        checkpoint = {"id": checkpoint_id, "manifest_path": str(manifest), "model_path": str(checkpoint_model),
                      "root": str(checkpoint_root), "context": copy.deepcopy(context)}
        report = {"status": "recovered" if failed_edit else "passed", "source_protection": {"passed": True},
                  "final_context": context, "checkpoints": [checkpoint],
                  "delivery": {"native": str(model), "step": str(step),
                               "sketch_constraints": {"all_fully_defined": True, "all_parametric": True},
                               "step_reopen_validation": {"passed": True}}}
        if mode == "create":
            report["steps"] = [{"id": "stock", "op": "extrude_boss", "attempts": [{"passed": True,
                "result": {"created": True, "feature_name": "凸台-拉伸1"}}]}]
        if failed_edit:
            report["recovery"] = {"passed": True, "native": str(model), "checkpoint_id": checkpoint_id,
                                  "context": copy.deepcopy(context)}
            report["steps"] = [{"id": "reject_wrong_volume", "op": "set_dimension",
                                "after": measured_context(14)}]
        if self.corrupt:
            self.corrupt(request, output, report)
        return report


def run(tmp_path, backend):
    return regression.run_suite(suite(), tmp_path / "regression", runner=backend, isolated_runner=backend)


def test_full_benchmark_links_real_predecessor_paths_and_discovers_localized_dimension(tmp_path):
    backend = FixtureRunner()
    result = run(tmp_path, backend)
    assert result["passed"] is True
    assert result["execution"] == "injected_test_backend"
    assert [c["passed"] for c in result["cases"]] == [True, True, True, True]
    create, edit, rejected, restore = backend.requests
    assert edit["operations"][0]["params"] == {"name": "D1@凸台-拉伸1", "value_mm": 12}
    assert Path(edit["source"]).parent.name == "create_plate"
    assert Path(rejected["source"]).parent.name == "edit_thickness"
    assert rejected["operations"][0]["params"]["value_mm"] == 14
    wrong = rejected["operations"][0]["expect"]["volume_mm3"]
    assert abs(wrong - measured_context(14)["geometry"]["volume_mm3"]) > 100
    assert Path(restore["checkpoint_root"]).parent.name == "edit_thickness"
    assert restore["checkpoint_id"].endswith("2")
    assert create["plan"]["operations"][-1]["params"]["through_all"] is True
    assert (tmp_path / "regression" / "regression_summary.json").is_file()


def test_passed_status_with_wrong_actual_volume_does_not_pass(tmp_path):
    def corrupt(request, output, report):
        report["final_context"]["geometry"]["volume_mm3"] = 48000
    backend = FixtureRunner(corrupt)
    result = run(tmp_path, backend)
    assert result["passed"] is False
    assert len(backend.requests) == 1
    check = next(c for c in result["cases"][0]["checks"] if c["name"] == "analytic_volume")
    assert check["passed"] is False


@pytest.mark.parametrize("missing", ["source_protection", "constraints", "step_reopen", "hole_geometry", "checkpoint"])
def test_missing_evidence_blocks_dependent_cases(tmp_path, missing):
    def corrupt(request, output, report):
        if missing == "source_protection":
            report.pop("source_protection")
        elif missing == "constraints":
            report["delivery"].pop("sketch_constraints")
        elif missing == "step_reopen":
            report["delivery"].pop("step_reopen_validation")
        elif missing == "hole_geometry":
            report["final_context"]["geometry"].pop("hole_measurements")
        elif missing == "checkpoint":
            Path(report["checkpoints"][0]["manifest_path"]).unlink()
    backend = FixtureRunner(corrupt)
    result = run(tmp_path, backend)
    assert result["passed"] is False
    assert len(backend.requests) == 1


def test_source_file_mutation_is_detected_independently_of_backend_claim(tmp_path):
    def corrupt(request, output, report):
        if request["mode"] == "edit":
            Path(request["source"]).write_bytes(b"unexpected source overwrite")
    backend = FixtureRunner(corrupt)
    result = run(tmp_path, backend)
    assert result["passed"] is False
    assert len(backend.requests) == 2
    checks = result["cases"][1]["checks"]
    assert next(c for c in checks if c["name"] == "source_protection")["passed"] is True
    assert next(c for c in checks if c["name"] == "source_disk_unchanged")["passed"] is False


@pytest.mark.parametrize("failure", ["status", "missing_recovery", "wrong_recovered_geometry", "never_mutated", "wrong_checkpoint"])
def test_failed_edit_needs_verified_restore_to_accepted_thickness(tmp_path, failure):
    def corrupt(request, output, report):
        if request["mode"] != "edit" or request["operations"][0]["id"] != "reject_wrong_volume":
            return
        if failure == "status":
            report["status"] = "passed"
        elif failure == "missing_recovery":
            report["recovery"]["passed"] = False
        elif failure == "never_mutated":
            report["steps"][0]["after"] = measured_context(12)
        elif failure == "wrong_checkpoint":
            report["recovery"]["checkpoint_id"] = "unrelated_checkpoint"
        else:
            report["recovery"]["context"] = measured_context(14)
    backend = FixtureRunner(corrupt)
    result = run(tmp_path, backend)
    assert result["passed"] is False
    assert len(backend.requests) == 3
    assert result["cases"][-1]["id"] == "recover_failed_edit"


def test_existing_output_is_never_overwritten_or_sent_to_backend(tmp_path):
    output = tmp_path / "regression"
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("existing user content", encoding="utf-8")
    backend = FixtureRunner()
    with pytest.raises(FileExistsError):
        regression.run_suite(suite(), output, runner=backend, isolated_runner=backend)
    assert backend.requests == []
    assert marker.read_text(encoding="utf-8") == "existing user content"


def test_edit_is_blocked_without_actual_created_feature_name(tmp_path):
    def corrupt(request, output, report):
        report.pop("steps", None)
    backend = FixtureRunner(corrupt)
    result = run(tmp_path, backend)
    assert result["passed"] is False
    assert len(backend.requests) == 1
    assert "extrusion feature name" in result["cases"][0]["error"]


@pytest.mark.parametrize("change", ["nan", "overlap", "outside", "dependency", "missing_case"])
def test_invalid_suite_fails_before_any_files_or_backend_calls(tmp_path, change):
    value = suite()
    if change == "nan":
        value["fixture"]["width_mm"] = float("nan")
    elif change == "overlap":
        value["fixture"]["holes"][1] = copy.deepcopy(value["fixture"]["holes"][0])
    elif change == "outside":
        value["fixture"]["holes"][0]["x_mm"] = 50
    elif change == "dependency":
        value["cases"][2]["source_case"] = "create_plate"
    else:
        value["cases"].pop()
    backend = FixtureRunner()
    with pytest.raises(ValueError):
        regression.run_suite(value, tmp_path / "regression", runner=backend, isolated_runner=backend)
    assert backend.requests == []
    assert not (tmp_path / "regression").exists()


def test_plate_normal_holes_are_required_even_if_tilted_axes_cross_expected_points():
    value = suite()
    context = measured_context(8)
    for hole in context["geometry"]["hole_measurements"]["holes"]:
        hole["axis"] = [1.0, 0.0, 0.0]
    checks = regression.geometry_checks(context, regression.oracle(value, 8), value)
    assert all(not c["passed"] for c in checks if c["name"].endswith("axis_and_diameter"))


def test_validate_cli_does_not_import_a_cad_backend(monkeypatch, capsys):
    import builtins
    original = builtins.__import__
    def guarded(name, *args, **kwargs):
        if any(key in name for key in ("sw_modeling", "sw_connect", "sw_review", "win32com", "pythoncom")):
            raise AssertionError("Offline validation imported a CAD module: " + name)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", guarded)
    assert regression.main(["validate"]) == 0
    response = json.loads(capsys.readouterr().out)
    assert response["status"] == "valid"
    assert response["cases"] == 4


def test_independent_restore_rejects_child_process_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(regression.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=7, stderr="restore failed"))
    with pytest.raises(RuntimeError, match="Independent checkpoint restore failed"):
        regression._isolated_restore({"mode": "restore"}, tmp_path / "restore")
