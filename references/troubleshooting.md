# Troubleshooting

## Connection problems

### Cannot connect to SolidWorks

```
Error: pywintypes.com_error: (-2147221005, 'Invalid class string', None, None)
```

**Cause**: SolidWorks is not installed or its COM server is not registered.
**Resolution**: Confirm installation and try connecting to a specific version:
```python
sw = win32com.client.Dispatch("SldWorks.Application.32")  # SW 2024
```

### GetActiveObject fails

```
Error: pywintypes.com_error: (-2147221021, 'Operation unavailable', None, None)
```

**Cause**: SolidWorks is not running.
**Resolution**: Start SolidWorks manually, or use `Dispatch` when launching a new instance is authorized.

### Python 32/64-bit mismatch

**Cause**: Python must match the SolidWorks architecture, normally 64-bit.
**Resolution**: Install 64-bit Python.

## Type errors

### Apparently callable COM properties report member not found

Symptom: during feature traversal or model summaries, pywin32 reports `callable=True` for members such as `FirstFeature`, `GetNextFeature`, and `GetTitle`, but invoking them returns:

```text
(-2147352573, 'Member not found.', None, None)
```

Cause: under dynamic dispatch, some SolidWorks COM members can appear as either properties or methods. `callable(member)` is not a sufficient discriminator.

Stable approach: prefer `sw_connect.get_com_member()` or `sw_assembly.safe_get_com_member()`.

```python
from sw_connect import get_com_member

feature = get_com_member(model, "FirstFeature")
while feature:
    print(get_com_member(feature, "Name"), get_com_member(feature, "GetTypeName2"))
    feature = get_com_member(feature, "GetNextFeature")
```

### Motion Study members report member not found

Symptom: `model.Extension.GetMotionStudyManager()` or `motion_mgr.CreateMotionStudy()` returns:

```text
(-2147352573, 'Member not found.', None, None)
```

Common causes:

1. Strongly typed Motion Study interfaces live in `swmotionstudy.tlb`, not the main `sldworks` type library.
2. Under dynamic pywin32 dispatch, `GetMotionStudyManager`, `CreateMotionStudy`, `Activate`, `Calculate`, and `Play` may be properties rather than methods.

Stable approach: prefer `sw_motion.py`.

```python
from sw_motion import create_motion_study, motion_member

study = create_motion_study(asm, name="Motion_60RPM", duration=4.0)
calculated = motion_member(study, "Calculate")
```

If low-level calls are required, load the type library first:

```python
from sw_motion import ensure_motion_type_library

ensure_motion_type_library(raise_on_error=True)
motion_mgr = asm.Extension.GetMotionStudyManager
study = motion_mgr.CreateMotionStudy
```

### SelectByID2 type mismatch

```
Error: TypeError: Objects of type 'NoneType' can not be converted to a COM VARIANT
```

**Resolution**: Pass an explicit VARIANT for the Callout argument:
```python
from win32com.client import VARIANT
import pythoncom
callout = VARIANT(pythoncom.VT_DISPATCH, None)
model.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, callout, 0)
```

### by-ref argument errors

**Resolution**: Wrap output arguments in VARIANT:
```python
errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
```

### Pack and Go reports a missing argument when obtaining its object

Symptom: `model.Extension.GetPackAndGo()` or strongly typed `IModelDocExtension.GetPackAndGo()` reports a required argument is missing, although official API documentation and Interop reflection show zero arguments and an `IPackAndGo` return.

Cause: local SW2024/2026 pywin32 runtime objects can mis-marshal `[out, retval] IPackAndGo**`. Both the official zero-argument dynamic call and explicit `VT_BYREF | VT_DISPATCH` have failed to obtain the return pointer in historical tests.

Stable approach: use `sw_delivery.pack_and_go()`. It first tries the official zero-argument pywin32 call, then uses early-bound `comtypes` for native `IModelDocExtension.GetPackAndGo()` / `SavePackAndGo()` on signature failure.

