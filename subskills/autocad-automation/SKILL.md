---
name: autocad-automation
description: "AutoCAD automation on Windows through Python COM/ActiveX for 2D drafting, layers, text, dimensions, blocks, DWG/DXF/PDF export, batch edits, and drawing review. Also covers AutoLISP/SCR and AutoCAD .NET alternatives when COM is insufficient. Use for AutoCAD, DWG/DXF, drawing output, layers, dimensions, blocks, batch changes, AutoLISP, ObjectARX, .NET plugins, and direct agent control of desktop CAD."
metadata: { "os": ["win32"], "requires": { "anyBins": ["python", "py"], "pythonPackages": ["pywin32"] } }
---

# AutoCAD Automation

> This is the AutoCAD/DWG subskill from `solidworks-automation-skill`. The parent handles SolidWorks parts, assemblies, drawings, and 3D export. This subskill handles AutoCAD 2D DWG/DXF drafting, batch edits, line-art vectorization, previews, and drawing review. Return to the parent for native SolidWorks modeling; use this subskill for AutoCAD and DWG/DXF.

## Goal

Provide repeatable local Windows desktop control of AutoCAD. Python + COM/ActiveX is the default route, but native writes must first pass `capabilities.yaml` and local live regression. AutoCAD 2024 dynamic proxies for Documents/Layers/SelectionSets are currently unreliable, so native COM DWG drafting remains `not_implemented`. Headless DXF reading, previews, and structural review are available. The allowlisted AutoCAD 2024 .NET backend has repeatedly passed real DWG save-and-reopen, PDF/PNG, entity, layer, and dimension regressions. It is `verified` only with complete runtime evidence. Allow fixed commands only; do not turn it into arbitrary code execution.

## Use cases

- Create or modify DWG/DXF drawings with lines, circles, arcs, polylines, rectangles, text, blocks, layers, and basic dimensions.
- Batch-open DWG files and inspect layers, entity counts, text, blocks, external references, or outputs.
- Connect an agent to local AutoCAD, save DWG, export DXF/PDF, and produce review reports.
- Develop AutoLISP, `.scr` command scripts, or C# AutoCAD .NET plugins.
- Consult Autodesk API documentation, ADN/GitHub examples, ObjectARX SDK, or APS Design Automation.

Route rendering-only requests, BIM/Revit, STEP-first mechanical modeling, CAM toolpaths, and engineering certification to their respective workflows.

## Defaults

- OS: Windows.
- AutoCAD: installed locally, preferably launched manually once to complete COM registration.
- Entry point: `AutoCAD.Application` COM ProgID.
- Visibility: show and activate AutoCAD before incremental drawing. Disable this only for batch work or an explicit speed request.
- Units: millimeters by default. AutoCAD database values are unitless; record units in drawing notes.
- Space: ModelSpace for geometry; handle layouts, title blocks, and plot settings separately.
- Coordinates: WCS, with `Z=0` for 2D entities.
- Outputs: prefer DWG with DXF/PDF as requested; use absolute paths.
- File protection: save a copy before editing an existing DWG unless the user explicitly permits overwriting.

Clarify missing version, units, standard, output path, or overwrite requirements when they matter. A simple sketch may assume millimeters, ModelSpace, and a new DWG; disclose those assumptions.

## Preflight

Run before automation:

```powershell
python subskills\autocad-automation\scripts\acad_preflight.py
```

If the user permits launching AutoCAD:

```powershell
python subskills\autocad-automation\scripts\acad_preflight.py --launch
```

On failure:

- Missing `pywin32`: explain `python -m pip install pywin32` and install only with explicit agreement.
- AutoCAD COM unavailable: ask the user to install or launch AutoCAD, or confirm whether it is LT or restricted.
- AutoCAD running without an active document: create a document; this alone is not a connection failure.

## Workflow

