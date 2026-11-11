# Motion Study and rotational motor automation

This historical guide records Motion Study automation exercised on SolidWorks 2024 SP3.1, Python 3.13, and pywin32. It creates real studies and motor features; script-generated animation is not a substitute for mechanical degrees of freedom.

## Appropriate uses

- Creating a Motion Study, adding a motor, or requesting constant rotation at 60 RPM.
- Assemblies already have real mates; rotating components retain rotation through unlocked concentric mates.
- A calculable, playable animation is needed in the SolidWorks Motion Study timeline.

Outside this workflow:

- To demonstrate only a change of angle, use `sw_assembly.apply_component_transform_x()` to generate frames.
- Complex contact, friction, collision, or force results require checking Motion/Simulation add-ins and licenses, followed by specialized validation.

## Recommended workflow

1. Generate and save the parts.
2. Create an assembly and insert components.
3. Resolve components and select assembly-context entities with `GetCorresponding()`.
4. Create a concentric mate for rotating components with `lock_rotation=False`.
5. Limit axial movement with one plane-coincident or distance mate. Do not lock rotation with three reference planes.
6. Fix stationary components and keep rotating ones floating.
7. Create a study with `sw_motion.create_motion_study()`.
8. Add a constant-speed motor with `add_constant_speed_rotary_motor_by_cylinders()`.
9. Calculate and play with `calculate_and_play()`.
10. Call `validate_motion_studies()`; delivery may proceed only when `validation.status == "pass"`.

## Minimal example

```python
import sys
sys.path.insert(0, r"C:\Users\you\.codex\skills\solidworks-automation\scripts")

from sw_connect import mm
from sw_motion import (
    create_motion_study,
    add_constant_speed_rotary_motor_by_cylinders,
    calculate_and_play,
    validate_motion_studies,
)

# Assumes asm is the assembly, stand_comp the stationary shaft/support, and impeller_comp the impeller.
# The impeller must already have an unlocked concentric mate to the shaft.
study = create_motion_study(
    asm,
    name="Impeller_60RPM_Cycle",
    duration=4.0,
)

motor = add_constant_speed_rotary_motor_by_cylinders(
    study,
    shaft_component=stand_comp,
    rotor_component=impeller_comp,
    shaft_radius=(mm(4.5), mm(5.5)),
    rotor_radius=(mm(10.5), mm(11.5)),
    rpm=60.0,
    name="ImpellerMotor_60RPM",
)

ok = calculate_and_play(study)
audit = validate_motion_studies(
    asm,
    study_name="Impeller_60RPM_Cycle",
    minimum_duration_seconds=4.0,
    minimum_motor_count=1,
    require_results=True,
)
print(ok, audit["validation"])
```

## Result acceptance gate

`validate_motion_studies()` checks:

- The target study actually exists and is readable.
- `swmotionstudy.tlb` is loaded.
- Duration meets the requirement.
- Motor count meets the requirement.
- Optional `StudyType` matches the task.
- `GetResults()` returns a result object.
- `results_out_of_date` is explicitly `False`.

A timeline, motor icon, playing animation, or `Calculate=True` cannot replace these results. Any failed check must block the Reviewer Gate and trigger recalculation or correction of assembly degrees of freedom.

## Type libraries and dynamic COM pitfalls

`IMotionStudyManager` lives in `swmotionstudy.tlb`, not the main `SolidWorks.Interop.sldworks.dll` type library. Without generated pywin32 wrappers, dynamic objects may behave unexpectedly:

- `model.Extension.GetMotionStudyManager` is exposed as a property rather than a method.
- Reading the `motion_mgr.CreateMotionStudy` property creates a study; calling `CreateMotionStudy()` instead can report member not found.
- `study.Activate`, `study.Calculate`, and `study.Play` may be Boolean properties rather than methods.
- `study.SetDuration()`, `study.CreateDefinition()`, and `study.CreateFeature()` generally remain methods.

Prefer `sw_motion.motion_member()` and `sw_motion.ensure_motion_type_library()`.

```python
from sw_motion import ensure_motion_type_library, motion_member

ensure_motion_type_library()
motion_mgr = motion_member(asm.Extension, "GetMotionStudyManager")
study = motion_member(motion_mgr, "CreateMotionStudy")
motion_member(study, "SetDuration", 4.0)
calculated = motion_member(study, "Calculate")
```

## Key rotational motor APIs

Create rotational motor data with `MotionStudy.CreateDefinition(swFmAEMRotationalMotor)`:

```python
SW_FM_AEM_ROTATIONAL_MOTOR = 78
motor_data = study.CreateDefinition(SW_FM_AEM_ROTATIONAL_MOTOR)
motor_data.DirectionReference = shaft_axis_face
motor_data.ConstantSpeedMotor(60.0)  # RPM
motor_data.RelativeComponent = stand_comp
motor_data.Location = rotor_face
motor_data.LoadReferences = (rotor_face,)
motor_feature = study.CreateFeature(motor_data)
```

Historical test notes:

- The most stable `DirectionReference` was a stationary shaft's assembly-context cylindrical face.
- `LoadReferences` accepts a tuple/list; some environments require `VARIANT(VT_ARRAY | VT_VARIANT, [...])` or `VT_DISPATCH`.
- `ConstantSpeedMotor(60.0)` takes RPM; do not convert it to rad/s.
- If `CreateFeature()` returns `None`, first confirm that both direction and load references are assembly-context entities.

## Relationship to mate degrees of freedom

A Motion motor can drive only a component that still has rotational freedom. Common failures:

- The impeller was fixed with `FixComponent()`.
- The concentric mate used `lock_rotation=True`.
- Additional coincident reference planes locked rotation.
- A part-context face was selected instead of the assembly-context face from `component.GetCorresponding()`.

Recommended constraints:

- Stationary components: fix the base, post, and guard.
- Rotating components: one concentric mate plus one axial-location mate; leave the component floating.
- Concentric mate: `lock_rotation=False`.

## Session cleanup and duplicate document titles

Repeatedly debugging generated parts can leave equal document titles in the SolidWorks session, causing:

```text
OpenDoc6 errors=65536
swFileWithSameTitleAlreadyOpen
AddComponent4 returns None
```

Stable historical practice:

1. Before a batch, confirm that current documents may be closed; an authorized unattended workflow may call `sw.CloseAllDocuments(True)`.
2. After saving each task-owned part, close it with `sw.CloseDoc(title)` and reinsert it by path when assembling.
3. Do not interpret `OpenDoc6` error `65536` as file corruption; it commonly indicates an already-open document with the same title.

## Historical test record

Environment:

- SolidWorks Premium 2024 SP3.1
- Python 3.13
- pywin32 dynamic COM

Exercised example:

- A four-part desktop mini cooling fan: base, central post, bladed impeller, and circular front guard.
- Mates: base/post concentric and coincident; impeller/shaft concentric with rotation unlocked plus axial coincidence; front guard concentric plus angular location.
- State: base/post/front guard fixed; impeller floating.
- Motion Study: an impeller 60 RPM cyclic-rotation study with a 60 RPM impeller motor, `Calculate=True`.

`examples/08_mini_fan_motion_assembly.py` is the repeatable baseline. It exercises modeling, assembly, real mates, Motion Study, and review/export. Fillets/chamfers are not acceptance criteria; blades are stable rectangular shapes rather than complex curved surfaces.