```python
from sw_delivery import pack_and_go

report = pack_and_go(assembly, r"E:\\delivery\\pack_and_go", flatten=True)
assert report["success"], report
```

### Pack and Go writes only the top-level assembly

Symptom: `IModelDoc2.GetDependencies2()` lists referenced `.SLDPRT` files, but `IPackAndGo.GetDocumentNames()` lists only the `.SLDASM`, and the saved package contains only the assembly.

Resolution: do not treat pre-save enumeration as the actual package or add native assembly parts through `AddExternalDocuments`. `sw_delivery.pack_and_go()` first calls native `SavePackAndGo()`, then audits this run's files. A basic two-part assembly produced one assembly and two parts in three historical SW2026 SP01.1 runs. If dependencies still go missing, the default returns an explicitly marked `pilot` staged package; strict mode returns `status=blocked` and `SW_PACK_AND_GO_DEPENDENCY_ENUMERATION_INCOMPLETE`. Both paths must retain missing-dependency evidence and require human review.

### STL exports the active assembly instead of the target part

Symptom: `IModelDocExtension.SaveAs()` reports success, but the intended part STL is missing and multiple files named
`PartName - AssemblyComponentName.STL` appear instead.

Cause: the SW2024 STL exporter may read `ActiveDoc`. Holding the target part's `IModelDoc2` alone does not ensure
that the exporter uses that part.

Resolution: use `sw_export.batch_export_formats()`, which calls `ActivateDoc3()` before each format
and strictly checks the active document path. Stop on a mismatch rather than accepting the API's superficial success.

## Operation failures

### run_review captures only one part or subassembly

Symptom: assembly component count, visibility, and color readbacks look correct, but `run_review()` shows only a wheel or small part; remaining geometry is absent or visible only as shadows.

Common causes:

1. SolidWorks `SaveBMP()` uses the active graphics window, while the target `model` is not active.
2. After opening parts/subassemblies in a batch, the last component remains active.
3. Rule-based review detects nonblank previews but cannot identify a screenshot of the wrong document.

Stable approach: use the current `sw_review.save_preview()` / `run_review()`, which activates the target by `GetTitle()` before capture. A manual workflow must call `ActivateDoc3()`, then `ClearSelection2(True)`, `ViewZoomtofit2()`, and `SaveBMP()`.

```python
errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
sw.ActivateDoc3(model.GetTitle(), False, 0, errors)
model.ClearSelection2(True)
model.ViewZoomtofit2()
model.SaveBMP(r"E:\review\assembly.bmp", 1600, 1000)
```

Inspect all four views manually; `evaluation.status=pass` does not establish geometric correctness.

### Split STEP components overlap at the assembly origin

Symptom: a colored STEP/assembly is split, imported as native parts, and reassembled. Component count is correct, but the preview shows a single wheel or an overlapping mass.

Cause: some exporters preserve a body's absolute coordinates when exporting it separately. SolidWorks `AddComponent5(path, ..., x, y, z)` may place its bounding-box center at the requested position, so `(0,0,0)` stacks all components.

Stable approach:

1. Record each body's global bounding-box center before export in the split-file manifest.
2. Insert at that center in meters rather than using `(0,0,0)` for every part.
3. Read `Transform2.ArrayData[9:12]` and `GetBox()` after insertion; confirm overall bounds are close to the original machine.
4. Recursively inspect components inside `.SLDASM` subassemblies, not just the top-level count.

```python
center_m = [value / 1000.0 for value in bbox_center_mm]
component = add_component(asm, native_path, x=center_m[0], y=center_m[1], z=center_m[2])
```

### GetModelDoc2 returns None

Symptom: a component is present in the assembly but `component.GetModelDoc2()` returns `None`, preventing access to planes, faces, and features.

Common causes:

