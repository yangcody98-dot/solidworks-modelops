# CAD Automation Delivery Workbench MVP — historical specification

Version: v0.1

Date: 2026-07-25
Related research: `docs/market-research-2026.md`

> Inherited upstream product proposal. The requirements, defaults, targets, UI, and schemas below describe that historical MVP, not delivered ModelOps functionality. Its v0.1 label belongs to the original proposal and does not expand the ModelOps v0.1 pilot contract. See [README](../README.md), [capabilities.yaml](../capabilities.yaml), and [VALIDATION.md](VALIDATION.md) for current scope and evidence.

## 1. Position and success criteria

Working name: CAD Automation Delivery Workbench. The proposed local workflow served mechanical engineers and 3D-print prototyping users: structured parameters → actual enclosure geometry → engineering drawings → rule review → archived delivery. It did not propose a new CAD kernel, cloud collaboration, or full PLM.

Users should create a `3d_print_shell` project, specify outer dimensions/walls/holes/slots/bosses/interfaces, create actual SolidWorks cuts, generate SolidWorks Drawing or AutoCAD drawings, pass P0 review, and receive a complete package.

| Metric | Proposed MVP target, not an observed result |
| --- | --- |
| Project creation to confirmed parameters | Within 5 minutes |
| Modeling script execution | Within 10 minutes |
| Initial drawing | Within 5 minutes |
| Missing P0 drawing annotations | 0 |
| Traceability | Every output recorded in the manifest |
| Failure diagnosis | Stage, cause, and recommendation for every failure |

## 2. Technical boundary and users

All CAD, references, parameters, and reviews were to remain local, without a rented server or cloud queue. Proposed stack: PySide6/Qt UI; Python with pywin32/comtypes; SolidWorks COM and AutoCAD COM; local JSON/Markdown/directories; PyInstaller packaging; GitHub updates.

Out of scope: geometry kernel, browser service, collaboration/accounts, arbitrary fully automatic complex CAD, enterprise PDM/PLM, and a general Python/VBA/AutoLISP execution interface for ordinary users.

Primary users were individual mechanical designers, automation engineers, makers, and prototype users. Priorities were actual openings, printability, familiar Chinese drafting conventions, complete feature locations, and usable manufacturing/customer files. Required environment: Windows; SolidWorks installed and launched once; AutoCAD installed and launched once when using that drawing route; Python 3.10+; `pywin32`/`comtypes`. AutoCAD could be omitted for SolidWorks Drawing-only use.

## 3. Information architecture and workflow

The proposed layout had left navigation, a central task form, and right review/output/log panels. Navigation: Projects, New Project, Parameter Templates, Generate Model, Generate Drawing, Review, Delivery, Skills. Actions: Save Parameters, Generate Model, Generate Drawing, Review, Open Output.

### Project creation and references

Collect project name, `3d_print_shell`, output directory, default unit `mm`, default GB/T-style drawing, default AutoCAD DWG/DXF exports, and optional native SolidWorks drawing. Create the project directory, `project.json`, `inputs/`, `outputs/`, `reviews/`, `previews/`, `logs/`, and check CAD/Python dependencies.

Accept `jpg`, `png`, `jpeg`, and `bmp` for appearance/location reference. Images cannot establish manufacturing dimensions. Every hole, slot, interface, fluid port, screw hole, and boss needs specification and location in the parameter form.

### Parameters and modeling

Forms are primary; prompts supplement them. Require envelope, wall/bottom thickness, fillets/chamfers, holes/slots, bosses/mounts, drawing settings, and technical requirements. Read `parameters.json`, run or generate a SolidWorks builder, form the shell via shelling/Boolean cuts, cut all openings, add bosses/ribs/fillets/chamfers, save SLDPRT, export STEP/STL, and review.

Acceptance requires nonempty geometry, matching envelope, actual wall thickness, feature quantities matching parameters, actual cuts rather than decorative sketches, and a nonempty plausibly sized STL.

### Drawings and review

SolidWorks Drawing would provide orthographic/isometric views, dimensions, and PDF; AutoCAD would provide DWG/DXF, hole/slot tables, and title blocks. The historical proposal prioritized AutoCAD for Chinese file-format/drafting needs, subject to actual backend availability.

Required contents: border/title, units/scale, front/top/right or necessary section, isometric reference, total dimensions, wall/bottom thickness, hole/slot specifications/quantities/locations, technical requirements, and a feature schedule.

Machine review: file existence, reasonable DWG/DXF bounds, layers, actual dimension count, hole/slot counts, title/table presence, complete `review.json` schema. Visual review: dimension obstruction, crossed-view leaders, overlapping text, title-block intrusion, readable locations, and accepted drafting conventions.

