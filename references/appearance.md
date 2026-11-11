# Appearance and material reference

## Core rule

Pass SolidWorks' nine-element material array to COM as `SAFEARRAY(double)`. Do not assign a Python
`list` directly to `MaterialPropertyValues`: pywin32 dynamic dispatch can marshal a normal list incorrectly,
placing RGB in positions 2, 5, and 8 and making the model appear almost entirely green.

Stable wrappers are in `scripts/sw_appearance.py`:

- `material_variant()`: wrap the nine-element array as `VT_ARRAY | VT_R8`.
- `set_document_appearance()`: write and read back document-level RGB.
- `set_feature_appearance()`: write and read back feature-level RGB.
- `set_component_appearance()`: write and read back assembly-component RGB.
- `apply_component_palette()`: apply colors in a batch and return a per-component audit.
- `verify_appearance()`: compare the expected RGB with COM readback.

## Recommended usage

```python
from sw_appearance import (
    apply_component_palette,
    set_document_appearance,
    set_feature_appearance,
    verify_appearance,
)

set_document_appearance(model, "iron_red")
set_feature_appearance(feature, "armor_gold")
assert verify_appearance(model, "iron_red")["ok"]

reports = apply_component_palette([
    (body_component, "aqua_blue"),
    (glass_component, "glass_tint"),
    (rear_light_component, "signal_red"),
    (rim_component, "silver"),
])
assert all(item["ok"] for item in reports)
```

## Color presets

| Name | Description |
|---|---|
| `iron_red` | Deep red armor |
| `armor_gold` | Gold armor |
| `dark_gunmetal` | Dark metal / joints |
| `arc_blue` | Blue illuminated part |
| `silver` | Silver metal |
| `black` | Black |
| `white` | White |
| `aqua_blue` | Cyan-blue body color |
| `glass_tint` | Dark glass |
| `signal_red` | Tail light / warning red |
| `light_cyan` | Light blue illuminated part |
| `tire_black` | Tire black |
| `graphite` | Graphite gray |

## Verified API signatures

Historical local reflection results from `SolidWorks.Interop.sldworks.dll`, SolidWorks 2024 SP3.1:

```text
IModelDoc2.MaterialPropertyValues = Object
IModelDocExtension.SetMaterialPropertyValues(Object, Int32, Object) -> void
IFeature.SetMaterialPropertyValues(Object) -> bool
IFeature.SetMaterialPropertyValues2(Object, Int32, Object) -> void
IComponent2.SetMaterialPropertyValues2(Object, Int32, Object) -> void
IComponent2.GetMaterialPropertyValues2(Int32, Object) -> Object
```

Configuration options: `swThisConfiguration=1`, `swAllConfiguration=2`,
and `swSpecifyConfiguration=3`. A setter returning `void` has completed when no COM exception is raised;
do not use `bool(method(...))` to judge success. Final acceptance must use `verify_appearance()` readback.

## Multicolor assembly workflow

1. Set the base appearance at document level in the source part and save.
2. Apply component-level overrides after inserting components as needed.
3. Read back the first three RGB values after each write; stop immediately on a mismatch.
4. Call `assembly.ClearSelection2(True)` before saving.
5. Clear selections again and redraw before previewing so green selection highlights do not hide the actual appearance.
6. Inspect at least one color isometric view and one orthographic view showing the lights or wheels.

## Stability recommendations

- Coloring multiple features in one part can depend on SolidWorks version, display state, and merged features.
- For color-critical models, prefer separate parts with document-level appearances.
- For complex projects, deliver an assembly whose component hierarchy expresses colors, materials, and replaceable modules.
- A setter returning without an exception does not prove the color is correct; read RGB back.
- Do not capture screenshots while components, faces, or edges remain selected; green highlights impair visual review.
- After generation, export previews with `sw_review.py` and check that colors and visual layers remain visible.
