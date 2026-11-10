"""Opt-in native regression. Creates and mutates ONLY its own test fixture.

Run while SolidWorks is open. Output directory must not already exist. Existing
user documents remain untouched; the source fixture is created by this run.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from sw_closed_loop_native import run_native, _attach, _restore_active, _hash_file, compare_protection
from sw_model_context import capture_session_context, capture_model_context
from sw_connect import get_com_member, open_document
from sw_document_data import set_custom_properties


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    output = Path(args.out_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)
    sw = _attach()
    original = capture_session_context(sw)
    plan = json.loads((ROOT / "examples" / "closed_loop_plate.json").read_text(encoding="utf-8"))
    fixture = None
    summary = {"passed": False, "checks": []}
    try:
        seed = run_native(plan, output / "seed")
        summary["seed_status"] = seed["status"]
        if seed["status"] != "passed":
            raise RuntimeError("Seed failed; inspect seed/run_report.json")
        fixture_path = seed["delivery"]["native"]
        fixture_hash = _hash_file(fixture_path)
        fixture = open_document(sw, fixture_path, silent=True, raise_on_error=True)
        prop = set_custom_properties(fixture, {"ClosedLoopRegression": "unsaved test-only marker"}, save=False)
        if not prop["success"]:
            raise RuntimeError("Could not create unsaved test-only property")
        # Explicitly dirty our own fixture to exercise protection of unsaved work.
        # IModelDoc2.SetSaveFlag has no arguments and changes only this test document.
        get_com_member(fixture, "SetSaveFlag")
        selected = False
        for item in capture_model_context(fixture, include_geometry=False)["features"]:
            if item["type"] != "RefPlane":
                continue
            feature = fixture.FeatureByName(item["name"])
            if feature is not None and bool(feature.Select2(False, 0)):
                selected = True
                break
        fixture_context = capture_model_context(fixture)
        if not selected or fixture_context["selection"].get("count", 0) < 1 or fixture_context["document"]["save_flag"] is not True:
            raise RuntimeError(f"Fixture must be dirty with a nonempty selection: selected={selected}, context={fixture_context['document']}")
        contextual = copy.deepcopy(plan)
        contextual["operations"][0]["params"]["width_mm"] = {"from_source": "geometry.bbox_size_mm.0"}
        contextual["operations"][0]["params"]["height_mm"] = {"from_source": "geometry.bbox_size_mm.1"}
        contextual["operations"][1]["params"]["depth_mm"] = {"from_source": "geometry.bbox_size_mm.2"}
        contextual["operations"][-1]["params"]["reverse"] = True
        contextual["operations"][-1]["fallback_params"] = [{"reverse": False}]
        result = run_native(contextual, output / "source_and_feedback")
        checks = summary["checks"]
        checks.append({"name": "source_bound_plan_passes", "passed": result["status"] == "passed"})
        checks.append({"name": "native_direction_retry", "passed": any(
            f.get("code") == "retry_declared_direction" for f in result.get("feedback", []))})
        checks.append({"name": "dirty_selected_source_preserved", "passed": result.get("source_protection", {}).get("passed") is True})
        negative = copy.deepcopy(plan)
        negative["operations"][1]["expect"]["volume_mm3"] = 49000
        rejected = run_native(negative, output / "failed_measurement")
        checks.append({"name": "wrong_volume_stops_later_operations", "passed": rejected["status"] == "needs_revision"
                       and len(rejected["steps"]) == 2 and "delivery" not in rejected})
        checks.append({"name": "source_preserved_on_failure", "passed": rejected.get("source_protection", {}).get("passed") is True})
        checks.append({"name": "source_disk_hash_unchanged", "passed": _hash_file(fixture_path) == fixture_hash})
        summary["solidworks_revision"] = result.get("solidworks_revision")
        summary["passed"] = all(check["passed"] for check in checks)
    except Exception as exc:
        summary["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if fixture is not None:
            # The fixture was produced by this run; discard only its unsaved test marker.
            sw.CloseDoc(get_com_member(fixture, "GetTitle"))
        _restore_active(sw, original.get("active_document"))
        restored = compare_protection(original, capture_session_context(sw), {}, {})
        summary["checks"].append({"name": "original_session_restored", "passed": restored["passed"]})
        summary["passed"] = summary["passed"] and restored["passed"]
        (output / "regression_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
