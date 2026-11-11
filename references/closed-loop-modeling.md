# Modeling loop driven by measured model context

Convert requirements into a structured operation plan, read real model data, and execute and verify each step. Reuse
wrappers such as `sw_part` and `sw_review`; existing specialized modeling, assembly, drawing, and export interfaces remain available.

## Entry points

```powershell
python scripts/sw_preflight.py
python scripts/sw_closed_loop.py observe --out output/context.json
python scripts/sw_closed_loop.py validate --plan examples/closed_loop_plate.json
python scripts/sw_closed_loop.py run --plan examples/closed_loop_plate.json --out-dir output/closed_loop_run_01
```

- `observe` reads the active model and session only; the output path must not exist. With no active document, it explicitly returns `model: null`.
- `validate` does not connect to CAD. It checks the operation allowlist, finite numbers, reference order, and acceptance conditions.
- `run` requires an open SolidWorks session and a new output directory. It executes only in a new part; the active source model is a read-only reference.
  It never rebuilds the source, resolves its lightweight components, clears its selections, saves it, or closes it. Source hashes, original document state, and restoration evidence go into the report.
- This entry does not edit existing models in place. Use the original specialized workflow for that capability and honor the user's file-protection requirements.

## Connecting a plan to the real model

The agent converts requirements into an operation plan. Plans are JSON data, not executable Python/VBA; never pass user text to `eval`.
Numbers come from explicit user dimensions, actual model measurements, or stated design assumptions. See `examples/closed_loop_plate.json` for a complete example.

Four operations are supported:

Native ribs use the separate `sw_native_ribs.create_native_rib()` wrapper and the
[native rib acceptance workflow](native-ribs.md); they are outside the JSON operation allowlist below.
Specialized scripts must still protect task-owned documents and follow before snapshot, creation, readback, after snapshot, and geometry acceptance.
Never report an ordinary extrusion as a Rib or bypass plan validation because a specialized capability was added.

| op | params (lengths in mm) |
|---|---|
| `sketch_rectangle` | `plane`, `cx_mm`, `cy_mm`, `width_mm`, `height_mm` |
| `sketch_circles` | `plane`, `circles: [{x_mm,y_mm,radius_mm}]` |
| `extrude_boss` | `sketch_id`, `depth_mm` |
| `extrude_cut` | `sketch_id`, `depth_mm`, `through_all`, `reverse` |

`id` identifies a plan step; `sketch_id` references an earlier successfully created sketch. Do not depend on an incidental GUI name such as `Sketch1`.
Sketch coordinates are local to the selected reference plane. Acceptance bounds and hole locations use global model coordinates; keep these frames distinct.

Parameters can bind to measured context, for example:

```json
{"from_context":"geometry.bbox_size_mm.2","scale":1,"offset_mm":0}
```

- `from_context` reads actual measurements immediately before the current step; `from_source` reads the source snapshot captured at execution start.
- Allowed paths are `geometry.bbox_size_mm.0/1/2`, `geometry.volume_mm3`, and `geometry.body_count`.
- Values use `value * scale + offset_mm`; the caller must respect physical units. Missing data or invalid values stop execution immediately.
  Do not hide failures with template dimensions. These limited scalar bindings are not persistent references to arbitrary faces/edges or automatic reverse engineering.
- `expect` can check `body_count`, `bbox_size_mm`, `volume_mm3`, `feature_ok`, and `holes`;
  `requirements` holds final acceptance conditions. Bounding-box, volume, and hole-location tolerances can be explicit.
- Bounds come from SolidWorks' approximate bounding-box API and do not prove a precision dimension chain. Hole locations use B-Rep cylindrical faces;
  cylindrical faces alone do not prove a blind or through hole.

## Checks and bounded correction

Each action records before/after snapshots, resolved parameters, return values, rebuild results, and measured acceptance results.
Before closing rectangle/circle sketches, the executor creates driving dimensions and relations and reads their constraint status. Delivery checks absorbed subsketches recursively.
Underdefined, overdefined, undimensioned, or entirely Fixed ordinary sketches block delivery. Native Hole Wizard profiles may retain their internal anchors only
when parent-feature and driving-parameter evidence is complete. Geometric correctness and valid parametric modeling are separate checks.
Extrusion must increase solid volume; a cut must reduce volume while retaining a solid. Unavailable volume cannot pass.

A plan may explicitly declare one alternate cut direction:

```json
"fallback_params": [{"reverse": true}]
```

The alternate is attempted only if the failed operation created no feature and a complete feature list, body count, volume, and bounds prove no mutation.
At most one retry is allowed per plan. Never shrink a hole, change thickness, or remove a required feature merely to pass acceptance.
Other failures return `needs_revision`, context, failed checks, and a suggested next action; later steps do not run.
Use that measured feedback to revise the plan and rerun in a new output directory. Do not simply edit a report to say pass.

## Relationship to the original VibeCAD workflow

`compile_design_plan` can adapt explicit legacy base-plate, through-hole, and through-hole-pattern plans. The original `plan_from_brief.py`,
its templates, and execution-summary entry remain unchanged. Fillets, chamfers, pockets, and closing old documents in the full CNC template
are outside this loop's execution allowlist and are rejected before any CAD write, including optional steps; unsupported steps are never silently removed.
Use the original CNC workflow or obtain confirmation of an explicitly simplified design and generate a new operation plan.

## Artifacts and acceptance scope

Output includes the input plan, source context, per-step `events.jsonl`, and `run_report.json`. Successful runs also produce uniquely named
SLDPRT and STEP files, four views, and the existing review report. Reimport STEP into a separate document and check body count, volume, and position.
During STEP import, temporarily use this run's output directory as SolidWorks' working directory. Restore it and read it back after success or failure so imported child paths do not land in the user's project.
Restoration or source-protection failure fails the entire task, even if the model looks correct.

This capability is `pilot` and covers basic part operations only. Engineering review remains required. It does not implement a proprietary official model,
arbitrary natural-language design, full assembly-topology reasoning, or automated engineering certification. Automated tests use new isolated parts rather than destructive tests on user models.