1. The component is suppressed or lightweight.
2. Its referenced file is not loaded in memory.
3. A newly inserted component has not yet been resolved.

Stable approach: resolve the component before reading its model; prefer `sw_assembly.get_component_model()`.

```python
from sw_assembly import get_component_model, resolve_component

resolve_component(component)  # Default: swComponentFullyResolved=2; fallback: swComponentResolved=3
part = get_component_model(component)
```

### AddComponent4 returns None

Symptom: on Chinese-language SW2024 with pywin32, `asm.AddComponent4(path, "", x, y, z)` returns `None` repeatedly without an exception, preventing insertion.

Stable approach: use `sw_assembly.add_component()`. It checks the file path, tries `AddComponent5(path, 0, "", False, config, x, y, z)`, then `AddComponent4()`. If both return null, it silently opens the part, reactivates the assembly, and retries `AddComponent5()`.

```python
from sw_assembly import add_component, get_components

component = add_component(asm, r"E:\parts\probe_block.SLDPRT", x=0, y=0, z=0)
if component is None:
    raise RuntimeError("Component insertion failed")
print(get_components(asm))
```

Real SolidWorks regression check:

```powershell
py -3.13 tests\solidworks_add_component_regression.py --output-dir C:\CADAutomationWorkbench\solidworks_add_component_regression
```

Acceptance: `component_count >= 1`, nonempty `component_name`, saved `.SLDASM`, and `review_evaluation.status=pass` or at least `review_checks.expected_outputs_exist=true`.

### Mate creation leaves no real mate in the feature tree

Symptom: the script reports success, but the tree has no Gear/Concentric Mate and dragging does not drive coupled motion.

Check:

1. Whether `AddMate5()` returned `None`.
2. Whether by-ref `ErrorStatus` is a success code. `swAddMateError_NoError=1`; some versions also return 0 on success.
3. Whether exactly two objects were selected before creation.
4. Whether selected objects belong to the assembly context rather than the part document.
5. Whether a mate was written under `MateGroup`.

Stable approach:

```python
from sw_assembly import add_mate5_checked, collect_mate_feature_summary

mate = add_mate5_checked(asm, 1, lock_rotation=False, name="shaft_concentric")
print(collect_mate_feature_summary(asm))
```

### AddMate5 returns a Mate with error_status=1

Symptom: `AddMate5()` returns a nonnull Mate and the tree contains it, but the script reports failure:

```text
AddMate5 failed: type=1, error_status=1
```

Cause: `swAddMateError_e` defines `1=swAddMateError_NoError`. Do not accept only 0 as success.

Verification command:

```powershell
Add-Type -Path 'E:\Solidworks\SOLIDWORKS\SolidWorks.Interop.swconst.dll'
[int][SolidWorks.Interop.swconst.swAddMateError_e]::swAddMateError_NoError
```

Stable approach: the current `sw_assembly.add_mate5_checked()` accepts 0 and 1 as success while still checking for a nonnull Mate.

### Selection set is cleared

Symptom: the first face selects correctly. After resolving a component or switching documents, the second face selects but `AddMate5()` fails.

Cause: `SetSuppression2()`, document activation, and some rebuilds can clear or change selections.

Stable sequence:

1. Resolve all components participating in the mate.
2. Map entities with `GetCorresponding()`.
3. Clear selections, then select both entities consecutively.
4. Immediately call `AddMate5()`.

```python
from sw_assembly import select_entities_for_mate

select_entities_for_mate(asm, entity_a, entity_b, mark=1)
```

### GetCorresponding returns None

Symptom: a plane or face exists in a part, but `component.GetCorresponding(face_or_feature)` returns `None`.

Common causes:

1. The supplied object does not belong to the component's referenced document.
2. The component is unresolved.
3. The wrong instance is used. When one part is inserted multiple times, call `GetCorresponding()` on the intended instance.
4. The selected geometry is temporary or the object is stale.