## 4. Page and field specifications

### Project list

Show recent projects, name, type, modified time, last state, and output path. Support new/open/output-folder/duplicate. Deleting a record must not delete source files unless the user explicitly selects file deletion.

### New project

| Field | Type | Default | Required | Meaning |
| --- | --- | --- | --- | --- |
| project_name | text | Empty | Yes | Project name |
| project_type | select | 3D-print enclosure | Yes | Only MVP project type |
| output_root | folder | User selection | Yes | Output root |
| unit | select | mm | Yes | mm only initially |
| drawing_standard | select | GB/T style | Yes | Later enterprise templates |
| need_dwg | checkbox | true | No | DWG export |
| need_dxf | checkbox | true | No | DXF export |
| need_pdf | checkbox | true | No | PDF export |
| need_stl | checkbox | true | No | STL export |
| need_step | checkbox | true | No | STEP export |

### Envelope

| Field | Type | Unit | Required | Validation |
| --- | --- | --- | --- | --- |
| outer_length | number | mm | Yes | > 0 |
| outer_width | number | mm | Yes | > 0 |
| outer_height | number | mm | Yes | > 0 |
| wall_thickness | number | mm | Yes | >= 0.8 |
| bottom_thickness | number | mm | Yes | >= 0.8 |
| corner_radius | number | mm | No | >= 0 |
| edge_chamfer | number | mm | No | >= 0 |
| shell_open_direction | select | — | Yes | top / bottom / side |

### Printing

| Field | Type | Unit | Default | Meaning |
| --- | --- | --- | --- | --- |
| print_process | select | — | FDM | FDM / SLA / SLS; prioritize FDM |
| nozzle_diameter | number | mm | 0.4 | FDM nozzle |
| hole_compensation | number | mm | 0.2 | Suggested diameter allowance |
| fit_clearance | number | mm | 0.3 | Assembly clearance |
| min_wall_warning | number | mm | 1.2 | Warn below this threshold |

These are proposed configurable process defaults, not universal manufacturing guarantees.

### Holes

Each hole needs type, specification, quantity, face, datum edges, and center location.

| Field | Type | Unit | Required | Meaning |
| --- | --- | --- | --- | --- |
| id | text | — | Yes | Example H1 |
| name | text | — | Yes | Example display mounting hole |
| hole_type | select | — | Yes | round / counterbore / countersink / threaded / slot |
| face | select | — | Yes | front / back / left / right / top / bottom |
| diameter | number | mm | Conditional | Round-hole diameter |
| width | number | mm | Conditional | Slot width |
| length | number | mm | Conditional | Slot length |
| quantity | number | count | Yes | >= 1 |
| datum_x | select | — | Yes | left / right / centerline |
| datum_y | select | — | Yes | bottom / top / centerline |
| center_x | number | mm | Yes | Relative to X datum |
| center_y | number | mm | Yes | Relative to Y datum |
| pitch_x | number | mm | Conditional | Horizontal pattern pitch |
| pitch_y | number | mm | Conditional | Vertical pattern pitch |
| through | checkbox | — | Yes | Through-hole flag |
| note | text | — | No | Process note |

### Interface openings

Interface openings follow the same mandatory geometry/dimension rules; descriptive text alone is insufficient. Examples: USB-C, round DC, HDMI, RJ45, button, LED, display, fluid port, ventilation slot.

| Field | Type | Unit | Required |
| --- | --- | --- | --- |
| id | text | — | Yes |
| interface_type | select | — | Yes |
| face | select | — | Yes |
| cutout_width | number | mm | Conditional |
| cutout_height | number | mm | Conditional |
| cutout_diameter | number | mm | Conditional |
| corner_radius | number | mm | No |
| center_x | number | mm | Yes |
| center_y | number | mm | Yes |
| quantity | number | count | Yes |
| clearance | number | mm | No |

### Bosses

| Field | Type | Unit | Required | Meaning |
| --- | --- | --- | --- | --- |
| id | text | — | Yes | Example B1 |
| screw_size | select | — | Yes | M2 / M2.5 / M3 / M4 |
| boss_outer_diameter | number | mm | Yes | Outer diameter |
| hole_diameter | number | mm | Yes | Screw/insert hole |
| boss_height | number | mm | Yes | Height |
| face | select | — | Yes | Host face |
| center_x | number | mm | Yes | X location |
| center_y | number | mm | Yes | Y location |
| quantity | number | count | Yes | Count |
| rib_enabled | checkbox | — | No | Add reinforcement ribs |

### Execution and review pages

