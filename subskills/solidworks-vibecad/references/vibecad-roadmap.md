# VibeCAD engineering roadmap

## Direction

Capture repeated mechanical design work as reusable engineering assets:

```text
Domain knowledge + parameter schema + planning prompts + reliable API wrappers + automated review
```

The LLM interprets intent and fills in parameters; the SolidWorks API performs deterministic operations; the knowledge base supplies engineering rules; the review workflow detects false success.

## Phase 1: Planning workflow

Completed:

- Example brief for a CNC mounting base
- Parametric design-plan JSON
- Initial manufacturing-rule knowledge base
- LLM planning prompt template
- SolidWorks execution outline
- JSON and Python syntax validation

Potential additions:

- More part families: connector blocks, L-brackets, shafts, and sheet-metal enclosures
- More standard-component rules: bearings, couplings, motor flanges, countersunk screws, and locating pins
- Stricter schemas for dimension ranges, hole pitch and edge distance, and process constraints

## Phase 2: Native SolidWorks executor

Prioritize a `cnc_mount` executor:

1. Run `sw_preflight.py`.
2. Read `design_plan.json`.
3. Create a part using `SolidWorksSession()`.
4. Create the planned base plate, holes, pockets, fillets, and chamfers.
5. Save `SLDPRT` and export `STEP`.
6. Call `sw_review.run_review()`.
7. Read the review report and use a recorded fallback and retry if the checks fail.

Key principles:

- Check return values from every long-argument SolidWorks API call.
- Convert all mm dimensions to meters through `sw_connect.mm()`.
- Prefer edge-object selection with `edge.Select2()` for fillets and chamfers.
- For threaded holes, establish correct tap-drill geometry, mouth chamfer, and metadata first.

## Phase 3: Expand the knowledge base

Prioritize frequent rules:

- M3/M4/M5/M6/M8/M10 coarse and fine threads and tap drills
- Recommended screw clearance, counterbore, and countersink dimensions
- CNC minimum wall thickness, minimum fillet radius, and chamfer defaults
- Sheet-metal bend radius, K-factor, and bend allowance
- Bearing bores, tolerances and fits, and retaining-ring grooves
- Motor mounting-hole patterns and flange standards

## Phase 4: User interfaces

Possible interfaces:

- CLI: a brief generates a plan and model in one workflow
- MCP: Codex or Claude operates SolidWorks through tool calls
- Small local web UI: enter requirements, adjust parameters, and preview review results
- Template library: successful cases become reusable design templates

## Metrics

- Reduction in time spent on repeated modeling
- First-attempt modeling success rate
- Automated review pass rate
- Number of manual changes
- Template reuse count
- Whether failure causes are captured in the knowledge base