1. **Classify:** new drawing, existing DWG edit, batch process, export, API or plugin development, or troubleshooting.
2. **Establish constraints:** units, version, target files, formats, overwrite permission, layer/linetype/dimension rules, and company templates.
3. **Preflight:** check Python COM and AutoCAD state with `acad_preflight.py`.
4. **Verify APIs:** for unwrapped APIs, read `references/api-lookup.md`, then Autodesk documentation or a reliable GitHub example. Do not guess long signatures, enums, or command behavior.
5. **Plan:** list layers, datums, entities, dimensions, text, output paths, and review points.
6. **Show AutoCAD:** connect or launch, make the window visible, and bring it forward where possible before drawing.
7. **Reuse scripts:** use JSON with `scripts/acad_draw.py` for simple geometry, or `scripts/acad_session.py` for complex COM workflows.
8. **Serialize COM:** connect, draw incrementally, save, review, and exit in one sequence. Do not operate desktop COM in parallel.
9. **Save/export:** create directories before DWG/DXF/PDF writes; keep a backup or copy when editing an original.
10. **Review:** use `scripts/acad_review.py` for entities, layers, bounds, and files, then `scripts/acad_preview.py` for native BMP/PNG. Inspect the image. Window screenshots are supplementary; obscured screenshots cannot prove success.
    Use `scripts/acad_headless.py` for read-only headless DXF inspection. It cannot write DWG; final DWG/PDF requires the gated AutoCAD route.
11. **Capture lessons:** record new pitfalls, command differences, version limits, and reliable wrappers in `references/troubleshooting.md` or scripts.

### Mechanical drawings and 3D-print cutout drawings

For strict-standard, Chinese-convention, GB/T-style, machining, or 3D-print cutout deliverables:

1. Prefer the user's/company template. Otherwise use common GB/T-style conventions: A3/A4 sheet, binding margin, lower-right title block, FangSong Chinese lettering, and separate thick/thin continuous, centerline, hidden-line, dimension, text, and cutout layers. State that this follows GB/T-style conventions and does not replace company drawing review.
2. Every cut, hole, slot, interface, water port, screw hole, and boss needs specification and locating dimensions. `4×φ3.4`, `7×4×30`, or `2×φ13.5` without datum-edge offsets, center distances, pitch, or heights is incomplete.
3. For dense layouts or leaders crossing views, use hole/slot schedules with location, specification, quantity, and position. Drawing dimensions must still establish key datums, center distances, and overall sizes.
4. Do not replace dimension chains with long leaders. Do not cross other views, centerlines, hole outlines, or dimension text. Move/split views or use tables when needed.
5. Enclosure drawings must specify wall/floor thickness, overall dimensions, interface sizes and centers, assembly-hole center distances, and water-port/vent-slot positions.
6. Use real AutoCAD dimension entities such as `AcDbRotatedDimension`, not ordinary lines and text pretending to be dimensions.
7. Export and inspect previews for missing dimensions, overlapping text, dimensions over views, cross-view leaders, unreadable tables, and title-block intrusion. Correct defects before reporting completion.

## Direct agent drafting

For a simple task, generate drawing JSON and run:

```powershell
python subskills\autocad-automation\scripts\acad_draw.py `
  --input C:\temp\plate_plan.json `
  --output C:\temp\plate.dwg `
  --new
```

The default opens or activates AutoCAD and adds entities incrementally. Use `--fast` only for batch work, slow playback, or an explicit speed request:

```powershell
python subskills\autocad-automation\scripts\acad_draw.py `
  --input C:\temp\batch_plan.json `
  --output C:\temp\batch.dwg `
  --new `
  --fast
```

Example JSON:

```json
{
  "units": "mm",
  "live_preview": true,
  "live_zoom_every": 6,
  "layers": [
    {"name": "OUTLINE", "color": 7},
    {"name": "CENTER", "color": 1},
    {"name": "TEXT", "color": 3}
  ],
  "entities": [
    {"type": "rectangle", "origin": [0, 0], "width": 120, "height": 80, "layer": "OUTLINE"},
    {"type": "circle", "center": [20, 20, 0], "radius": 4.5, "layer": "CENTER"},
    {"type": "text", "text": "MOUNTING PLATE", "point": [8, 88, 0], "height": 5, "layer": "TEXT"}
  ]
}
```

For complex tasks, use Python:

```python
import sys
sys.path.insert(0, r"subskills\autocad-automation\scripts")
from acad_session import AutoCADSession

