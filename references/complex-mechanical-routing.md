# Routing complex mechanical modeling tasks

## Probe before execution

Before a complex mechanical task, run:

```powershell
python scripts\sw_capability_probe.py --output capability_report.json
```

The report distinguishes:

- `type_library_present`: the local installation contains interface definitions.
- `implementation_status`: this skill has a wrapper exercised by real regression tests.
- `ready_for_unattended_use`: unattended execution is permitted.

An available type library proves neither licensing nor validated automation. Do not report `reference_only`, `not_implemented`, or unsupported `pilot` work as complete.

## Capability levels in this historical guide (current authority: `capabilities.yaml`)

| Domain | Historical level | Execution rule |
|---|---|---|
| Parametric parts, holes/slots, fillets/chamfers | Verified | Use real COM and provide parameter JSON and a review report |
| Assemblies and concentric/distance/gear mates | Verified | Check degrees of freedom and the mate feature tree |
| Motion Study rotational motor | Verified | After calculation, call `collect_motion_study_summary()` and check result freshness |
| Drawings | Pilot | Manually review borders, views, dimension chains, and GB/T formatting |
| Configurations and design tables | Reference only | Run a minimal sample regression before using customer models |
| Sheet metal and weldments | Reference only | `references/advanced.md` alone does not authorize unattended delivery |
| Complex surfaces and molds | Pilot | `create-ocp-loft/create-ocp-surface` can create and reopen restricted ruled/smooth Loft, Sweep/Knit/Thicken. G1/G2 and curvature radii use discrete samples; complex paths and molds remain gated |
| Routing | Pilot | Only `routing-preflight` or `check-routing`; native writes must be blocked without add-in/license evidence |
| Simulation/FEA | Pilot | `run-fea` runs restricted linear/nonlinear statics and parses final-step contact penetration/pressure/slip; `run-fea-convergence` runs 3–8 linear/nonlinear mesh levels. Plasticity, contact, and convergence still require engineering review |

## Complex parts

1. Separate base volumes, primary functions, interfaces, manufacturing details, and appearance features.
2. Prefer stable datums, fully constrained sketches, and named features. Do not rely on `Edge1`, screen coordinates, or incidental selection order.
3. Define continuity targets (G0/G1/G2), parting/draft, thickness, and a feasible manufacturing process for complex surfaces.
4. Sheet-metal records must include thickness, material, inside bend radius, K-factor/bend table, bend directions, and flat-pattern DXF.
5. Weldments must record profile standards, cut lengths, miters, welds, cut lists, and machining allowances.
6. Verify that every configuration/design-table variant rebuilds, has reasonable mass properties, and produces collision-free filenames.

## Complex assemblies and motion

1. Budget degrees of freedom: start with the expected six for each moving component and remove them mate by mate.
2. Use concentric mates plus axial location for rotating components without locking rotation. Use slot/distance/limit mates for linear motion.
3. Contact, friction, springs, damping, gravity, and collisions are outside the rotational-motor validation scope.
4. Motion delivery must include study type, duration, motor count, external-force count, feature count, result existence, and `results_out_of_date`.
5. A playable animation does not prove the mechanism is correct; check interference, travel limits, speed/acceleration, driving force/torque, and mate reactions.
6. Motion Analysis depends on add-ins and licensing. When unavailable, explicitly fall back to Animation/Basic Motion; never fabricate analysis results.

## Gates for new capabilities

1. Confirm the interface, signature, enums, and version from the local `.tlb` or official SolidWorks API documentation.
2. Build a minimal regression sample rather than experimenting on the user's complex assembly.
3. Add a narrow `scripts/sw_*.py` interface and explicitly check every COM return value.
4. Add static tests and real SolidWorks regression scripts.
5. Produce machine-readable acceptance evidence and multiple preview views.
6. Record failure modes in `references/troubleshooting.md` before marking a capability Pilot; require repeated real regressions before marking it Verified.
