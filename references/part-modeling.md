# Part modeling API reference

## Sketch operations

### Selecting reference planes

```python
# English-language installation
model.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
# Chinese-language installation; preserve the localized API object name
model.Extension.SelectByID2("前视基准面", "PLANE", 0, 0, 0, False, 0, None, 0)
```

Reference-plane aliases (localized names are literal API object identifiers):
| English | Chinese API identifier | Normal direction |
|---|---|---|
| Front Plane | `前视基准面` | Z axis |
| Top Plane | `上视基准面` | Y axis |
| Right Plane | `右视基准面` | X axis |

### Sketch geometry quick reference

| Method | Arguments | Description |
|---|---|---|
| `CreateLine(x1,y1,z1, x2,y2,z2)` | Start/end coordinates (meters) | Line |
| `CreateCircleByRadius(cx,cy,cz, r)` | Center and radius | Circle |
| `CreateCenterRectangle(cx,cy,cz, rx,ry,rz)` | Center and corner | Center rectangle |
| `CreateCornerRectangle(x1,y1,z1, x2,y2,z2)` | Opposite corners | Corner rectangle |
| `CreateArc(cx,cy,cz, x1,y1,z1, x2,y2,z2, dir)` | Center, start/end, direction | Arc |
| `CreatePolygon(cx,cy,cz, sx,sy,sz, sides, inscr)` | Center, vertex, side count | Regular polygon |
| `CreateEllipse(cx,cy,cz, mx,my,mz, r)` | Center, major-axis endpoint, minor radius | Ellipse |
| `CreateSpline2(pointArray, closed)` | Points and closed flag | Spline |
| `CreateSketchSlot(type, w, w, ...)` | Type, width, endpoints | Slot |

### Sketch relations

```python
# Select entities before adding relations
model.SketchAddConstraints("sgHORIZONTAL")
```

Common relation types: `sgFIXED`, `sgHORIZONTAL`, `sgVERTICAL`, `sgCOLINEAR`, `sgPARALLEL`, `sgPERPENDICULAR`, `sgTANGENT`, `sgCONCENTRIC`, `sgEQUAL`, `sgSYMMETRIC`, `sgMIDPOINT`, `sgCOINCIDENT`

### Stable sketch selection

Prefer the context from `sw_part.sketch()` or the return from `end_sketch()`. Do not rely solely on `SelectByID2("Sketch1", "SKETCH", ...)`; Chinese-language SolidWorks 2024 has repeatedly returned `False` for name-based SKETCH selection.

Recommended:

```python
with sketch(model, "Front Plane") as sketch_name:
    sketch_circle(model, 0, 0, mm(25))
feature = extrude_boss(model, sketch_name, mm(50))
```

Manual sequence:

```python
start_sketch(model, "Front Plane")
sketch_circle(model, 0, 0, mm(25))
sketch_ref = end_sketch(model)
feature = extrude_boss(model, sketch_ref, mm(50))
```

Internally, `extrude_boss()` / `extrude_cut()` try the active sketch reference, cached creation reference, `FeatureByName`, then `SelectByID2("SKETCH")`. A leftover selection set is not proof that the sketch is selected.

## Feature operations

### FeatureExtrusion3 parameters

```python
feature_mgr.FeatureExtrusion3(
    Sd,           # bool: one direction (True) or two directions (False)
    Flip,         # bool: flip cut direction
    Dir,          # bool: reverse extrusion direction
    T1,           # int: end condition 1 (see below)
    T2,           # int: end condition 2 (bidirectional)
    D1,           # float: depth 1 (meters)
    D2,           # float: depth 2
    Dchk1,        # bool: draft 1
    Dchk2,        # bool: draft 2
    Ddir1,        # bool: outward draft direction 1
    Ddir2,        # bool: outward draft direction 2
    Dang1,        # float: draft angle 1 (radians)
    Dang2,        # float: draft angle 2
    OffsetReverse1, # bool: reverse offset 1
    OffsetReverse2, # bool: reverse offset 2
    TranslateSurface, # bool: translate surface
    Merge,        # bool: merge results
    UseFeatScope, # bool: automatic body scope
    UseAutoSelect, # bool: automatic selection
    T0,           # bool:
    StartOffset   # float: start offset
)
```