Stable approach: find the feature/face in the model returned by `get_component_model(component)`, then map it with that same component.

### A component cannot rotate after a concentric mate

The usual issue is locked rotation, not a missing hinge:

1. `lock_rotation=True` or GUI Lock Rotation is enabled.
2. Three additional coincident reference planes fully constrain the rotating part.
3. The component itself is fixed.
4. Too many axial-location mates overdefine the assembly.

For moving assemblies, use this concentric-mate default:

```python
add_concentric_mate_by_cylinders(..., lock_rotation=False)
```

A cover hinge can retain rotation through a concentric mate and limit axial movement with one plane-coincident/distance mate.

### Feature creation returns None

Common causes:
1. **Wrong entity selection**: check the name and type passed to SelectByID2.
2. **Underconstrained sketch**: add the required dimensions and relations.
3. **Open sketch contour**: extrusion requires a closed profile.
4. **Incorrect units**: API lengths are meters, not millimeters.

### SelectByID2("SKETCH") repeatedly returns False

Symptom: in Chinese-language SolidWorks 2024, both `SelectByID2("草图1", "SKETCH", ...)` (localized Sketch1) and `SelectByID2("Sketch1", "SKETCH", ...)` return `False`; `FeatureExtrusion3()` then returns `None`.

Cause: name-based sketch selection is unstable on some versions/localizations. An old `sw_part._ensure_sketch_selected()` also treated any nonempty selection set as success, so early parts worked accidentally until another action cleared the leftover selection.

Stable approach:

1. Prefer `with sketch(model, "...") as sketch_name:` so `sw_part.py` caches the real sketch object at creation.
2. Do not depend on leftover selections. Document switches, rebuilds, component resolution, and failed APIs can clear them.
3. Prefer object-level `Select2()` on the sketch Feature/Sketch, falling back to `SelectByID2("SKETCH")` last.
4. In a manual low-level flow, pass the result of `end_sketch(model)` directly to `extrude_boss()` / `extrude_cut()`.

```python
from sw_part import end_sketch, extrude_boss, sketch_circle, start_sketch

start_sketch(model, "Front Plane")
sketch_circle(model, 0, 0, 0.025)
sketch_ref = end_sketch(model)
feature = extrude_boss(model, sketch_ref, 0.05)
if feature is None:
    raise RuntimeError("Extrusion failed: check closed contours, direction, and object selection")
```

Real SolidWorks regression check:

```powershell
py -3.13 tests\solidworks_sketch_selection_regression.py --output-dir C:\CADAutomationWorkbench\solidworks_skill_regression
```

Acceptance: after two `ClearSelection2(True)` calls the script reports `selection_count=0`, yet still creates the localized `凸台-拉伸1` (Boss-Extrude1) and `切除-拉伸1` (Cut-Extrude1), saves `.SLDPRT`, exports `.step`, and returns `review_evaluation.status=pass`.

### Unstable long FeatureCut4 signatures

Symptom: handwritten `FeatureCut4(...)` returns `None`, although the same sketch cuts successfully in the GUI or wrapper.

Cause: mismatched end conditions, reverse direction, `FlipSide`, `NormalCut`, or selection state can silently fail among FeatureCut4's many arguments. Do not reconstruct long calls from memory.

Stable approach:

1. Prefer `sw_part.extrude_cut()`.
2. If a low-level call is required, test directions and end conditions on a minimal cylinder/rectangle first.
3. Check the returned feature after every cut; do not save a delivery file after an unresolved failure.

```python
from sw_part import extrude_cut

feature = extrude_cut(model, sketch_name, 0, direction=True, flip=False)
if feature is None:
    feature = extrude_cut(model, sketch_name, 0, direction=True, flip=True)
if feature is None:
    raise RuntimeError("Cut failed: check the sketch, direction, and end condition")
```

### Cutting a slot from a central plane splits the shaft

Symptom: an obround/keyway drawn on `Front Plane` and cut blind produces a broad axial planar opening, as though half the cylinder were removed.

