# Assemblies and motion mates

## Official references

- AddMate5: `https://help.solidworks.com/2023/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.iassemblydoc~addmate5.html`
- GetModelDoc2: `https://help.solidworks.com/2019/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icomponent2~getmodeldoc2.html`
- GetCorresponding: `https://help.solidworks.com/2019/English/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icomponent2~getcorresponding.html`
- IsCylinder / CylinderParams: `https://help.solidworks.com/2021/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISurface~IsCylinder.html`、`https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISurface~CylinderParams.html`
- Gear Mates: `https://help.solidworks.com/2024/English/solidworks/sldworks/t_Gear_Mates_SWassy.htm`
- Hinge Mates: `https://help.solidworks.com/2023/english/SolidWorks/sldworks/t_hinge_mates.htm`
- Mate Controller: `https://help.solidworks.com/2024/english/Solidworks/sldworks/c_assembly_mate_controller.htm`

## Inserting components

Prefer `add_component()` in `scripts/sw_assembly.py`. On Chinese-language SW2024 with pywin32,
`AddComponent4()` may return `None` without an exception. The wrapper first tries the
eight-argument `AddComponent5()` signature, then falls back to `AddComponent4()`. If both return null,
it silently opens the part in the SolidWorks session, reactivates the assembly, and retries `AddComponent5()`.

```python
from sw_assembly import add_component

component = add_component(asm_model, r"E:\parts\base.SLDPRT", x=0, y=0, z=0)
```

Stable low-level call:

```python
component = asm_model.AddComponent5(
    CompPath, 0, "", False, ConfigName, X, Y, Z
)
```

If `AddComponent4` / `AddComponent5` fails, check that the part file exists, the assembly is active, and the part has been saved to disk. If necessary, open the part first and reactivate the assembly. Real regression check:

```powershell
py -3.13 tests\solidworks_add_component_regression.py --output-dir C:\CADAutomationWorkbench\solidworks_add_component_regression
```

## Moving-assembly workflow

1. Create and save each part first. Close part documents that no longer need editing to limit the number of open documents.
2. Create an assembly and insert the base, bearing blocks, shafts, gears, cover, and other components.
3. Call `resolve_component(component)` before reading a component's features or faces; lightweight/suppressed components can make `GetModelDoc2()` return `None`.
4. Map part reference planes, cylindrical faces, or sketch entities into the assembly context with `IComponent2.GetCorresponding()`, then select them with `Select2()`.
5. Fixed components can be constrained with three plane-coincident or distance mates; do not fully lock rotating parts with three reference-plane mates.
6. Use concentric shaft/hole mates with `lock_rotation=False` to preserve rotation about the axis.
7. Use a gear mate for coupled rotation. Select gear axes, hole cylinders, cylindrical faces, or axis entities and supply the tooth-count ratio.
8. A cover hinge can use a concentric mate plus one plane-coincident/distance mate to leave one rotational degree of freedom. For Motion analysis, prefer the official GUI Hinge Mate or a higher-level MateFeatureData API.
9. Traverse MateGroup subfeatures after creation to confirm that real mates were written to the feature tree. A preview animation proves script-driven movement, not interactive dragging.
10. Export multiple views with `sw_review.py`, then manually drag a free component in SolidWorks to verify motion.

## Notes from published engineering resources

- Official Mechanical Mates documentation states that a gear mate enforces proportional rotation about the selected axes. A hinge mate is equivalent to concentric and coincident mates and can include angle limits.
- GoEngineer's mate tutorial describes mates as geometric constraints between components. Mechanical mates express gear, rack-and-pinion, screw, and universal-joint relationships; they are not contact simulation: `https://www.goengineer.com/blog/introduction-to-solidworks-mates`
- CodeStack's lightweight-component example explains that `GetModelDoc2()` can return null for lightweight/suppressed components. Resolve them or silently open their referenced models: `https://www.codestack.net/solidworks-api/document/assembly/components/lightweight-get-model-doc/`
- CAD Booster emphasizes that part and assembly contexts cannot be mixed. Prefer `GetCorresponding()` and `Select2()` when an object reference is available instead of coordinate clicks: `https://cadbooster.com/entities-and-getcorresponding-in-the-solidworks-api/`
- A null `GetModelDoc2()` from a lightweight component is common. Resolve it before mating; do not interpret `None` as proof that the part has no features.

## AddMate5 parameters

In SolidWorks 2015+, `AddMate5` has 15 parameters. Wrap its by-ref error code in a `VARIANT` for Python COM:

```python
errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
mate = asm_model.AddMate5(
    mate_type,          # swMateType_e
    align,              # swMateAlign_e; commonly 0=Aligned
    flip,               # bool
    distance,           # Distance mate value, meters
    distance_upper,     # Upper limit; equal to distance if unlimited
    distance_lower,     # Lower limit; equal to distance if unlimited
    gear_num,           # Gear mate numerator
    gear_den,           # Gear mate denominator
    angle,              # Angle, radians
    angle_upper,        # Upper angle limit
    angle_lower,        # Lower angle limit
    for_positioning_only,
    lock_rotation,      # Whether the concentric mate locks rotation
    width_mate_option,  # Width mate option
    errors,
)
```

Prefer the wrappers in `scripts/sw_assembly.py`:

```python
from sw_assembly import (
    add_concentric_mate_by_cylinders,
    add_gear_mate_by_cylinders,
    collect_mate_feature_summary,
)

add_concentric_mate_by_cylinders(
    asm,
    shaft_comp,
    bearing_comp,
    radius_a=(0.004, 0.006),
    radius_b=(0.004, 0.006),
    name="shaft_bearing_concentric",
    lock_rotation=False,
)

add_gear_mate_by_cylinders(
    asm,
    small_gear_comp,
    large_gear_comp,
    teeth_a=18,
    teeth_b=26,
    radius_a=(0.004, 0.008),
    radius_b=(0.004, 0.008),
    name="small_large_gear_ratio_18_26",
)

print(collect_mate_feature_summary(asm))
```

## Mate type enums

Common values historically verified against the local SW 2024 `SolidWorks.Interop.swconst.dll`:

| Value | Name | Description |
|---:|---|---|
| 0 | `swMateCOINCIDENT` | Coincident |
| 1 | `swMateCONCENTRIC` | Concentric |
| 2 | `swMatePERPENDICULAR` | Perpendicular |
| 3 | `swMatePARALLEL` | Parallel |
| 4 | `swMateTANGENT` | Tangent |
| 5 | `swMateDISTANCE` | Distance |
| 6 | `swMateANGLE` | Angle |
| 10 | `swMateGEAR` | Gear |
| 11 | `swMateWIDTH` | Width |
| 16 | `swMateLOCK` | Lock |
| 22 | `swMateHINGE` | Hinge |

Common component suppression states:

| Value | Name | Description |
|---:|---|---|
| 0 | `swComponentSuppressed` | Suppressed |
| 1 | `swComponentLightweight` | Lightweight |
| 2 | `swComponentFullyResolved` | Fully resolved |
| 3 | `swComponentResolved` | Resolved |
| 4 | `swComponentFullyLightweight` | Fully lightweight |

## Selection and assembly context

Stable sequence:

```python
from sw_assembly import (
    get_component_feature,
    get_assembly_entity,
    find_component_by_name,
    resolve_component,
    select_entities_for_mate,
)

component_a = find_component_by_name(asm, "shaft")
component_b = find_component_by_name(asm, "bearing")
resolve_component(component_a)
resolve_component(component_b)

feature_a = get_component_feature(component_a, ["前视基准面", "Front Plane"])  # Chinese/English Front Plane names
feature_b = get_component_feature(component_b, ["前视基准面", "Front Plane"])  # Chinese/English Front Plane names
entity_a = get_assembly_entity(component_a, feature_a)
entity_b = get_assembly_entity(component_b, feature_b)

select_entities_for_mate(asm, entity_a, entity_b, mark=1)
```

Notes:

- Resolve components before selecting entities; `SetSuppression2()` may clear the selection set.
- Select the first entity with `Select2(False, 1)` and append the second with `Select2(True, 1)`.
- Check `SelectionManager.GetSelectedObjectCount2(-1) == 2` before creating a mate.
- Gear and ordinary mates generally use selection mark `1`; Width Mate uses `16`, Cam-Follower uses `8`.

## Identifying cylindrical faces

The largest cylindrical face often identifies a shaft, hole, or gear axis:

```python
from sw_assembly import find_largest_cylinder_face

face = find_largest_cylinder_face(
    gear_component,
    min_radius=0.004,
    max_radius=0.008,
)
```

Low-level logic:

```python
bodies = part.GetBodies2(0, False)
for body in bodies:
    for face in body.GetFaces():
        surface = face.GetSurface()
        if surface.IsCylinder:
            params = surface.CylinderParams
            radius = params[6]  # Meters
```

## Interactive operation in SolidWorks

Interactive operation requires real mates without overconstraint:

- Open the `.SLDASM` in SolidWorks.
- Use `Move Component` to drag the shaft, gear, or cover.
- With a correct gear mate, rotating one gear about its axis drives the other at the configured ratio and direction.
- If dragging fails, check fixed components, Lock Rotation on concentric mates, extra planar mates locking rotation, and mate errors/overdefinition.

A script-generated GIF or preview video only proves movement through several positions. Interactive behavior depends on the SolidWorks mate solver and remaining degrees of freedom.

## Interference and motion limits

A gear mate does not prevent solid gear interference; it establishes a rotational ratio. For geometric safety:

- Run `InterferenceDetection` or the GUI interference check.
- Constrain travel with Limit Angle / Limit Distance.
- Save key positions in Mate Controller and generate a Motion Study animation.

```python
interference = asm.InterferenceDetection
interference.TreatSubAssembliesAsComponents = False
interference.TreatCoincidenceAsInterference = False
interference.Done()
count = interference.GetInterferenceCount()
```

## Large-assembly recommendations

- For more than 20 parts, generate in batches, save and close the part documents, then assemble them.
- Confirm that all component paths exist before insertion and record failed insertions.
- Disable unnecessary graphics refresh during automation; restore it, rebuild, and export previews at the end.
- Historical session troubleshooting: when too many open documents or internal COM errors cause instability, `CloseAllDocuments(False)` was tried before restarting SolidWorks. Apply session-clearing actions only within the user's document-protection scope.
