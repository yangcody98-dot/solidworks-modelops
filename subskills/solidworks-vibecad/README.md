# SolidWorks VibeCAD

`solidworks-vibecad` is the parametric design planning subskill from the `solidworks-automation` repository. It converts natural-language mechanical requirements into structured plans, manufacturing-rule checks, SolidWorks API execution outlines, and review gates.

## Why it is a subskill

Repeated mechanical design work benefits from reusable engineering assets:

```text
Domain knowledge + parameter schema + planning prompts + reliable API wrappers + automated review
```

This capability belongs alongside the repository's CNC fillet and chamfer, threaded-hole, assembly, and MCP workflows.

## Current capabilities

- Generate parametric design-plan JSON from natural-language requirements.
- Apply built-in rules for M3-M12 tap drills, clearance holes, CNC fillets and chamfers, and minimum wall thickness.
- Provide a constrained planning prompt to keep LLM output separate from unstable macro generation.
- Generate a SolidWorks API execution outline identifying the parent skill's wrapper for each step.
- Generate review gates requiring saving, export, multiple preview views, and a review report.

## Layout

```text
solidworks-vibecad/
├── SKILL.md
├── README.md
├── manifest.yaml
├── knowledge/
│   └── manufacturing_rules.yaml
├── prompts/
│   └── solidworks_parametric_planner.md
├── schemas/
│   └── design_plan.schema.json
├── scripts/
│   ├── plan_from_brief.py
│   └── sw_execution_outline.py
├── examples/
│   ├── motor_mount_brief.txt
│   ├── motor_mount_plan.json
│   └── motor_mount_execution.md
└── references/
    └── vibecad-roadmap.md
```

## Quick start

Run from the `solidworks-automation` repository root:

```powershell
py subskills\solidworks-vibecad\scripts\plan_from_brief.py `
  --brief-file subskills\solidworks-vibecad\examples\motor_mount_brief.txt `
  --out subskills\solidworks-vibecad\examples\motor_mount_plan.json

py subskills\solidworks-vibecad\scripts\sw_execution_outline.py `
  --plan subskills\solidworks-vibecad\examples\motor_mount_plan.json `
  --out subskills\solidworks-vibecad\examples\motor_mount_execution.md
```

## Example output

The example brief identifies:

- Base plate: `90 x 60 x 8 mm`
- Fastening holes: `M5` screw clearance holes, diameter `5.5 mm`
- Center hole: `22 mm`
- Outer corner fillets: `R6`
- Top-edge chamfer: `C1`
- Review: `SLDPRT + STEP + parameters_json + review_report_json + isometric_preview`

## Execution and feedback

The parent skill's `scripts/sw_closed_loop.py` connects read-only model snapshots, planned actions, real geometry checks, and bounded corrective feedback.
Run from the parent skill root:

```powershell
python scripts/sw_closed_loop.py validate --plan examples/closed_loop_plate.json
python scripts/sw_closed_loop.py run --plan examples/closed_loop_plate.json --out-dir output/closed_loop_run_01
```

The output directory must not already exist, and writes target only a newly created part. Current support covers rectangle and circle sketches, extrusions, cuts, and measurement bindings;
see the [closed-loop guide](../../references/closed-loop-modeling.md). The original requirement planner and execution outline remain available.
Fillets, chamfers, and pockets in the full default `cnc_mount` plan are not yet on the new action allowlist. Use the existing specialized tools for those features;
conversion must not silently remove them. After a failure, the agent revises the plan using the actual context and report rather than automatically changing key design dimensions.
