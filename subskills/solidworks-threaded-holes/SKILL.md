---
name: solidworks-threaded-holes
description: SolidWorks automation subskill for internal threaded holes, including M3/M4/M5/M6/M8, tap-drill geometry, blind and through holes, mouth chamfers, cosmetic threads, visible 3D helices, and thread metadata. Use for tapped mounting holes, M6x1 blind holes, Hole Wizard/ThreadFeatureData/CosmeticThread workflows, STEP export, and threaded-hole review.
---

# SolidWorks Threaded Holes

## Key considerations

Creating a native `ThreadFeatureData` feature through SolidWorks COM can be unreliable across versions and interface languages. Use a layered delivery strategy:

1. Run the parent skill's preflight: `python ../../scripts/sw_preflight.py`.
2. Create correct physical geometry: tap-drill diameter, blind or through depth, and mouth chamfer.
3. Attempt a native Thread feature; if it fails, try `InsertCosmeticThread3`.
4. Regardless of native or cosmetic thread success, write the thread specification, tap-drill diameter, and depth to custom properties.
5. For samples requiring a visible thread indication, add a 3D sketch helix for preview review.
6. Save `SLDPRT`, export `STEP`, run `sw_review.run_review()`, and inspect previews and the feature tree.

## Recommended imports

Reuse the parent skill's scripts:

```python
import sys
sys.path.insert(0, r"C:\path\to\solidworks-automation-skill\scripts")

from sw_connect import mm, get_com_member, create_empty_dispatch_variant
from sw_session import SolidWorksSession
from sw_export import export_to_step
from sw_review import run_review
from sw_part import sketch, sketch_rectangle, extrude_boss
```

To generate a sample, run or copy this template:

```text
subskills/solidworks-threaded-holes/scripts/create_threaded_hole_template.py
```

For live-tested interface lessons and known pitfalls, read:

```text
subskills/solidworks-threaded-holes/references/threaded-hole-lessons.md
```

## Reliable workflow

1. Establish the specification: for example `M6x1.0`, internal or external, blind or through, thread depth, hole position, material, and whether explicit machinable thread geometry is required.
2. Choose the tap drill. Typical coarse internal metric values include `M3=2.5`, `M4=3.3`, `M5=4.2`, `M6=5.0`, `M8=6.8`, and `M10=8.5` mm.
3. Cut the tap-drill hole first using a circle sketch and `FeatureCut4`; do not begin with a complex helical sweep.
4. Find the circular mouth edge by enumerating `GetBodies2/GetEdges` and checking its center, radius, and top-face height. Select with `edge.Select2()` rather than `Edge1` or coordinate picks.
5. Attempt the thread representation:
   - Native Thread: `CreateDefinition(swFmSweepThread)` + `CreateFeature(thread_data)`.
   - Cosmetic thread: `InsertCosmeticThread3(8, "Tapped Hole", "M6x1.0", diameter, 0, depth, note)`.
   - Visible fallback: a short-segment helix in a 3D sketch named `Sketch_M6x1_Visible_Internal_Thread_Helix`.
6. Add the mouth chamfer last. Typical sizes are `C0.3-C0.8`; the M6 default is `C0.6`.
7. Write custom properties and parameter JSON, save, export STEP, and review.

## Template usage

Generate the default M6x1 internal blind-hole sample:

```powershell
python subskills/solidworks-threaded-holes/scripts/create_threaded_hole_template.py `
  --output-dir C:\CADAutomationWorkbench\solidworks_threaded_hole_output
```

Generate an M8x1.25 hole with custom block dimensions:

```powershell
python subskills/solidworks-threaded-holes/scripts/create_threaded_hole_template.py `
  --thread M8 `
  --block-length 60 `
  --block-width 36 `
  --block-thickness 20 `
  --thread-depth 16 `
  --output-dir C:\CADAutomationWorkbench\m8_threaded_hole_output
```

The default `--hole-face top` drills inward from the mounting base's top face. For side holes, pass `--hole-face front` or `--hole-face right`.

## Pitfalls

- Do not assume explicit helical thread geometry is included in STEP by default. A true helical sweep increases rebuild time and failure risk.
- Do not promise that `ThreadFeatureData` will succeed. `CreateFeature(ThreadFeatureData)` has returned `None` in local tests.
- Do not rely solely on `CosmeticThread`: it may return an object yet fail to appear consistently in the saved feature tree.
- Keep the tap-drill hole and mouth chamfer correct; they establish the physical geometry and manufacturing intent.
- Visible lines are not a drawing thread callout. State the specification, depth, and representation method in properties or delivery notes.
- Saving alone is insufficient. Inspect the review report and isometric and top previews.

## Validation requirements

Each completed run must produce:

- `*.SLDPRT`
- `*.step`
- `*_parameters.json`
- `*_review_report.json`
- `*_isometric.bmp/png`

Check at least:

- `evaluation.status` is `pass` or an explained `warn`.
- `expected_outputs_exist` is `True`.
- `previews_not_blank` is `True`.
- The feature tree contains the tap-drill cut, mouth chamfer, and at least one of Thread, CosmeticThread, or a visible helix representation.