Cause: `Front Plane` commonly crosses the shaft axis rather than its outer surface. A cut from that central plane sections the shaft instead of making a surface recess.

Stable approach: create a tangent offset reference plane, sketch the slot there, and blind-cut to the requested depth. See the cylindrical-surface obround-slot section in `references/part-modeling.md`.

### Slot feature exists but is absent from the preview

Symptom: `Cut_*_Slot` exists and `run_review()` passes, but no slot appears in the isometric or main view.

Check:

1. Whether it cut the rear side; reverse `flip` or export the opposite view.
2. Whether the cut started at the central plane and is hidden by shading; inspect top/right views.
3. Whether it removed only invisible internal volume; inspect a section or revise the tangent plane.
4. Whether a selected reference plane obscures the slot outline.

Resolution: `feature is not None` is insufficient. Export `isometric/front/top/right` and visually confirm the required geometry.

### Reference-plane selection fails

**Cause**: English and Chinese object names differ.
**Resolution**:
```python
# Try the English name
success = model.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, None, 0)
if not success:
# Try the Chinese-language API object name
    model.Extension.SelectByID2("前视基准面", "PLANE", 0, 0, 0, False, 0, None, 0)
```

### Save/export fails

Read the error codes:
```python
errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
success = model.Extension.SaveAs(path, 0, 1, None, errors, warnings)
print(f"Error code: {errors.value}, warning code: {warnings.value}")
# See the code table in references/export.md
```

### OpenDoc6 crashes on STEP/IGES or import opens a template dialog

Symptom: opening `.step/.stp/.igs/.iges` with `OpenDoc6()` exits SolidWorks or disconnects RPC; alternatively,
`LoadFile4(path, "", importData, errors)` blocks on the New SOLIDWORKS Document template dialog.

Cause: foreign files other than DXF/DWG or Pro/E should be imported into new documents with `LoadFile4`,
using `ArgString="r"`. An empty string can trigger template selection in SW2024 and is unsuitable for automation.

Stable approach: prefer `sw_connect.open_document()` / `SolidWorksSession.open()`, which automatically use
`LoadFile4(file_path, "r", sw.GetImportFileData(file_path), errors)` for STEP/STP/IGES/IGS.
Before import, `ensure_default_templates()` configures part, assembly, and drawing defaults and enables
`swAlwaysUseDefaultTemplates=111` to reduce New SOLIDWORKS Document dialogs.

```python
from sw_session import SolidWorksSession

session = SolidWorksSession(version=2024, visible=True)
model = session.open(r"E:\parts\body.step", silent=True, raise_on_error=True)
session.save(model, r"E:\parts\body.SLDPRT")
```

Real SolidWorks regression check:

```powershell
py -3.13 tests\solidworks_loadfile4_import_regression.py --output-dir C:\CADAutomationWorkbench\solidworks_loadfile4_import_regression
```

Acceptance: `status=pass`, `body_count >= 1`, a saved imported `.SLDPRT`, and a four-view review report.

Default template string-preference enums are `swDefaultTemplatePart=8`,
`swDefaultTemplateAssembly=9`, and `swDefaultTemplateDrawing=10`. Do not substitute file-location enums or obsolete values;
otherwise `NewDocument()` / `LoadFile4()` may still show a template dialog.

If a large STEP repeatedly raises `pywintypes.com_error: (-2147023170, 'The remote procedure call failed.')`,
do not keep retrying the same SolidWorks process blindly. Save logs, restart SolidWorks, and try smaller split parts,
a Parasolid intermediate, or user-confirmed template selection. `ensure_default_templates()` reduces dialog risk
but cannot guarantee silent import for every local SW2024 template configuration.

### OBJ/STL fails with OpenDoc6 or has a LoadFile4 type mismatch

