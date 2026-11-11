# ModelOps API verification notes

The unified executor reuses the bundled, previously verified `update_dimension_mm`, save, open, and context interfaces.
It additionally reads `IDimension.GetType()` to reject angular or integer parameters rather than writing them as millimeters.

- Official method: `IDimension.GetType() -> int`
- Enum: `swDimensionParamTypeDoubleLinear=0`, `DoubleAngular=1`, `Integer=2`, `Unknown=-1`
- Official sources:
  - https://help.solidworks.com/2024/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~GetType.html
  - https://help.solidworks.com/2024/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDimensionParamType_e.html
- Driving state uses `DrivenState`, as in the sketch audit; driven dimensions are not modified.
- An API success from `update_dimension_mm()` must also agree with `after_mm.current`; the return code alone is insufficient.
- Checkpoints are saved native artifacts, not transactions covering arbitrary Python side effects. Recovery manages only this task's part copies.

Version compatibility and real-machine regressions are recorded separately. Do not extrapolate to untested SolidWorks versions or part types.
