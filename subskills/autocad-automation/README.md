# AutoCAD Automation subskill

> Headless DXF previews and structural review are available. The allowlisted AutoCAD 2024 .NET backend has repeatedly passed real DWG/PDF/PNG, reopen, entity, layer, and dimension regressions. It is `verified` after the latest three runtime evidence sets are rechecked. ActiveX/COM native writes remain subject to live-test gates and must not be advertised as stable.

This is the AutoCAD/DWG/DXF subskill from `solidworks-automation-skill`. The parent covers SolidWorks 3D modeling, assemblies, drawings, and export. This subskill covers Windows desktop AutoCAD automation: 2D drafting, batch edits, layers, text, dimensions, DWG/DXF/PDF export, line-art vectorization, and drawing review.

## Use cases

- Create DWG, DXF, or AutoCAD drawings.
- Convert image line art into CAD entities and save DWG/DXF.
- Inspect layers, entity counts, bounds, text, blocks, external references, or outputs in a batch.
- Show incremental drawing in AutoCAD and export native previews for review.
- Add AutoCAD 2D drawings, machining profiles, laser-cutting DXF, or drawing cleanup to a SolidWorks workflow.

## Relationship to the parent

- `solidworks-automation`: SolidWorks COM connection, parts, assemblies, drawings, STEP/STL/PDF export, and 3D review.
- `autocad-automation`: AutoCAD COM connection, 2D DWG/DXF drafting, layers, dimensions, blocks, native previews, and drawing review.

Use the parent for native SolidWorks parts, assemblies, or drawings. Read this subskill for AutoCAD, DWG, DXF, 2D CAD drawings, image tracing, or batch DWG edits.

## Quick commands

Check and regress the AutoCAD .NET backend:

```powershell
python subskills\autocad-automation\scripts\acad_dotnet_preflight.py
python subskills\autocad-automation\scripts\acad_dotnet_regression.py --real-cad
```

The regression launches only its owned AutoCAD Core Console and runs only the fixed commands `CADSTUDIOPROBE` and `CADSTUDIOCREATE`. Desktop deployment should use a trusted path or signed plugin package; do not expose arbitrary code execution.

```powershell
python subskills\autocad-automation\scripts\acad_preflight.py --launch
```

```powershell
python subskills\autocad-automation\scripts\acad_draw.py `
  --input C:\temp\plan.json `
  --output C:\temp\result.dwg `
  --new
```

```powershell
python subskills\autocad-automation\scripts\acad_review.py C:\temp\result.dwg `
  --launch `
  --json C:\temp\review.json
```

```powershell
python subskills\autocad-automation\scripts\acad_preview.py `
  --source C:\temp\result.dwg `
  --output C:\temp\preview.png `
  --launch
```

## Image-to-CAD tracing requirements

For ordinary faithful tracing, the final drawing must contain only vectorized source lines. Do not retain guessed outer outlines, facial ellipses, logo triangles, ripples, replacement text, or review notes in the final DWG/DXF.

The final check must confirm zero entities on these auxiliary layers:

```text
PORTRAIT_OUTLINE, BODY_OUTLINE, JERSEY_OUTLINE,
OUTER_GUIDE, CONSTRUCTION, FACE_FEATURES,
LOGO_GEOMETRY, WATER_SPLASH, JERSEY_STRIPE,
TEXT_LOGO, TEXT_BRAND, REVIEW_NOTES
```

This rule comes from a real tracing-demo review: outlines, ellipses, triangles, and colored ripples added to improve recognition became unwanted CAD entities. Prioritize clean, faithful output without extra entities in ordinary tracing tasks.

## References

- `SKILL.md`: agent entry point and full workflow.
- `references/api-lookup.md`: API verification.
- `references/engineering-patterns.md`: layers, units, blocks, dimensions, and batch processing.
- `references/troubleshooting.md`: local COM behavior, DXF/BMP export, tracing contamination, and review pitfalls.
