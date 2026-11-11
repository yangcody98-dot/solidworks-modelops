# Native Rib creation and acceptance

For solid stiffening ribs between existing intersecting walls, such as an L-bracket, prefer
`scripts/sw_native_ribs.py` instead of copying unverified long COM calls. It supplements existing part, hole/slot, fillet/chamfer,
assembly, drawing, and export interfaces; the basic JSON action allowlist in `sw_closed_loop` is unchanged.

## Historically verified scope

Two independent new parts passed on **SOLIDWORKS Professional 2025 SP2.0** using an open, single-line 2D sketch,
symmetric two-sided thickness, generation parallel to the sketch, and no draft, merging into one solid. The capability remains `pilot`.
This does not verify curves, multiple profiles, one-sided ribs, normal-to-sketch generation, draft, or other versions.

The relative paths below identify upstream local test records. Original reports and CAD artifacts are not included in this public repository;
these paths establish historical provenance, not completed regression on a new installation:

```text
output/sw_skill_L_bracket_20261029/probe_01/run_report.json
output/sw_skill_L_bracket_20261029/run_01/run_report.json
output/sw_skill_L_bracket_20261029/run_01/reopened_native_validation.json
```

Both the isolated probe and complete L-bracket created one native `Rib` with **8000 mm³** added volume.
The complete part read back `Thickness=0.008 m`, `IsTwoSided=True`, `ExtrusionDirection=0`, and `EnableDraft=False`;
all six sketches, including absorbed Hole Wizard sketches, were fully defined with parametric evidence; no feature errors were reported.
Reimported STEP contained one solid with bounds **120×80×92 mm** and volume approximately **224443.161001 mm³**.
Source document state, source file hashes, and working-directory restoration passed. These are sample-specific results, not general strength or manufacturing certification.

## Correct native call

Official interface: [IFeatureManager.InsertRib](https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeatureManager~InsertRib.html).
It returns **void** and takes parameters in this order:

```python
FeatureManager.InsertRib(
    Is2Sided, ReverseThicknessDir, Thickness, ReferenceEdgeIndex,
    ReverseMaterialDir, IsDrafted, DraftOutward, DraftAngle,
    IsNormToSketch, IsDraftedFromWall,
)
```

Values used in the historical passing sample:

```python
FeatureManager.InsertRib(True, False, 0.008, 0, False, False, False, 0, False, False)
```

`Thickness` is in meters. Two-sided thickness is distributed symmetrically about the sketch plane: 8 mm means 4 mm per side.
The first argument, `Is2Sided`, controls thickness distribution, not material-generation direction.
The earlier nine-argument call omitted `IsDraftedFromWall` and treated the return as a Feature; it is not a valid success path.
The compatible `sw_part.rib()` entry remains, but new tasks should prefer the higher-level checked entry.
Its `thickness` still uses meters. The retained compatibility argument `direction` actually maps to `Is2Sided`,
not generation direction. Its `False` one-sided mode remains callable at low level but is outside the historically verified scope.

## From context to execution and verification

1. Read the current session, source model context, and source file hashes. Create a new task-owned part;
   verify ownership at each stage and never clear, rebuild, save, or close the original model.
2. Read actual support-wall, sketch-plane, and rib-endpoint coordinates. Confirm a single solid and available volume first.
   Sketch coordinates are local; convert global XYZ with `ModelToSketchTransform` rather than mixing frames.
3. Create an open single-line sketch. Call `fully_define_active_sketch()` before closing it,
   requiring both `fully_defined` and `parametric_evidence`; do not lock the entire sketch with Fix.
4. Capture the before snapshot and feature list, then call `create_native_rib()`, for example on a task-owned `backend`:

   ```python
   from sw_native_ribs import create_native_rib

   backend.ensure_owned()
   result = create_native_rib(
       backend.model, sketch_name, 8,
       name="Central_Rib_T8",
       expected_added_volume_mm3=0.5 * 40 * 50 * 8,
       volume_tolerance_mm3=0.1,
   )
   # feature is a COM object; the remaining evidence is JSON-serializable.
   evidence = {key: value for key, value in result.items() if key != "feature"}
   ```

   Read an existing rib back without rebuilding or saving:

   ```python
   from sw_native_ribs import read_native_rib

   readback = read_native_rib(
       result["feature"], expected_thickness_mm=8, expected_two_sided=True,
   )
   ```

   Readback returns `feature_type`, `thickness_mm`, `is_two_sided`, `extrusion_direction`,
   `flip_side`, `enable_draft`, and `draft_angle`, checked against expectations. Normal-to-sketch or drafted ribs are outside this validation path.

5. Accept the newly created native `Rib` using evidence, not merely the absence of a COM exception:
   - Exactly one new feature has `GetTypeName2()=="Rib"` and a readable definition.
   - Readback of thickness, two-sided state, direction, and draft matches the request.
   - Rebuild succeeds, the complete feature list has no errors, and one solid remains.
   - Volume increases and matches an analytical expectation within tolerance when available.
   - Recursively check all sketches, including the absorbed rib sketch, for full definition and retained driving dimensions/relations.
6. On failure, retain the failure snapshot, error, and actual geometry; stop downstream delivery. If a rib or changed solid remains,
   do not repeat the call blindly. Revise in a different new task-owned document or return for review. An ordinary extrusion can be an explicitly stated alternative design,
   but cannot be recorded as successful native Rib creation.
7. After success, save, export STEP, and review four views. Independently reimport STEP and check solid count, volume, and position.
   Reopen the new SLDPRT, reread sketches and rib parameters, and verify source context, hashes, and working-directory protection.

Calculate added volume for each design. `0.5×40×50×8` applies only to this nonoverlapping right-triangle sample.
Account for wall overlap, fillets, or other cuts instead of universally expecting 8000 mm³.

## Skill-only maintenance tasks

When the user requests only a skill update and explicitly excludes model changes, validate wrappers and failure paths with existing real-machine reports and offline tests.
Do not connect to SolidWorks, open, modify, or save models merely to test again. A new real-machine regression is a separately authorized modeling task
and must continue to use only new task-owned documents.