Symptom: a public mesh reference, vehicle model, or test cube `.obj/.stl` fails to open with `OpenDoc6(path, swDocPART, ...)`
and returns `2097152` (`swFileRequiresRepairError`); switching to
`LoadFile4(path, "r", None, errors)` produces `com_error(-2147352571, 'Type mismatch.')`.

Cause: some SolidWorks 2024 COM environments cannot open OBJ/STL as ordinary part documents,
and `LoadFile4()` cannot take Python `None` as its third argument. This does not necessarily mean corruption;
even a simple 684-byte STL cube can reproduce it.

Stable approach: use `scripts/sw_import_mesh_reference.py` or the following minimal import:

```python
from sw_connect import connect_solidworks, create_empty_dispatch_variant, save_document
from win32com.client import VARIANT
import pythoncom

sw, _ = connect_solidworks(visible=True)
sw.SetUserPreferenceIntegerValue(208, 0)   # swImportStlVrmlModelType_Graphics
sw.SetUserPreferenceIntegerValue(210, 2)   # swMETER
sw.SetUserPreferenceToggle(303, True)      # swImportStlVrmlTextureInformation
sw.SetUserPreferenceToggle(679, True)      # swVrmlStlImportAsPSMesh

errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
model = sw.LoadFile4(
    r"E:\work\reference_scaled_m.obj",
    "r",
    create_empty_dispatch_variant(),
    errors,
)
assert model is not None, errors.value
save_document(model, r"E:\work\reference.SLDPRT")
```

STEP/STP/IGES/IGS and OBJ/STL use different import-data arguments. Neutral CAD files continue to use
`sw.GetImportFileData(path)`; OBJ/STL mesh references use an empty Dispatch variant. Do not mix these routes.

### SaveAs error 1 or failed overwrite

Symptom: `session.save(model, path)` or `model.Extension.SaveAs(...)` returns failure/error `1`, even though the target exists and its path is correct.

Common cause: a document with the same name is already open or the current SolidWorks process holds the target file, preventing overwrite.

Stable approach:

```python
session = SolidWorksSession()
session.sw.CloseDoc("Drawing_Stepped_Shaft.SLDPRT")
model = session.new_part()
```

Close only the output document that this script explicitly intends to overwrite. Do not call `CloseAllDocuments()` blindly unless the user approved clearing the session.

### Cannot delete a temporary SLDPRT

Symptom: PowerShell `Remove-Item` reports:

```text
The process cannot access the file ... because it is being used by another process.
```

Cause: the debug part remains open in SolidWorks.

Recovery sequence:

1. Close the matching document with `sw.CloseDoc("<filename>.SLDPRT")`.
2. Remove the temporary file with `Remove-Item -LiteralPath <path> -Force`.
3. Before deletion, verify that the path matches only the intended temporary file, such as `debug_*.SLDPRT`.

### Reference planes or sketches obscure previews

Symptom: the BMP from `run_review()` contains large orange planes, sketches, or selection highlights that obscure solid geometry.

Stable approach:

```python
for plane_name in created_plane_names:
    model.ClearSelection2(True)
    selected = model.Extension.SelectByID2(
        plane_name, "PLANE", 0, 0, 0, False, 0,
        create_empty_dispatch_variant(), 0,
    )
    if selected:
        model.BlankRefGeom()

model.BlankSketch()
model.ClearSelection2(True)
model.ForceRebuild3(False)
```

`BlankRefGeom()` usually requires selecting the reference geometry first; calling it alone may not hide a newly created plane.

### A multicolor assembly appears almost entirely green

Symptom: red, blue, silver, and black were configured, but the assembly or BMP is nearly all green.

Distinguish and verify these two common causes:

1. A normal Python `list` was passed directly to `MaterialPropertyValues`, mis-marshalling the COM array.
2. A component, face, or edge remains selected, and SolidWorks' green highlight hides the actual appearance.

Stable approach:

