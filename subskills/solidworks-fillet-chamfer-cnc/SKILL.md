---
name: solidworks-fillet-chamfer-cnc
description: SolidWorks automation subskill for CNC parts with many fillets and chamfers. Use to create or modify machined mounts, connector blocks, enclosures, brackets, and counterbored plates, including FeatureFillet, InsertFeatureChamfer, reliable edge selection, hole-mouth chamfers, rounded rectangular outlines, lightening pockets, STEP export, and preview review.
---

# SolidWorks Fillet Chamfer CNC

## Key considerations

Reliable topology, edge selection, and feature order are the main challenges when automating parts with many fillets and chamfers. Use this default strategy:

1. Run the parent skill's preflight: `python ../../scripts/sw_preflight.py`.
2. Start with simple, reliable base geometry: rectangles, cylinders, bosses, holes, and slots. Avoid a complex filleted sketch at the outset.
3. Place large fillets and outer-edge chamfers before hole and slot cuts where possible.
4. Add holes, counterbores, locating holes, long slots, and lightening pockets after finishing the main body's edges.
5. Add small hole-mouth chamfers last. Small fillets that stall rebuilding may be reduced or omitted, with the change recorded in the parameter report.
6. Save the result, export STEP, run `sw_review.run_review()`, and inspect the isometric preview.

## Recommended imports

Reuse the parent skill's scripts:

```python
import sys
sys.path.insert(0, r"C:\path\to\solidworks-automation-skill\scripts")

from sw_connect import mm, get_com_member, create_empty_dispatch_variant
from sw_session import SolidWorksSession
from sw_export import export_to_step
from sw_review import run_review
from sw_appearance import set_document_appearance
```

For a template, copy or consult:

```text
subskills/solidworks-fillet-chamfer-cnc/scripts/create_cnc_mount_template.py
```

For detailed lessons and known pitfalls, read:

```text
subskills/solidworks-fillet-chamfer-cnc/references/cnc-fillet-chamfer-lessons.md
```

## Reliable workflow

1. Use unique names for new parts and output files to avoid `SaveAs` collisions. Close only this task's temporary documents; leave the user's original documents open.
2. Create a part, then the base plate, bosses, and required reference planes.
3. Enumerate body edges and select the edge object with `edge.Select2(append, 0)`. Do not rely on `Edge1` names or arbitrary coordinate picks.
4. Add native outer-profile features first:
   - Large vertical-edge fillets: `FeatureFillet(195, radius, ...)`
   - Top and bottom outer-edge chamfers: `InsertFeatureChamfer(4, 1, distance, pi/4, ...)`
5. Cut holes and slots:
   - Through mounting holes
   - Counterbore steps
   - Locating holes
   - Central obround slot
   - Lightening pockets
6. Finish with lightweight hole-mouth chamfers. Treat small fillets at complex slot mouths or pocket floors conservatively.
7. Write the parameter JSON, save SLDPRT, export STEP, and review the result.

For an L-shaped structure requiring a reinforcing rib, use the parent skill's `scripts/sw_native_ribs.py` after reading
[Native ribs and acceptance checks](../../references/native-ribs.md). Use the native Rib feature for the live-tested open single-line case.
Read back thickness, both-sides, direction, and draft settings after creation, and check sketch constraints, body merging, and added volume. Continue using the existing fillet, chamfer, hole, slot, and export workflows.

## Pitfalls

- Many fillets do not require a complex initial sketch. An unclosed sketch can make extrusion return `None`.
- Do not use `SelectByID2("", "EDGE", x, y, z, ...)` as the main selection strategy; views and topology changes can cause incorrect picks.
- Avoid applying all large fillets after every hole and slot cut. Complex topology can make SolidWorks solve very slowly or stall.
- Successful appearance changes do not prove correct geometry. Appearance APIs may produce unexpected transparency or colors; inspect the geometry in the review previews.
- Saving alone is insufficient. Confirm that `SLDPRT`, `STEP`, previews, and the review report exist and are nonempty.

## Validation requirements

Each completed run must produce:

- `*.SLDPRT`
- `*.step`
- `*_parameters.json`
- `*_review_report.json`
- `*_isometric.bmp` or a converted PNG

Check at least:

- `evaluation.status` is `pass` or an explained `warn`.
- `expected_outputs_exist` is `True`.
- `previews_not_blank` is `True`.
- The feature tree contains the expected `Fillet`, `Chamfer`, and `Cut` features.
