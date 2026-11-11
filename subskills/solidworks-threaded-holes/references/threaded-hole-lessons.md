# Lessons from SolidWorks threaded-hole modeling

## Findings from the validation case

The M6x1 internal blind-hole sample demonstrated a repeatable way to produce threaded-hole models with correct manufacturing intent through SolidWorks COM. A native Thread feature cannot be the only delivery path. The most reliable result used four layers:

- Physical tap-drill cut: a 5.0 mm drill for M6x1, with a blind-hole depth of 13 mm.
- Thread metadata: specification, depth, tap drill, and status in custom properties and JSON.
- Mouth chamfer: the M6 default C0.6, supporting manufacturing intent and visual recognition.
- Visible 3D helix: a preview aid indicating that the hole is threaded.

Final M6 sample parameters:

- Block: `40 x 30 x 16 mm`
- Drilling face: `top` by default, drilling inward from the upper face
- Thread: `M6x1 internal blind thread`
- Tap drill: `5.0 mm`
- Tap-drill depth: `13 mm`
- Thread depth: `12 mm`
- Mouth chamfer: `C0.6`
- Review result: `pass / 100`

## Live-tested interface findings

Enumeration values:

```python
swFmSweepThread = 87
swThreadMethod_Cut = 0
swThreadEndCondition_Blind = 0
swCosmeticStandardType_e.swStandardType_StandardISO = 8
swCosmeticEndConditions_e.swEndConditionBlind = 0
```

Live-tested `InsertCosmeticThread3` signature:

```python
InsertCosmeticThread3(Standard, StandardType, Size, Diameter, EndType, Depth, Note)
```

Local reflection exposed these writable `IThreadFeatureData` properties:

```text
Edge, StartEntity, EndCondition, BlindDepth, Pitch, ThreadMethod, Type, Size,
Diameter, PitchOverride, DiameterOverride
```

Native Thread creation remained unreliable:

- `CreateFeature(ThreadFeatureData)` returned `None` in a test.
- `LoadReferences(edge)` was unavailable or failed on the tested machine.
- Properties including `MajorDiameter/MinorDiameter/ThreadClass/ThreadType/ThreadSize` could not be set.

Attempt the operation, inspect its result, and use a recorded fallback when it fails. An API name alone does not establish support.

## Recommended representation strategy

Apply these layers in order:

1. Physical tap-drill geometry: required; stop if it fails.
2. `ThreadFeatureData`: attempt as an enhancement; failure does not invalidate the tap-drill geometry.
3. `InsertCosmeticThread3`: attempt for drawing and feature-tree semantics; inspect the saved tree even when it returns an object.
4. A 3D sketch helix: a visible fallback, not a physical cut thread profile.
5. Custom properties: required as a reliable record of the final thread intent.

For STEP:

- STEP can preserve the tap-drill hole, chamfer, and solid geometry.
- STEP may not preserve SolidWorks cosmetic-thread or drawing semantics.
- If CAM must recognize a physical thread profile directly, model an explicit helical sweep cut and separately assess build time, file size, and rebuild reliability.

## Reliable edge selection

Avoid `Edge1`, automatic feature names, and coordinate picks. Enumerate body edges:

```python
def circle_center_radius(edge):
    curve = get_com_member(edge, "GetCurve")
    if not curve or not get_com_member(curve, "IsCircle"):
        return None
    values = get_com_member(curve, "CircleParams")
    return (float(values[0]), float(values[1]), float(values[2])), float(values[6])

def select_top_hole_edge(model, x, y, z_top, radius):
    model.ClearSelection2(True)
    for body in get_com_member(model, "GetBodies2", 0, False) or []:
        for edge in get_com_member(body, "GetEdges") or []:
            data = circle_center_radius(edge)
            if not data:
                continue
            center, edge_radius = data
            if close(center[0], x) and close(center[1], y) and close(center[2], z_top) and close(edge_radius, radius):
                if edge.Select2(False, 0):
                    return edge
    raise RuntimeError("Hole-mouth circular edge not found")
```

Suggested matching tolerances:

- Center XY: `0.2 mm`
- Top-face Z: `0.5 mm`
- Radius: `0.3 mm`

## Common coarse metric tap drills

| Thread | Pitch mm | Tap drill mm |
|---|---:|---:|
| M3 | 0.5 | 2.5 |
| M4 | 0.7 | 3.3 |
| M5 | 0.8 | 4.2 |
| M6 | 1.0 | 5.0 |
| M8 | 1.25 | 6.8 |
| M10 | 1.5 | 8.5 |
| M12 | 1.75 | 10.2 |

Blind-hole rules of thumb:

- Thread depth: about `2D`, or as specified by the user.
- Tap-drill depth: thread depth + `1-2P`, without breaking through a part specified as blind.
- Mouth chamfer: about `0.1D`; `C0.6` is suitable for the M6 example.

## Common failures

### Native Thread returns None

Keep the tap-drill hole, chamfer, properties, and 3D helix, and report `thread_status`. Do not block the entire delivery while repeatedly pursuing the Thread API.

### CosmeticThread returns an object but is absent from the feature tree

This occurred in live testing. Inspect the saved feature tree or previews; a non-null return is not final proof of success.

### The hole-mouth circular edge cannot be found

Check that the tap-drill hole has rebuilt, the top-face reference height is correct, and the search uses the tap-drill radius rather than the nominal thread radius.

For a side hole, confirm that `--hole-face front/right` agrees with the modeling reference plane. The default `top` suits threaded holes on a mounting base's upper face.

### STEP has no thread lines

This is expected. The tap-drill hole and chamfer are the reliably retained geometry. Keep the 3D sketch for a visible indication; use an explicit helical cut when physical thread geometry is required.

## Review checklist

Read the review report and check at least:

- Output files exist and are nonempty.
- `model.features` contains a tap-drill cut such as `Cut_M6_Tap_Drill_Blind`.
- `model.features` contains a mouth chamfer such as `Chamfer_Thread_Mouth`.
- If native or cosmetic thread creation failed, model properties record the reason and fallback method.
- Isometric and top previews show correct hole positions and a visible mouth chamfer, with no unintended floating lines or scale errors.
