---
name: solidworks-modelops
description: Parametric SolidWorks modeling, named dimension edits, checkpoint recovery, and regression validation. Create or edit task-owned part copies, measure actual geometry, audit sketch constraints, and deliver native files and STEP exports; route other mechanical workflows to the included specialist modules as needed.
---

# SolidWorks ModelOps

Use one JSON interface for planning, native modeling, dimension edits, checkpoints, and acceptance checks.
The unified executor is **pilot** and covers basic parts only. Included specialist workflows do not
automatically become part of its transactional interface.

## Entry points

Run `python scripts/sw_preflight.py` first. Native operations require Windows, Python COM dependencies,
and an open, licensed SolidWorks instance. Explain missing dependencies before installing them.
This skill does not include SolidWorks software or a license.

Unified CLI:

```powershell
python scripts/sw_modeling.py validate --request examples/modeling_create.json
python scripts/sw_modeling.py run --request examples/modeling_create.json --out-dir output/create-001
python scripts/sw_modeling.py inspect --source C:\CAD\part.sldprt
python scripts/sw_modeling.py checkpoints --root output/create-001/checkpoints
```

`validate` does not connect to CAD. `inspect` reads the specified part only if it is already open;
it does not activate or open files. `run` requires a new output directory.
See [README](README.md) for complete requests and usage.

## Choose a mode

- **create**: Express the request as an existing operation plan using `sketch_rectangle`, `sketch_circles`,
  `extrude_boss`, and `extrude_cut`. Specifications and acceptance criteria must come from user-supplied
  dimensions, measurements, or explicitly recorded design assumptions. For detailed parameter planning,
  read [VibeCAD](subskills/solidworks-vibecad/SKILL.md) as needed.
- **edit**: Supply the source `SLDPRT` and exact `dimension@feature` name. `set_dimension` supports positive
  linear driving dimensions in the current configuration. Use `inspect` and its `dimensions` field to
  discover actual names. Stop if the source has unsaved changes so the disk snapshot is not confused
  with the in-memory model.
- **restore**: Supply the checkpoint root and ID, verify the file digest, copy it to a new file, then reopen
  it in SolidWorks to compare geometry, features, dimensions, and sketches.

Editing and recovery support only single-configuration parts without external dependencies.
Protect source files and documents from the original session as read-only. All writes must target
new documents or disk copies owned by the current task.

## Acceptance and failure handling

1. Create/edit requests must include measurable final geometry requirements. Empty criteria, a successful
   save, or a nonblank screenshot cannot establish that the specification passed.
2. Save the working part after each accepted step and create an immutable checkpoint containing the native
   file, SHA-256, measured context, and step metadata.
3. Check hole positions, diameters, body counts, volume, and bounds against explicit tolerances.
   SolidWorks bounding boxes are approximate and cannot prove precision dimension chains.
4. Before delivery, audit full definition of ordinary and absorbed sketches, driving dimensions, feature
   errors, and independent STEP reopening. Inspect the four views to confirm design intent.
5. On an edit failure, stop later steps, restore the last complete checkpoint to a new copy, and verify it
   by measurement. `status=recovered` means recovery passed while the original task failed:
   `task_succeeded=false`, CLI exit code 2. Fail if no valid checkpoint or sufficient recovery evidence
   exists. Do not shrink holes, reduce thickness, or remove required features to force acceptance.

Use `modeling_report.json` as the result record. Check `status`, `task_succeeded`, `source_protection`,
and `delivery` or `recovery`. Do not present a recovered artifact as successful delivery of the original request.

## Specialist routing

For tasks outside the unified operation allowlist, use the included specialist scripts as appropriate.
Explain that those workflows do not inherit this entry point's automatic checkpoint guarantees.

| Task | Read first |
|---|---|
| CNC parts with many fillets/chamfers | [CNC workflow](subskills/solidworks-fillet-chamfer-cnc/SKILL.md) |
| Threaded holes and thread representation | [Thread workflow](subskills/solidworks-threaded-holes/SKILL.md) |
| Native Hole Wizard and ribs | [Hole features](references/complex-hole-features.md), [ribs](references/native-ribs.md) |
| Assemblies, draggable mates, motion studies | [Assembly](references/assembly.md), [Motion](references/motion-study.md) |
| Drawings, BOM, multi-format delivery | [Drawing](references/drawing.md), [export](references/export.md) |
| Other inherited capabilities and execution lessons | [Upstream workflows](references/upstream-automation-guide.md) |

[capabilities.yaml](capabilities.yaml) separates inherited capabilities from the new entry point's
validated scope. Do not extrapolate to unverified features. For an unwrapped SolidWorks API, follow
[API lookup](references/api-lookup.md) before implementation and live acceptance testing.
Distinguish helical reference curves, cosmetic threads, and solid thread geometry. Validate animation,
real mates, and load analysis separately.

## Regression suite

```powershell
python scripts/sw_modeling_regression.py validate
python scripts/sw_modeling_regression.py run --out-dir output/regression-001
```

The four cases create a four-hole plate, change its thickness from 8 to 12 mm, actually change it to
14 mm before an intentionally incorrect expectation triggers recovery to 12 mm, and restore a checkpoint
in an independent Python process. Checks include analytical volume, all four hole specifications and
positions, constraints, reopened exports, and source file hashes. Record offline tests and native
SolidWorks regression separately. Test counts do not constitute engineering certification.

## License and provenance

The included automation foundation derives from the MIT-licensed `wzyn20051216/solidworks-automation-skill`.
Preserve [LICENSE](LICENSE) and [NOTICE](NOTICE.md). Public reports and examples use fixtures generated
for this work and exclude user project models.
