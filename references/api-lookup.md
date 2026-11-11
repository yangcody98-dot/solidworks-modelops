# Verifying SolidWorks API calls

Verify before implementing a SolidWorks API that is not yet wrapped in `scripts/`. Do not reconstruct long signatures, enum values, or return contracts from memory.

## Preferred sources

1. Official documentation: `https://help.solidworks.com`
   - Suggested search terms:
     - `site:help.solidworks.com SolidWorks API Help <InterfaceName> <MethodName>`
     - `site:help.solidworks.com <MethodName> Method (SOLIDWORKS API Help)`
     - `site:help.solidworks.com swSaveAsOptions_e`
2. Local SDK / API Help:
   - Common locations under the SolidWorks installation: `api`, `api\help`, `api\redist`
   - Common type libraries: `SolidWorks.Interop.sldworks.dll`, `SolidWorks.Interop.swconst.dll`
3. Wrappers and lessons in this repository:
   - Search `scripts/*.py` first.
   - Then consult `references/*.md`.
   - Write a new minimal validation script only afterward.

## APIs that require verification

- `IModelDocExtension.SaveAs*`, `OpenDoc*`, `CloseDoc`, and export APIs
- `SelectByID2`, selection marks, selection-type strings, and append behavior
- Long-argument methods including `FeatureManager.FeatureExtrusion*`, `FeatureCut*`, sweeps, lofts, fillets, and chamfers
- `IAssemblyDoc.AddComponent*`, `AddMate*`, component transforms, and lightweight/suppression states
- Moving assemblies: `IAssemblyDoc.AddMate5`, `IComponent2.GetModelDoc2`, `IComponent2.GetCorresponding`, `IComponent2.SetSuppression2`, `ISurface.IsCylinder`, `ISurface.CylinderParams`, `IComponent2.SetTransformAndSolve2`
- Motion Study: `IModelDocExtension.GetMotionStudyManager`, `IMotionStudyManager.CreateMotionStudy`, `IMotionStudy.CreateDefinition`, `IMotionStudy.CreateFeature`, `ISimulationMotorFeatureData.ConstantSpeedMotor`, `ISimulationMotorFeatureData.LoadReferences`
- Appearance/material: `MaterialPropertyValues`, `IMaterialVisualPropertiesData`, component-level appearances, and display states
- Drawings: view creation, BOM, dimensions, printing, and PDF export
- Interfaces requiring `VARIANT`, by-ref values, enums, or bitmasks

## Verification record template

Keep a minimal record in the task script or commit description so the findings can be reused:

```text
API:
Source:
Version:
Signature:
Key parameters:
Enums/constants:
Return value:
Failure symptoms:
Validation script:
Added to scripts/references:
```

## Moving-assembly API notes

- `AddMate5`: confirm the 15-parameter signature; the final `ErrorStatus` is a by-ref integer. Gear mates use `GearRatioNumerator` / `GearRatioDenominator`; moving concentric mates need `LockRotation=False`.
- `GetModelDoc2`: the official documentation notes that suppressed, lightweight, or unloaded components may not return a model. Resolve components before automation.
- `GetCorresponding`: map an object from a part document into the assembly context. If the same part has multiple instances, call it on the intended component instance.
- `IsCylinder` / `CylinderParams`: identify cylindrical shaft, hole, and gear faces. `CylinderParams[6]` is the radius in meters.
- `SetTransformAndSolve2`: suitable for driving component positions and updating the assembly solver. If unstable, reuse the component's existing `Transform2` and modify `ArrayData`.
- `swmotionstudy.tlb`: strongly typed Motion Study interfaces live in a separate type library. With pywin32, use `pythoncom.LoadTypeLib(...)` and `win32com.client.gencache.EnsureModule(...)`.
- `swFmAEMRotationalMotor`: the locally verified SW 2024 `swFeatureNameID_e` value is `78`; use `CreateDefinition(78)` to create rotational motor FeatureData.
- `ISimulationMotorFeatureData.ConstantSpeedMotor(60.0)`: the argument is in RPM, not rad/s.
- `swAddMateError_e`: `swAddMateError_NoError=1`; do not treat the by-ref `ErrorStatus=1` from `AddMate5` as failure.

Local enum cross-check command:

```powershell
Add-Type -Path 'E:\Solidworks\SOLIDWORKS\SolidWorks.Interop.swconst.dll'
[int][SolidWorks.Interop.swconst.swMateType_e]::swMateGEAR
[int][SolidWorks.Interop.swconst.swMateType_e]::swMateHINGE
[int][SolidWorks.Interop.swconst.swFeatureNameID_e]::swFmAEMRotationalMotor
[int][SolidWorks.Interop.swconst.swAddMateError_e]::swAddMateError_NoError
[enum]::GetValues([SolidWorks.Interop.swconst.swComponentSuppressionState_e])
```

## Minimal validation script requirements

1. Connect to SolidWorks in isolation and print `sw.RevisionNumber()` and the active document type.
2. Validate one new API at a time; do not immediately mix it into a larger task.
3. Check every COM call for `None`, `False`, error codes, and warning codes.
4. Produce an openable `.SLDPRT`, `.SLDASM`, `.SLDDRW`, or exported file.
5. Run `sw_review.py` or inspect screenshots to confirm the model, drawing, or assembly is actually correct.

## Reuse rules

- On the second use of an API, prefer adding a wrapper under `scripts/`.
- Record compatibility issues, error codes, localized Chinese names, and selection-mark pitfalls in the relevant `references/*.md`.
- Wrappers should hide long COM signatures and expose a stable, readable Python API with explicit unit conventions.
- Documentation examples must use previously executed call patterns; do not include unverified guesses.