End-condition enums:
| Value | Name | Description |
|---|---|---|
| 0 | swEndCondBlind | Specified depth |
| 1 | swEndCondThroughAll | Through all |
| 2 | swEndCondThroughAllBoth | Through all, both directions |
| 5 | swEndCondUpToSurface | Up to surface |
| 6 | swEndCondMidPlane | Mid-plane |
| 7 | swEndCondUpToBody | Up to body |

### FeatureCut4 parameters

Similar to FeatureExtrusion3 but creates a cut. Additional parameters:
- `NormalCut`: normal cut.
- `FlipSide`: reverse the cut side.

### FeatureRevolve2 parameters

```python
feature_mgr.FeatureRevolve2(
    SingleDir,     # bool: single direction
    IsSolid,       # bool: solid revolve (True)
    IsThin,        # bool: thin-feature revolve
    IsCut,         # bool: revolved cut
    ReverseDir,    # bool: reverse direction
    BothDirectionUpToSameEntity, # bool
    Dir1Type,      # int: end condition (0=Blind)
    Dir2Type,      # int
    Dir1Angle,     # float: rotation angle (radians)
    Dir2Angle,     # float
    OffsetReverse1, # bool
    OffsetReverse2, # bool
    OffsetDistance1, # float
    OffsetDistance2, # float
    ThinType,      # int: thin-feature type
    ThinThickness1, # float
    ThinThickness2, # float
    Merge,         # bool
    UseFeatScope,  # bool
    UseAutoSelect  # bool
)
```

### Recommended stepped-shaft workflow

Prefer one half-section profile, centerline, and revolved boss for the main shaft rather than merging successive extruded cylinders. This keeps the tree shorter and makes shoulder positions and overall length easier to control from a parameter table.

Recommended sequence:

1. Describe shaft segments in millimeters using `start_mm`, `end_mm`, and `diameter_mm`.
2. Draw a centerline on `Front Plane` as the revolve axis.
3. Generate one closed half-section from segment radii.
4. Call `FeatureRevolve2(..., 2*pi, ...)` and immediately check that the returned feature is not `None`.
5. Record dimensional/geometric tolerances and surface roughness in properties or delivery requirements; do not distort nominal solid geometry to represent tolerances.

Minimal pattern:

```python
segments = [
    {"start": 0, "end": 43, "diameter": 56},
    {"start": 43, "end": 113, "diameter": 65},
]

with sketch(model, "Front Plane") as sketch_name:
    model.SketchManager.CreateCenterLine(mm(-5), 0, 0, mm(120), 0, 0)
    points = [(0, 0), (0, 28), (43, 28), (43, 32.5), (113, 32.5), (113, 0), (0, 0)]
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        model.SketchManager.CreateLine(mm(x1), mm(y1), 0, mm(x2), mm(y2), 0)

model.ClearSelection2(True)
model.Extension.SelectByID2(sketch_name, "SKETCH", 0, 0, 0, False, 0, create_empty_dispatch_variant(), 0)
feature = model.FeatureManager.FeatureRevolve2(
    True, True, False, False, False, False,
    0, 0, 2 * math.pi, 0,
    False, False, 0, 0, 0, 0, 0,
    True, True, True,
)
if feature is None:
    raise RuntimeError("Failed to create the stepped-shaft revolved body")
```

### Obround slots on cylindrical surfaces

For surface keyways, obround slots, or local recesses on a shaft, do not cut directly from its central reference plane. A central-plane cut may split the shaft open, leaving a broad planar opening instead of a surface recess.

Stable approach:

1. Create a plane parallel to `Front Plane`, offset approximately by the target cylinder radius.
2. Draw the obround with `sketch_slot()` on this tangent plane.
3. Represent slot depth with a blind cut. Try one direction, then reverse `flip` if it fails.
4. Hide the temporary plane afterward so orange reference geometry does not obscure previews.