```text
preflight -> build_model -> export_model -> build_drawing -> export_drawing -> review -> package
```

For each stage, show `waiting / running / passed / warning / failed`, start/end times, logs, failure cause, and recommended action. The review page groups model/drawing/printability/package checks. `pass` means deliverable, `warning` needs human confirmation, and `fail` requires rework. Any failed P0 rule forces overall `fail`.

## 5. Proposed project directory

```text
<output_root>/<project_slug>/
  project.json
  parameters.json
  inputs/reference_001.png
  inputs/brief.md
  generated/build_model.py
  generated/build_drawing.py
  generated/drawing_plan.json
  outputs/model/<project>.sldprt
  outputs/model/<project>.step
  outputs/model/<project>.stl
  outputs/drawing/<project>.dwg
  outputs/drawing/<project>.dxf
  outputs/drawing/<project>.pdf
  outputs/package/<project>_delivery.zip
  previews/model_iso.png
  previews/model_front.png
  previews/drawing_preview.png
  previews/package_cover.png
  reviews/model_review.json
  reviews/drawing_review.json
  reviews/printability_review.json
  reviews/final_review.json
  logs/run_YYYYMMDD_HHMMSS.log
  README_DELIVERY.md
```

## 6. Historical data examples

These schemas are historical workbench examples, not the ModelOps modeling-request schema. Keys, enums, timestamps, and numeric fixture values are retained.

### project.json

```json
{
  "schema_version": "0.1",
  "project_id": "20260725_001",
  "project_name": "ai_cpu_cooling_shell",
  "project_type": "3d_print_shell",
  "unit": "mm",
  "drawing_standard": "GB_T_style",
  "created_at": "2026-07-25T20:00:00+08:00",
  "updated_at": "2026-07-25T20:00:00+08:00",
  "output_root": "C:/Users/current/Documents/CADAutomationWorkbench",
  "status": "draft"
}
```

### parameters.json

```json
{
  "schema_version": "0.1",
  "units": "mm",
  "shell": {
    "outer_length": 120,
    "outer_width": 80,
    "outer_height": 35,
    "wall_thickness": 1.6,
    "bottom_thickness": 2.0,
    "corner_radius": 4,
    "edge_chamfer": 0.5,
    "open_direction": "top"
  },
  "printing": {
    "process": "FDM",
    "nozzle_diameter": 0.4,
    "hole_compensation": 0.2,
    "fit_clearance": 0.3,
    "min_wall_warning": 1.2
  },
  "features": {
    "holes": [],
    "cutouts": [],
    "bosses": [],
    "vents": []
  },
  "drawing": {
    "paper_size": "A3",
    "scale": "1:1",
    "title": "3D-printed enclosure",
    "material": "PLA/PETG",
    "projection": "first_angle",
    "required_exports": [
      "dwg",
      "dxf",
      "pdf",
      "png"
    ]
  }
}
```

### final_review.json

```json
{
  "schema_version": "0.1",
  "overall_status": "fail",
  "project_id": "20260725_001",
  "checked_at": "2026-07-25T20:30:00+08:00",
  "checks": [
    {
      "id": "drawing-hole-position-complete",
      "severity": "P0",
      "status": "fail",
      "target": "drawing",
      "message": "Interface opening I1 lacks X/Y center-location dimensions",
      "suggestion": "Add center-location dimensions from the left and bottom datums"
    }
  ],
  "outputs": {
    "sldprt": "outputs/model/project.sldprt",
    "step": "outputs/model/project.step",
    "stl": "outputs/model/project.stl",
    "dwg": "outputs/drawing/project.dwg",
    "dxf": "outputs/drawing/project.dxf",
    "pdf": "outputs/drawing/project.pdf",
    "preview": "previews/drawing_preview.png"
  }
}
```

## 7. Mandatory P0 checks

### Model

| ID | Check | Failure condition |
| --- | --- | --- |
| model-file-exists | Model file | Missing or suspicious SLDPRT/STEP/STL size |
| model-solid-body | Solid geometry | No solid or unexpected solid count |
| model-shell-thickness | Wall/bottom | Unmodeled or below requested thickness |
| model-cut-through | Actual openings | Sketches/decorations rather than cuts through the specified face |
| model-feature-count | Feature quantity | Model hole/slot count differs from parameters |
| model-print-scale | Units | STL scale does not correspond to mm |

### Drawing

