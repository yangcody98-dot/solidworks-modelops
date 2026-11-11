# Result review reference

## Required checks

After generating, modifying, or exporting a SolidWorks file, verify at least:

1. COM calls returned non-`None` objects and required features were created.
2. `save_document()`, `session.save()`, and `session.export()` reported success.
3. Output `.sldprt` / `.sldasm` / `.slddrw` / `.step` / `.stl` files actually exist and have reasonable sizes.
4. The task model was rebuilt with `model.ForceRebuild3(False)`.
5. Fit the task model to the window with `model.ViewZoomtofit2()`.
6. Export at least an isometric BMP; add front, top, and right views for complex models.

## Structured review report

```python
import sys
sys.path.insert(0, r"SKILL_DIR/scripts")

from sw_review import run_review

model.ForceRebuild3(False)
report, report_path = run_review(
    model,
    r"C:\temp\solidworks_review",
    basename="model",
    views=("isometric", "front", "top", "right"),
    expected_outputs=[r"C:\temp\model.sldprt", r"C:\temp\model.step"],
)
print(report_path)
print(report["checks"])
```

`run_review()` produces:

- Multiple BMP preview views.
- A structured `*_review_report.json`.
- A readable `*_review_summary.md` for delivery notes, issues, or PRs.
- `evaluation.status`：`pass` / `warn` / `fail`。
- `evaluation.score`: rule-based score, maximum 100.
- `evaluation.issues`: machine-readable issues.
- `evaluation.recommendations`: repair suggestions.
- `checks.previews_created`: previews were generated.
- `checks.previews_not_blank`: previews appear nonblank.
- `checks.expected_outputs_exist`: requested files exist and contain bytes.
- `checks.feature_summary_available`: feature-tree summary is readable.

Structured checks catch obvious failures; they do not replace human or vision-model judgment of geometric intent.

Manufacturing tasks also need separate machine-readable specification evidence, for example:

```json
{
  "cad_spec": {
    "envelope_mm": {"length": 60, "width": 40, "thickness": 12},
    "holes": [
      {"diameter_mm": 10, "count": 1, "positions_xy_mm": [[0, 0]]},
      {"diameter_mm": 4, "count": 4, "positions_xy_mm": [[-24, -14], [24, -14], [-24, 14], [24, 14]]}
    ]
  },
  "measurement_source": "SolidWorks API/B-Rep/parameter readback",
  "units": "mm"
}
```

If specified overall dimensions or diameters lack independent JSON evidence, the Reviewer Gate must fail. A Codex summary or executor-reported pass does not substitute for evidence. Record required hole counts, locations, edge distances, center distances, fillets, walls, and assembly degrees of freedom individually.

For complex holes/slots, `collect_geometry_measurements()` also returns:

- `hole_groups`: cylindrical segments grouped by spatial axis.
- `compound_holes`: coaxial counterbore/compound-hole candidates with differing diameters.
- `slot_arc_candidates`: slot-end internal cylinders with multiple boundary edges; excluded from round-hole counts.
- `validate_hole_positions()`: per-hole checks against axis-distance and diameter tolerances.

```python
from sw_review import collect_geometry_measurements, validate_hole_positions

measurements = collect_geometry_measurements(model)
position_checks = validate_hole_positions(
    measurements,
    [{"id": "H1", "diameter_mm": 8, "position_mm": [20, 20, 0]}],
    position_tolerance_mm=0.1,
    diameter_tolerance_mm=0.05,
)
assert position_checks["status"] == "pass"
```

Cylindrical B-Rep faces can establish diameter, axis, and segment length, but cannot reliably distinguish blind/through holes alone. Cross-check blind depths, countersink angles, and hole types against creation evidence from `sw_hole_features.py` or feature-definition readback.

## Command-line review

```bash
python scripts/sw_review.py ^
  --file C:\temp\model.sldprt ^
  --output-dir C:\temp\solidworks_review ^
  --basename model ^
  --expected C:\temp\model.sldprt ^
  --expected C:\temp\model.step
```

Exit codes:

- `0`: `pass` or `warn`; report generated.
- `1`: `warn` when `--fail-on-warn` was supplied.
- `2`: `fail`; required repairs remain.

## Visual review checklist

- Is the main body visible rather than a blank frame or sketch alone?
- Are required wheels, holes, shafts, enclosures, brackets, BOM tables, and other components present?
- Are reported cuts/holes/slots visible on the intended face? `feature is not None` does not establish geometric intent.
- Are proportions correct, without unit mistakes such as treating millimeters as meters?
- Is orientation correct, such as wheels on the side rather than the roof?
- Are there obvious overlaps, floating parts, penetrations, or missing constraints?
- Do filenames, output directories, and formats match the request?

## Handling findings

1. Do not report only that a file was saved.
2. Identify sketch, selection, extrusion-direction, unit, reference-plane, or export failures.
3. Revise the script, regenerate, and export previews again.
4. State which previews were checked and what limitations remain in the final reply.