```python
plane = model.FeatureManager.InsertRefPlane(8, mm(radius_mm), 0, 0, 0, 0)
plane.Name = "Plane_Keyway_Tangent"

model.Extension.SelectByID2(plane.Name, "PLANE", 0, 0, 0, False, 0, create_empty_dispatch_variant(), 0)
model.SketchManager.InsertSketch(True)
sketch_name = model.SketchManager.ActiveSketch.Name
sketch_slot(model, mm(x1), 0, mm(x2), 0, mm(slot_width_mm / 2))
model.SketchManager.InsertSketch(True)

feature = extrude_cut(model, sketch_name, mm(depth_mm), direction=True, flip=True)
if feature is None:
    feature = extrude_cut(model, sketch_name, mm(depth_mm), direction=True, flip=False)
if feature is None:
    raise RuntimeError("Failed to create the cylindrical-surface obround slot")
```

Note: the `radius` parameter in `CreateSketchSlot` relates to slot width; verify its actual behavior with a local test. For manufacturing-critical width, measure the export or verify it in a drawing.

### Fillets and chamfers

```python
# FeatureFillet parameters
feature_mgr.FeatureFillet(
    Options,   # int: 195 is a commonly used default
    R1,        # float: radius (meters)
    R2,        # float: second radius
    R3,        # float: third radius
    Rarray1,   # variant: radius array 1
    Rarray2,   # variant: radius array 2
    Rarray3    # variant: radius array 3
)

# InsertFeatureChamfer parameters
feature_mgr.InsertFeatureChamfer(
    Options,     # int: 4=angle-distance
    ChamferType, # int: 1=equal distance
    Width,       # float: distance (meters)
    Angle,       # float: angle (radians)
    OtherDist,   # float: other distance
    VertexDist1, # float
    VertexDist2, # float
    VertexDist3  # float
)
```

### Reliable fillet/chamfer boundaries

The primary difficulty is **stable edge/face selection**, not the API arguments. SolidWorks version, localization, feature order, and sketch profile can change generated `Edge`/`Face` names. Random-coordinate selection followed by FeatureFillet is not a reliable workflow.

Recommended strategies:

1. Baseline demonstrations and unattended batch scripts should not use optional fillets/chamfers as their success criterion.
2. When appropriate, use stable sketch geometry such as arcs, slots, or rounded rectangles to represent rounded outlines.
3. For actual fillet/chamfer features, enumerate bodies/faces/edges, filter geometrically, and select the entity objects. Do not depend on temporary `Edge1` names.
4. A failed appearance fillet may fall back to the straight-edged model, with the unapplied fillet explicitly recorded in review/delivery notes; do not conceal the omission.

### Native Rib

Use `sw_native_ribs.create_native_rib()` within the historically verified scope; detailed parameters, acceptance, and machine evidence are in
[native-ribs.md](native-ribs.md). Its thickness uses millimeters; the legacy meter-based `sw_part.rib()` remains available.

`IFeatureManager.InsertRib` has **10 parameters and returns void**. Do not infer success from its return value or omit the final
`IsDraftedFromWall`. Identify the new `Rib`, read back `Thickness`, `IsTwoSided`,
`ExtrusionDirection`, and draft state, then check full sketch definition, body merge, feature error codes, and added volume.
The exercised mode is an open single-line 2D sketch, symmetric two-sided thickness, parallel generation, and no draft. Other modes need separate validation.

## SelectByID2 entity types

| Type string | Description |
|---|---|
| `"PLANE"` | Reference plane |
| `"FACE"` | Face |
| `"EDGE"` | Edge |
| `"VERTEX"` | Vertex |
| `"SKETCH"` | Sketch |
| `"BODYFEATURE"` | Body feature |
| `"COMPONENT"` | Component |
| `"AXIS"` | Axis |
| `"SKETCHSEGMENT"` | Sketch segment |
| `"SKETCHPOINT"` | Sketch point |
| `"EXTSKETCHSEGMENT"` | External sketch segment |
| `"REFERENCECURVES"` | Reference curves |