| ID | Check | Failure condition |
| --- | --- | --- |
| drawing-frame-title | Border/title | Missing border, title, units, or scale |
| drawing-main-dimensions | Envelope | Missing any length/width/height |
| drawing-wall-dimensions | Wall/bottom | Missing enclosure wall or bottom thickness |
| drawing-hole-spec | Feature specification | Missing type, specification, or count |
| drawing-hole-position | Locations | Missing X/Y, center distance, or datum dimensions |
| drawing-real-dimensions | Dimension entities | Critical dimensions imitated by lines/text |
| drawing-leader-crossing | Leaders | Across views, holes, centerlines, or text |
| drawing-overlap | Readability | Dimension/text/table overlap impairs reading |
| drawing-title-intrusion | Title area | Dimensions/text enter title block |
| drawing-hole-table | Schedule | Dense features lack a table or specifications/counts/locations |

### Printability

| ID | Check | Failure condition |
| --- | --- | --- |
| print-min-wall | Minimum wall | Below the user's hard limit |
| print-open-hole | Required opening | Requested opening is not cut |
| print-fit-clearance | Clearance | Required assembly lacks clearance |
| print-stl-valid | STL | Missing, empty, or incorrect scale |

## 8. Default drawing conventions

Proposed defaults: A3, with A4 when appropriate; mm; 1:1 or 1:2 / 2:1 to fit; FangSong-style Chinese typeface with a recorded available-Chinese-font fallback; separately layered thick/thin visible, center, hidden, and dimension lines; bottom-right title block; front/top/right or section plus isometric reference; hole/slot tables in dense areas. GB/T-style presentation does not replace company drawing review. A supplied enterprise template takes precedence.

## 9. Delivery package

```text
01_model/
  project.sldprt
  project.step
  project.stl
02_drawing/
  project.dwg
  project.dxf
  project.pdf
  drawing_preview.png
03_review/
  model_review.json
  drawing_review.json
  printability_review.json
  final_review.json
04_source/
  project.json
  parameters.json
  generated_scripts/
README_DELIVERY.md
```

Delivery notes must state project name, units, material/printing assumptions, file descriptions, drawing standards, review status, and outstanding human confirmations.

## 10. States and errors

```text
draft -> ready -> running -> generated -> reviewing -> pass
                                      -> warning
                                      -> failed
```

Stage states: `waiting`, `running`, `passed`, `warning`, `failed`, `skipped`.
Any P0 failure forces project `failed`; P1 failure can yield `warning`. Only complete required outputs and passed P0 checks allow `pass`.

Errors must be structured:

```json
{
  "stage": "build_drawing",
  "error_code": "AUTOCAD_COM_REJECTED",
  "message": "AutoCAD COM call was rejected",
  "retryable": true,
  "suggestion": "Retry when AutoCAD is idle; close modal dialogs or restart AutoCAD if needed"
}
```

| Code | Stage | Response |
| --- | --- | --- |
| SOLIDWORKS_NOT_FOUND | preflight | Install/start SolidWorks |
| PYWIN32_MISSING | preflight | Install dependencies |
| AUTOCAD_NOT_FOUND | preflight | Install/start AutoCAD |
| AUTOCAD_COM_REJECTED | build_drawing | Serial retry; request closing modal dialogs when needed |
| FEATURE_PARAM_INCOMPLETE | validate_parameters | Stop generation; supply feature locations |
| MODEL_CUT_MISSING | review_model | Rework model |
| DRAWING_DIM_MISSING | review_drawing | Rework drawing |
| EXPORT_FILE_MISSING | package | Export again |

## 11. Historical UI priorities and development stages

P0 pages: project list, new project, enclosure parameters, execution logs, review report, output files. P1: skill versions, rule configuration, enterprise templates, project duplication. P2: visual hole-position editor, 3D preview, drawing comments, template marketplace.

1. **Runnable prototype:** create desktop directory, window/navigation, projects/forms, local JSON, mock execution state machine, and output-folder opening. Produce `review.json` and delivery directories.
2. **Native model:** integrate `sw_preflight.py`, SolidWorks builders, SLDPRT/STEP/STL, previews, and model review.
3. **Drawings:** integrate `acad_preflight.py`, `drawing_plan.json`, AutoCAD drawing, DWG/DXF/PDF/PNG, and P0 review.
4. **Package:** collect outputs, write delivery notes, ZIP, and final-state page.

Unresolved questions included cross-version AutoCAD preview export, lower-rework SolidWorks versus AutoCAD drawing routes, robust proof of through cuts, machine-versus-human P0 coverage, and built-in versus company-supplied frames.

The proposed next step was `apps/desktop/`: PySide6 window, project creation, forms, local project directories, mock execution, and `review.json`. Native CAD integration was to follow after validating the mock user flow. This sequence is a historical plan, not an implementation or manufacturing-readiness claim.
