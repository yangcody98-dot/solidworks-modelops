# Lessons from CNC fillet and chamfer modeling

## Findings from the validation case

The CNC aluminum mounting-base case demonstrated that SolidWorks COM automation can generate parts with many fillets and chamfers when feature order and edge selection are controlled. The successful model included a base plate, central boss, mounting holes, counterbores, locating holes, a central long slot, lightening pockets, and native Fillet and Chamfer features. It passed the `sw_review` rule checks.

Key findings:

- Keep the main body's topology simple, then add complexity gradually.
- Large fillets and outer-edge chamfers were more reliable before hole and slot cuts than after all cuts.
- Selecting edge objects was more reliable than automatic edge names or coordinate picks.
- Check every SolidWorks feature result for `None` or `False`; stop or use an explicitly recorded fallback on failure.
- Saving can fail if a same-name output is already open in SolidWorks, commonly with `SaveAs` error code `1`.

## Recommended APIs and wrappers

Prefer the parent skill's existing wrappers:

```python
from sw_session import SolidWorksSession
from sw_connect import mm, get_com_member, create_empty_dispatch_variant
from sw_export import export_to_step
from sw_review import run_review
from sw_appearance import set_document_appearance
```

Frequently used SolidWorks APIs:

```python
model.FeatureManager.FeatureExtrusion3(...)
model.FeatureManager.FeatureCut4(...)
model.FeatureManager.FeatureFillet(195, radius, 0, 0, None, None, None)
model.FeatureManager.InsertFeatureChamfer(4, 1, distance, math.pi / 4, 0, 0, 0, 0)
edge.Select2(append, 0)
model.GetBodies2(0, False)
body.GetEdges()
edge.GetCurve()
curve.IsLine()
curve.IsCircle()
curve.CircleParams()
```

With pywin32, members such as `GetStartVertex`, `GetEndVertex`, and `FirstFeature` may appear as pseudo-callable properties. Read them through `get_com_member()`.

## Reliable edge selection

Avoid `Edge1`, `Edge2`, and empty-name coordinate selection. Recommended pattern:

```python
def edge_points(edge):
    start_vertex = get_com_member(edge, "GetStartVertex")
    end_vertex = get_com_member(edge, "GetEndVertex")
    if not start_vertex or not end_vertex:
        return None
    return (
        tuple(get_com_member(start_vertex, "GetPoint")),
        tuple(get_com_member(end_vertex, "GetPoint")),
    )

def midpoint(edge):
    points = edge_points(edge)
    if not points:
        return None
    start, end = points
    return tuple((start[i] + end[i]) / 2.0 for i in range(3))

def select_edges(model, predicate):
    model.ClearSelection2(True)
    count = 0
    for body in get_com_member(model, "GetBodies2", 0, False) or []:
        for edge in get_com_member(body, "GetEdges") or []:
            if predicate(edge) and edge.Select2(count > 0, 0):
                count += 1
    return count
```

Classify edges by midpoint, direction, line or circle type, center, and radius.

## Recommended feature order

For CNC mounting bases, connector blocks, and machined bases:

1. Extrude a rectangular base plate.
2. Extrude the top boss.
3. Add large outer-profile fillets and top and bottom edge chamfers.
4. Cut lightening pockets.
5. Cut through mounting holes.
6. Add counterbore or countersink steps.
7. Add locating holes.
8. Cut the central obround slot.
9. Add small hole-mouth chamfers.
10. Save, export STEP, and inspect the previews.

Placing step 3 after the holes and slots may cause lengthy solving on complex topology. If it must come later, reduce the radius and selected edge count first, and test each edge category separately.

## Radii and fallback strategy

Conservative defaults:

- Large vertical base-plate corner fillets: R6-R10
- Vertical boss corner fillets: R3-R6
- Outer-edge chamfers: C0.8-C2
- Boss top-edge chamfers: C0.5-C1
- Hole-mouth chamfers: C0.3-C0.8

Fallback order:

1. Reduce the radius or chamfer distance.
2. Select fewer edges per operation.
3. Move large fillets before the hole and slot cuts.
4. Omit small slot-mouth or pocket-floor fillets and record their value as `0`.
5. Preserve the main body, holes, slots, and essential outer-profile fillets, then complete an exportable model.

## Common failures

### An obround slot is half the requested width

`sw_part.sketch_slot(..., radius)` takes the end-arc radius, while native
`CreateSketchSlot(SlotCreationType, SlotLengthType, Width, ...)` takes the full slot width.
Pass `SlotLengthType=0` for the distance between end-arc centers and `Width=2*radius`; do not pass the radius for both arguments.
The SW2025 live-tested 42×14 slot had center distance 28, R7, and a through depth of 34, giving removed volume
`34*(28*14+49*pi)=18561.893361 mm³`. A non-null feature alone cannot detect a half-width slot; validate volume and B-Rep readback.

### Extrusion returns None

A common cause is an unclosed complex filleted sketch. Extrude a simple rectangle, then add native Fillet features to its vertical corners.

### Fillets or chamfers take too long

Likely causes include complex post-cut topology, excessive radius, or overly broad edge selection. Test base-plate vertical edges, boss vertical edges, top edges, bottom edges, and hole mouths separately.

### SaveAs error code 1

The target may already be open in SolidWorks. Close a same-name task-owned document before creating a replacement; do not close the user's original document:

```python
try:
    session.close(title=Path(output_part).name)
except Exception:
    pass
```

### The preview looks transparent or has unexpected colors

Check geometry separately from appearance. Confirm the review report and nonblank previews first. For controlled appearance, use `set_document_appearance(model, "silver")` or separate components in an assembly and color them individually.

## Review checklist

Read the review report and check at least:

- `evaluation.status`
- `checks.previews_created`
- `checks.previews_not_blank`
- `checks.expected_outputs_exist`
- Expected `Fillet`, `Chamfer`, and `Cut` features in `model.features`

After the rule checks pass, inspect the `isometric` and `top` previews for proportions, hole positions, counterbores, long slots, pockets, and fillet orientation.
