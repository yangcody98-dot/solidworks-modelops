# Automating compound holes and slots

## Supported scope

`scripts/sw_hole_features.py` uses sketches and cut features to create:

- Blind holes with a specified depth.
- Through holes.
- Two-stage compound holes with a through bore and cylindrical counterbore.
- Through holes with a conical countersink of a specified included angle.
- Straight slots with semicircular ends, through or blind.
- Hole patterns at explicit coordinates.

`sw_hole_features.py` retains these geometric-hole interfaces. The separate `sw_native_holes.py`
`create_native_counterbore(model, position_mm, hole_diameter_mm, counterbore_diameter_mm, counterbore_depth_mm, name=...)`
uses real `HoleWizard5` and has historical SW2025 tests for ISO/M8 cylindrical counterbores. Prefer native features for standard fastener counterbores,
rather than calling two cuts a Hole Wizard feature. Do not reconstruct unverified Hole Wizard signatures from memory.

The native interface reads back `HoleWzd`, Type14, `ThruHoleDiameter`, `CounterBoreDiameter`,
`CounterBoreDepth`, through-all condition, ISO standard, and actual 2D positions. Only its returned `feature` field is a COM handle;
the other fields are JSON-serializable. Fully dimension and constrain the positioning subsketch with `sw_sketch_constraints` before closing it,
then verify status 3 in final review. Native feature parameters control the automatically generated profile; do not delete its valid internal anchors.
The interfaces use different units: the new native interface uses mm; the original geometric interface still uses meters.

For multiple holes of the same specification, use `create_native_counterbore_group(model, positions_mm, hole_diameter_mm,
counterbore_diameter_mm, counterbore_depth_mm, name=...)`. It creates one `HoleWzd`,
places all points in its single 2D positioning sketch, and supplies dimensions and relations. Convert model coordinates with
`ModelToSketchTransform`; after closing, read every point through the inverse transform and verify count, position, and full definition.
Input positions must be distinct and lie on one planar face. Different specifications or support faces require separate features.

## Units and reference frames

- The geometric interfaces take all lengths in meters; use `sw_connect.mm()` to convert.
- `center`, `start`, and `end` are local 2D coordinates on the target sketch plane.
- The default reference is `Front Plane`; `sw_part.start_sketch()` handles the Chinese localization.
- Creation evidence includes meter and millimeter fields. Millimeter fields are for reporting and are not passed back to COM.

## Example

```python
from sw_connect import mm
from sw_hole_features import (
    create_blind_hole,
    create_counterbore_hole,
    create_countersink_hole,
    create_semicircular_slot,
)

blind = create_blind_hole(model, (mm(20), mm(20)), mm(8), mm(10), name="H1_Blind")
counterbore = create_counterbore_hole(
    model,
    (mm(50), mm(20)),
    hole_diameter=mm(6),
    counterbore_diameter=mm(12),
    counterbore_depth=mm(4),
    name="H2_Counterbore",
)
countersink = create_countersink_hole(
    model,
    (mm(80), mm(20)),
    hole_diameter=mm(5),
    countersink_diameter=mm(10),
    included_angle_deg=90,
    name="H3_Countersink",
)
slot = create_semicircular_slot(
    model,
    (mm(30), mm(50)),
    (mm(60), mm(50)),
    width=mm(10),
    depth=0,
    name="S1_ObroundSlot",
)
```

## Acceptance evidence

Creation functions return parameter evidence, not a geometric acceptance decision. Before delivery:

1. Read B-Rep cylindrical faces with `sw_review.collect_geometry_measurements()`.
2. Verify diameters and hole-axis positions with `sw_review.validate_hole_positions()`.
3. Read feature definitions for blind depth, counterbore depth, and countersink angle, or review section views manually.
4. Slot-end cylindrical faces must enter `slot_arc_candidates`, not the round-hole count.
5. Compound holes should appear in `compound_holes` as coaxial segments of different diameters.

For each hole, record at least type, specification, count, datum-edge location, center distances, depth/through condition, dimensional tolerances, and evidence source.

## Known limits

- Conical countersinks use an angle/distance chamfer on the through-hole entrance edge. Filter by center, radius, and reference-plane position instead of temporary edge names; inspect a section view afterward to confirm the entrance direction.
- B-Rep alone cannot reliably distinguish blind and through holes. Cross-check creation parameters or feature-definition readback.
- The current geometric pattern creates a feature at each explicit position for auditability. Large regular patterns may later gain Linear/Circular Pattern wrappers.