session = AutoCADSession(create_if_missing=True, visible=True).connect()
session.new_document()
session.activate_window()
session.create_layer("OUTLINE", color=7)
session.add_rectangle((0, 0), width=120, height=80, layer="OUTLINE")
session.live_update(step_delay_s=0.15, zoom=True)
session.save_as(r"C:\temp\plate.dwg")
```

## Technical routes

| Need | Preferred route | Notes |
|---|---|---|
| Quick drafting, edits, batch checks | Python COM/ActiveX | Default shell route; native writes remain gated |
| AutoCAD commands or existing command workflows | `SendCommand` / `.scr` / AutoLISP | May be asynchronous; save and verify |
| Many database transactions, complex selection, plugin menus | AutoCAD .NET | Follow the official guide for transactions and document locks |
| High-performance native or deep database/graphics access | ObjectARX C++ | High cost and version coupling; confirm necessity |
| Cloud DWG batches | APS Design Automation | Suitable without a desktop and for production/CI; requires APS credentials |

## Engineering rules

- Create layers before entities, use ACI colors, and avoid putting everything on layer `0`.
- Declare units/scale; draw 1:1 in ModelSpace and set plotting scale in Layout/Plot.
- Centralize coordinates, dimensions, text heights, and diameters as parameters.
- Manufacturing drawings require verifiable datums and complete cutout locations. Use hole/slot tables when space is limited; long floating leaders are insufficient.
- For ordinary image tracing, keep vectorized source lines. Do not invent broad arcs, long polylines, ellipses, triangles, colored ripples, or replacement text for body outlines, faces, logos, clothing, or splashes. These can look like incorrect construction geometry.
- Remove, freeze, turn off, or make nonplotting any temporary `BODY_OUTLINE`, `JERSEY_OUTLINE`, `PORTRAIT_OUTLINE`, `OUTER_GUIDE`, `CONSTRUCTION`, `FACE_FEATURES`, `LOGO_GEOMETRY`, `WATER_SPLASH`, `JERSEY_STRIPE`, `TEXT_LOGO`, or `TEXT_BRAND` layers before final save, preview, and scoring. Confirm they are invisible and have final entity count `0`.
- Keep hand enhancements only for explicit creative requests, such as reconstructed logos, enhanced faces, added splashes, or text. Explain that they are manual additions, and isolate them on switchable layers.
- Put review notes, scores, and parameters in JSON/Markdown, not visible final ModelSpace text unless requested.
- Check COM results, then output existence and reasonable size after save/export.
- Use `SendCommand` last. Prefer object methods and `_.COMMAND` to reduce language dependence.
- If the user wants to watch, show/activate AutoCAD first and add entities incrementally.
- Delete a same-name SelectionSet before creating a replacement.
- Use per-drawing try/finally for batches and record the file, error, and stage.
- Open originals read-only or save copies by default; overwriting needs explicit authorization.
- Expose only allowlisted drawing/export/review MCP tools, never arbitrary Python/VBA/AutoLISP execution.

## Sources

Prefer official Autodesk AutoCAD API, ActiveX/VBA, Managed .NET, ObjectARX, and APS documentation; then ADN-DevTech/APS GitHub examples. Established projects such as `pyautocad` can inform coordinate, iteration, and wrapper patterns; do not copy code with unclear licensing. Forums, blogs, and Stack Overflow are troubleshooting aids; verify important APIs officially.

When sources disagree, use target-version documentation and local live-test results.

## References

Read as needed:

- `references/api-lookup.md`: documentation, GitHub examples, API verification.
- `references/engineering-patterns.md`: drafting, layers, units, blocks, dimensions, batches.
- `references/troubleshooting.md`: COM, sessions, SendCommand, save/export, versions.

## Acceptance and reporting

Include in the final response:

- Assumptions: units, version, template, and new versus existing drawing.
- Absolute output paths for DWG/DXF/PDF, JSON reports, and BMP/PNG previews.
- Checks actually performed: preflight, entity/layer counts, bounds, save/export, and native-preview review. For tracing, confirm no extra outer guides, internal construction geometry, colored decoration, or in-drawing review notes. State whether any window screenshot was unobscured.
- Human checks still required: sheet border, plotter, company standards, lineweights, fonts, scale, and professional drawing review.
