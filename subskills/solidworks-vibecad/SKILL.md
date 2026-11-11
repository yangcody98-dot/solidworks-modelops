---
name: solidworks-vibecad
description: SolidWorks VibeCAD parametric design planning subskill. Convert natural-language mechanical requirements into structured design plans, manufacturing-rule checks, SolidWorks API execution outlines, and review gates. Use for text-to-CAD workflows, reusable mechanical knowledge, planning prompts, parametric modeling plans, and families of CNC mounts, connector blocks, and brackets.
---

# SolidWorks VibeCAD

## Purpose

This subskill turns natural-language ideas into executable, reviewable SolidWorks parametric design plans. It captures repeated mechanical design work as reusable assets:

```text
Domain knowledge + parameter schema + planning prompts + reliable API wrappers + automated review
```

The LLM interprets intent and fills in parameters; the SolidWorks API performs deterministic operations; the knowledge base supplies engineering rules; and the review workflow detects apparent success with incorrect geometry.

## Use cases

- Convert a natural-language part description into a parametric modeling plan.
- Create reusable templates for CNC mounts, connector blocks, L-brackets, base plates, and hole patterns.
- Record rules for tap drills, clearance holes, counterbores, chamfers, fillets, and minimum wall thickness.
- Supply JSON plans and risk gates to a SolidWorks executor.
- Turn successful cases into reusable templates instead of rewriting macros for each task.

## Workflow

1. Read the brief and establish the part family, process, material, output formats, and constraints.
2. Use `knowledge/manufacturing_rules.yaml` for conservative defaults.
3. Use `prompts/solidworks_parametric_planner.md` to produce a structured plan.
4. Validate the fields against `schemas/design_plan.schema.json`.
5. Run `scripts/plan_from_brief.py` for a local rule-based plan, or save the LLM output as JSON using the same schema.
6. Run `scripts/sw_execution_outline.py` to generate the SolidWorks execution outline.
7. For actual basic-part execution, read the parent skill's `references/closed-loop-modeling.md` and use `scripts/sw_closed_loop.py` for read-only context, stepwise execution, and measured feedback. Route unsupported operations to the existing specialized subskills; do not silently omit them.

## Quick commands

```powershell
py subskills\solidworks-vibecad\scripts\plan_from_brief.py `
  --brief-file subskills\solidworks-vibecad\examples\motor_mount_brief.txt `
  --out subskills\solidworks-vibecad\examples\motor_mount_plan.json

py subskills\solidworks-vibecad\scripts\sw_execution_outline.py `
  --plan subskills\solidworks-vibecad\examples\motor_mount_plan.json `
  --out subskills\solidworks-vibecad\examples\motor_mount_execution.md
```

## Relationship to the parent skill

- `solidworks-automation`: SolidWorks connection, modeling, export, and review.
- `solidworks-vibecad`: natural language to parametric design plans.
- `solidworks-fillet-chamfer-cnc`: execution lessons for CNC parts with many fillets and chamfers.
- `solidworks-threaded-holes`: execution lessons for tap drills and thread representations.

When a plan includes a CNC part with many fillets or chamfers, read:

```text
subskills/solidworks-fillet-chamfer-cnc/SKILL.md
```

When it includes M3/M4/M5/M6/M8 threaded holes, read:

```text
subskills/solidworks-threaded-holes/SKILL.md
```

## Pitfalls

- Do not have the LLM directly generate long-argument SolidWorks COM calls.
- A plan JSON file does not prove geometry success. Run it in SolidWorks and review it with `sw_review`.
- Conservative defaults are acceptable for uncertain parameters, but record them in `assumptions`.
- Distinguish clearance, counterbored, and tapped fastening holes. An `M5 screw mounting hole` must not automatically become an M5 tapped hole.
- The output must include `review_plan` before automated modeling begins.

## Current status

The original entry point continues to generate requirement plans and execution outlines. `scripts/sw_closed_loop.py` adds basic new-part execution,
context parameter binding, and geometry feedback after each step. It remains `pilot`; see the parent skill's `references/closed-loop-modeling.md` for scope and usage.
Fillets, chamfers, and pockets in the default complete CNC plan are not yet included in that executor's allowlist and still use the existing specialized workflows. Source models remain read-only and are not modified in place.