```python
from sw_appearance import set_component_appearance, verify_appearance

assert set_component_appearance(component, "signal_red")
assert verify_appearance(component, "signal_red")["ok"]

model.ClearSelection2(True)
model.GraphicsRedraw2()
```

Do not simply replace a list with a tuple and keep guessing. Use `material_variant()` consistently to produce
`VT_ARRAY | VT_R8`. Do not judge `SetMaterialPropertyValues2(...)` with `bool(...)`
because it returns `void`. Verification command:

```powershell
python tests\solidworks_appearance_regression.py
```

### MathUtility.CreateTransform is unstable

Symptom: `sw.GetMathUtility().CreateTransform(data)` or `math_utility.CreateTransform()` raises COM errors, returns null, or moves a component without solving.

Stable approach: reuse the component's existing `Transform2`, modify `ArrayData`, and call `SetTransformAndSolve2()`. If necessary, fall back to `component.Transform2 = transform`.

```python
from sw_assembly import apply_component_transform_x
from sw_connect import deg

ok = apply_component_transform_x(component, 0.1, 0.0, 0.0, deg(30))
```

Direct transforms are suitable for positioning or demonstration frames. Interactive dragging still requires real mates preserving degrees of freedom.

### Internal SolidWorks errors or slow COM

Symptom: after large batches of parts/assemblies, `AddComponent4`, saves, exports, or feature calls fail intermittently.

Common causes: too many documents, accumulated graphics/tree refresh work, and a long-running process.

Recovery sequence, within the approved session-cleanup scope:

1. Save critical outputs.
2. Clear the session with `sw.CloseAllDocuments(False)`.
3. Reopen required parts in batches and assemble them.
4. If instability persists, obtain user confirmation before restarting `SLDWORKS.exe`.
5. Log failed components and API calls rather than printing only a completion message.

## Calling unwrapped APIs

When the skill does not yet wrap an API:

1. Verify the interface signature and enums in official SolidWorks API documentation or the local SDK.
2. Exercise it in a minimal script before adding it to a larger task.
3. Check COM returns for `None` / `False` and print error/warning codes.
4. Add stable calls to `scripts/` and pitfalls to this file or the relevant `references/*.md`.

Reusable record:

```text
### <API or failure symptom>

Scenario:
Error/symptom:
Cause:
Stable approach:
  # Minimal executable example
Verification:
```

## Performance

### Slow large-assembly operations

```python
# Enable background processing mode
model.FeatureManager.EnableFeatureTree = False
model.ActiveView.EnableGraphicsUpdate = False

# ... Perform operations ...

# Restore and refresh
model.FeatureManager.EnableFeatureTree = True
model.ActiveView.EnableGraphicsUpdate = True
model.GraphicsRedraw2()
```

### Batch optimization

```python
# Disable automatic rebuilding
sw.UserControl = False

# Perform batch operations...

# Rebuild manually
model.EditRebuild3()
sw.UserControl = True
```

## Version mapping

| SolidWorks | Revision | ProgID |
|---|---|---|
| 2020 | 28 | SldWorks.Application.28 |
| 2021 | 29 | SldWorks.Application.29 |
| 2022 | 30 | SldWorks.Application.30 |
| 2023 | 31 | SldWorks.Application.31 |
| 2024 | 32 | SldWorks.Application.32 |
| 2025 | 33 | SldWorks.Application.33 |
| 2026 | 34 | SldWorks.Application.34 |

Formula: `revision = (year - 2000) + 8`

## License and add-in boundaries

A working base COM connection does not establish available Simulation, Routing, Motion, or mold-tool licenses. Record add-in registration, load state, and a minimal real operation separately. Missing authorization returns `blocked` with its dependency; do not misclassify it as an ordinary script failure.

This project does not patch licenses, bypass activation, modify licensing services, or fabricate capabilities for unauthorized installations. Legitimate headless backends such as OCP, CalculiX, and ezdxf remain available within their open-format scope.
