---
name: solidworks-automation
description: "SolidWorks CAD automation covering historically verified parts, holes/slots, assemblies, drawings, export, and delivery review; capabilities.yaml is authoritative, and unverified capabilities require human review."
metadata: { "openclaw": { "homepage": "https://github.com/wzyn20051216/solidworks-automation-skill", "os": ["win32"], "requires": { "anyBins": ["python", "py"] } } }
---

# SolidWorks Automation Skill

> **Inherited historical guide.** The `name`, `homepage`, module descriptions, and regression statements below describe the upstream
> SolidWorks Automation Skill. This is not a separate ModelOps installation entry and does not mean all inherited capabilities are integrated
> into ModelOps v0.1. For installation, the unified CLI, and verified scope, read this repository's [README](../README.md) and
> [root SKILL](../SKILL.md). Attribution is recorded in [NOTICE](../NOTICE.md).

## Quick start

### Requirements

- Windows; native SolidWorks formats require SolidWorks, while headless open-format output requires no installed CAD application.
- Python 3.10+; native Windows CAD automation additionally needs `pywin32` / `comtypes`.
- MCP/tool access needs `mcp` / `pydantic`.
- GLB/GLTF/OBJ/STL references may also need `trimesh`, `pygltflib`, `numpy`, and `Pillow`.
- For OpenClaw, place the skill in `~/.openclaw/skills/solidworks-automation/` or `~/.agents/skills/solidworks-automation/`.

### Entry preflight

Before SolidWorks automation, agents first run:

```bash
python SKILL_DIR/scripts/sw_preflight.py
```

Before desktop or CLI execution, also run the environment diagnostic:

```powershell
python SKILL_DIR/scripts/cad_studio.py doctor
```

`capabilities.yaml` is the single capability authority shared by the skill, MCP, queue, and UI. Levels are `verified`, `pilot`, `reference_only`, and `not_implemented`; the latter two cannot support unattended delivery.

### Two entry points and two backends

- CAD Studio and Skill/CLI/MCP are peer entry points sharing Automation Job, NeutralCadDocument, Preview Manifest, Evidence Graph, and the capability registry.
- Missing SolidWorks/AutoCAD blocks only native formats such as `SLDPRT/SLDASM/SLDDRW/DWG`; route open-format tasks to `headless_open_format_writing`.
- Headless writing uses `scripts/headless_cad_writer.py`: isolated OCCT/OCP processes write real STEP, IGES, BREP, STL, OBJ, and GLB; 2D backends write DXF, SVG, PDF, and PNG with geometry and SHA-256 evidence.
- DXF delivery also produces `preview_scene`. Convert an existing DXF with `python scripts/cad_studio.py preview-dxf --input drawing.dxf --output drawing.scene.json` or MCP `cadstudio_build_dxf_preview_scene`. It reads only allowlisted entities into a restricted PreviewScene and refuses to overwrite existing files.
- OCCT covers boxes, cylinders, Boolean union, cylindrical-hole cuts, ruled/restricted smooth Loft, straight/single-arc Sweep, closed-shell Knit, and open-surface Thicken. Complex paths, self-intersecting offsets, and missing OCP remain `blocked`. Never fake support through renamed extensions or empty files.
- `delivery-preview` may show only actual artifacts from the current task. Fixed examples must be marked `demo-showcase` and `isDemo: true` and cannot count toward delivery acceptance.

Rules:

1. If `comtypes`, `win32com`, or `pythoncom` is missing, present a clear confirmation:
   `This Python environment lacks comtypes / win32com. May the agent configure these local dependencies automatically? [Y/N]`
2. After `Y` / `yes`, run `python -m pip install "pywin32>=305" "comtypes>=1.2.0"` in the local shell. If declined, stop and provide manual commands.
3. Missing SolidWorks installation/COM registration stops native operations only. If native output is unnecessary and `fallbackPolicy=allow_open_formats`, continue headless output instead of reporting the whole task failed.

### Python dependency notes

Install the minimum dependencies for the task; ordinary part modeling does not require mesh-conversion libraries:

```powershell
# Core SolidWorks COM automation dependencies
python -m pip install -r SKILL_DIR\requirements.txt

# Install only for GLB/GLTF/OBJ/STL inspection, scaling, or conversion
python -m pip install -r SKILL_DIR\requirements-mesh.txt
```

Before converting GLB/GLTF/FBX/BLEND to OBJ/STL, use `importlib.util.find_spec()` to check
`trimesh`, `pygltflib`, and `PIL`. Explain missing libraries and their purpose before installation or provide manual commands.

### Connecting to SolidWorks

```python
import sys; sys.path.insert(0, r"SKILL_DIR/scripts")
from sw_connect import mm
from sw_part import sketch, sketch_circle, extrude_boss
from sw_session import SolidWorksSession

session = SolidWorksSession()
model = session.new_part()

with sketch(model, "Front Plane") as sketch_name:
    sketch_circle(model, 0, 0, mm(25))

extrude_boss(model, sketch_name, mm(50))
session.save(model, r"C:\temp\cylinder.sldprt")
session.export(model, r"C:\temp\cylinder.step")
```

> Replace `SKILL_DIR` with the actual skill installation directory.

## Core workflows

Choose the module matching the task:

| Need | Script | Reference |
|---|---|---|
| Entry preflight and dependency setup | `scripts/sw_preflight.py` | `references/troubleshooting.md` |
| Headless open-format writing | `scripts/headless_cad_writer.py`, `scripts/cad_studio.py write-open-format` | `capabilities.yaml`, shared CAD Core Schema |
| Advanced capability/type-library probe | `scripts/sw_capability_probe.py` | `references/complex-mechanical-routing.md` |
| Guards for model-generated macros | `scripts/sw_macro_guard.py` | `references/openclaw.md` |
| Friendly session API | `scripts/sw_session.py` | - |
| Connection and documents | `scripts/sw_connect.py` | - |
| Appearance/material | `scripts/sw_appearance.py` | `references/appearance.md` |
| Parts: sketches and features | `scripts/sw_part.py` | `references/part-modeling.md` |
| Blind/counterbore/countersink holes, obrounds, and hole acceptance | `scripts/sw_hole_features.py`, `scripts/sw_review.py` | `references/complex-hole-features.md`, `references/review.md` |
| Full sketch definition and driving-dimension audit | `scripts/sw_sketch_constraints.py` | Read all sketch constraint states, including absorbed subsketches; solid geometry alone is insufficient |
| Native Hole Wizard cylindrical counterbores | `scripts/sw_native_holes.py` | `references/complex-hole-features.md`; historical ISO/M8 validation, not two cuts presented as a native hole |
| Native Rib and postcreation checks | `scripts/sw_native_ribs.py` | `references/native-ribs.md`; historical SW2025 open single-line, symmetric two-sided, parallel, undrafted Rib; reread parameters/sketch/volume |
| Natural language to parametric plan / VibeCAD | `subskills/solidworks-vibecad/scripts/plan_from_brief.py` | `subskills/solidworks-vibecad/SKILL.md`, `subskills/solidworks-vibecad/README.md` |
| Read context, execute basic modeling, verify feedback | `scripts/sw_model_context.py`, `scripts/sw_closed_loop.py` | `references/closed-loop-modeling.md`; independent new parts, source preservation, per-step measurements |
| CNC parts with many fillets/chamfers | `subskills/solidworks-fillet-chamfer-cnc/scripts/create_cnc_mount_template.py` | `subskills/solidworks-fillet-chamfer-cnc/SKILL.md`, `subskills/solidworks-fillet-chamfer-cnc/references/cnc-fillet-chamfer-lessons.md` |
| Screw/threaded/tap-drill holes | `subskills/solidworks-threaded-holes/scripts/create_threaded_hole_template.py` | `subskills/solidworks-threaded-holes/SKILL.md`, `subskills/solidworks-threaded-holes/references/threaded-hole-lessons.md` |
| AutoCAD DWG/DXF drafting, linework conversion, and batch edits | `subskills/autocad-automation/scripts/acad_draw.py`, `subskills/autocad-automation/scripts/acad_review.py` | `subskills/autocad-automation/SKILL.md`, `subskills/autocad-automation/references/troubleshooting.md` |
| Assemblies, gear/hinge/drag-compatible mates | `scripts/sw_assembly.py` | `references/assembly.md` |
| Motion Study, rotational motors, result audit | `scripts/sw_motion.py` | `references/motion-study.md`, `references/complex-mechanical-routing.md` |
| Drawings | `scripts/sw_drawing.py` | `references/drawing.md` |
| Export | `scripts/sw_export.py` | `references/export.md` |
| Dimension updates and custom properties | `scripts/sw_document_data.py` | `references/advanced.md` |
| Assembly BOM CSV and Pack and Go | `scripts/sw_delivery.py` | `references/export.md` |
| High-fidelity OBJ/STL references | `scripts/sw_import_mesh_reference.py` | `references/mesh-reference-import.md` |
| Result review | `scripts/sw_review.py` | `references/review.md` |
| Semantic entity references | `scripts/sw_entity_reference.py` | Gradually replace Face1/Edge1 and screen coordinates |
| DFM manufacturing-risk review | `scripts/dfm_review.py`, `scripts/dfm_profiles.py`, `scripts/cad_studio.py check-dfm` | Supplier profiles, B-Rep evidence, structured machining/sheet-metal/laser/printing rules |
| Neutral Routing review and preflight | `scripts/routing_review.py`, `scripts/cad_studio.py check-routing`, `scripts/cad_studio.py routing-preflight` | Endpoints, segments, lengths, bend radii, collision/clearance, supports, BOM; native writes require add-in/license evidence |
| FEA preflight, input, restricted solving | `scripts/fea_analysis.py`, `scripts/fea_convergence.py`, `scripts/cad_studio.py fea-preflight/prepare-fea/run-fea/run-fea-convergence` | Historical CalculiX 2.23 linear/nonlinear statics, plasticity, face contact, final COPEN/CPRESS/CSLIP, and mesh convergence; engineering review remains mandatory |
| Advanced surfaces and molds | `scripts/advanced_geometry.py`, `scripts/advanced_geometry_ocp.py`, `scripts/advanced_surface_ocp.py`, `scripts/cad_studio.py review-advanced-geometry/create-ocp-loft/create-ocp-surface` | Ruled/smooth Loft and restricted Sweep/Knit/Thicken write/reopen B-Rep; G1/G2 and curvature radii are sampled evidence only |
| Local MCP server | `mcp-server/server.py` | `mcp-server/README.md`, `references/mcp-server.md` |
| MCP protocol validation | `scripts/validate_mcp.py` | `mcp-server/README.md` |
| Verification of unwrapped APIs | - | `references/api-lookup.md` |
| OpenClaw integration | - | `references/openclaw.md` |
| Sheet metal/weldments/simulation/properties | - | `references/advanced.md` |
| Enterprise agents / local-first and cloud RAG | `apps/desktop/cad_workbench/knowledge_retrieval.py` | `references/enterprise-agent-rag.md` |
| Codex/Claude/Gemini/OpenCode Provider Adapter | `apps/desktop/cad_workbench/agent_providers.py` | `references/agent-provider-architecture.md` |
| Mechanical engineering DAG orchestration | `apps/desktop/cad_workbench/engineering_orchestrator.py` | `references/complex-mechanical-routing.md` |
| Troubleshooting | - | `references/troubleshooting.md` |

In three historical SW2026 SP01.1 regressions on a basic two-part assembly, native `SavePackAndGo()` wrote the assembly and both parts with status codes 0 and no staging fallback. Some versions may enumerate only the top level before saving. Do not use `AddExternalDocuments` to add native assembly parts; save natively first, then audit actual dependencies. If files remain missing, `scripts/sw_delivery.py::pack_and_go()` defaults to a `pilot` package staged from `GetDependencies2`, with a manifest and SHA-256. Use `fallback_policy="blocked"` for strict native semantics. External references, Toolbox, configurations, and drawings still need human review; the overall capability remains `pilot`.

## OpenClaw collaboration

1. Establish SolidWorks version, interface language, input/output paths, and the intended operation: modeling, assembly, drawing, or export.
2. Reuse `{baseDir}/scripts` modules instead of rewriting COM connection code.
3. Run small, single-purpose Python scripts through OpenClaw `exec` / `shell`, using this minimal import set:

```python
import sys
sys.path.insert(0, r"{baseDir}/scripts")
from sw_connect import connect_solidworks, mm, deg, new_document
```

4. Check for `None`, saving/export success, and files actually written.
5. After model creation/modification, export at least an isometric preview and front/top/right views when needed. Inspect screenshots/BMPs against the user's geometric intent.
6. Consult `references/openclaw.md` for full workflows, prompts, and troubleshooting.

## Workflow

To connect model context, planning, and verification, first read `references/closed-loop-modeling.md`.
The new entry reuses existing modeling functions and supports only its listed basic actions. Observe read-only and validate offline before executing in a new document;
continue, retry within limits, or request revision based on measured feedback. Unsupported fillet/chamfer or assembly tasks use the original specialized workflows.
Do not silently omit steps; this entry does not replace existing capabilities.

1. Choose a backend from `preferredBackend`, `requiredOutputs`, `nativeFormatRequired`, and `fallbackPolicy`; do not assume SolidWorks is always required.
2. For native SolidWorks output, run `sw_preflight.py`. Missing libraries require authorization before automatic installation; missing SolidWorks blocks only the native stage.
3. For open-format output or permitted fallback, run `python scripts/cad_studio.py write-open-format --input model.cadstudio.json --out-dir output`.
4. For a quick DFM review, run `python scripts/cad_studio.py check-dfm --input model.cadstudio.json --output output/dfm_report.json --process machining`, optionally with `--profile supplier.json` and `--brep-evidence brep.json`. Missing material, wall thickness, K-factor, kerf, forming space, or required B-Rep evidence returns `blocked`; passing rules still needs human review.
5. Prefer `SolidWorksSession()` for connecting, opening, creating, saving, and exporting. Combine lower-level `sw_connect.py` / `sw_part.py` calls only when needed.
6. For natural-language briefs, incomplete parameters, or industry knowledge plus prompt templates and parametric planning, read `subskills/solidworks-vibecad/SKILL.md` and generate `design_plan.json` plus an execution summary.
7. For CNC mounts, blocks, or brackets with many fillets/chamfers, read `subskills/solidworks-fillet-chamfer-cnc/SKILL.md`. Use base volume, outer fillets/chamfers, hole/slot cuts, hole-mouth chamfers, then review.
8. For screw/threaded/tapped M3/M4/M5/M6/M8 blind or through holes, read `subskills/solidworks-threaded-holes/SKILL.md`. Use tap-drill geometry, attempt Thread/CosmeticThread, visible 3D helix fallback, mouth chamfer, properties, and review.
9. For ordinary blind/through/counterbore/countersink/obround/pattern tasks, read `references/complex-hole-features.md` and prefer `scripts/sw_hole_features.py`. Cross-check creation evidence with `collect_geometry_measurements()`, `validate_hole_positions()`, and section views.
10. For CAD drawings, mechanical/3D-print enclosures, opening layouts, DWG/DXF, tracing, batch DWG edits, or native AutoCAD previews, first read `subskills/autocad-automation/SKILL.md`. Manufacturing drawings must specify every hole, slot, interface, water port, screw hole, and screw boss with size, count, and locating dimensions. Use hole/slot tables for crowded views, not long leaders in place of dimensions. For ordinary image tracing, retain only source-vectorized linework; reject invented outer contours, facial guides, logo geometry, wave lines, replacement text, or embedded review notes.
11. For faithful original-product appearance or 1:1 replicas, read `references/mesh-reference-import.md`. Prefer public meshes/blueprints over repeated refinement of low-fidelity primitives; use `scripts/sw_import_mesh_reference.py` for OBJ/STL.
12. If an LLM must generate VBA, first use `sw_macro_guard.py` for routing, validation, bounded retries, and local template fallback.
13. Save/export with `session.export()` or `sw_export.py`.
14. Export previews and review them with `sw_review.py`; if GUI/desktop capture is available, also inspect the SolidWorks view.
15. For sheet metal, weldments, complex surfaces, molds, Routing, Simulation/FEA, complex Motion, or configuration families, run `sw_capability_probe.py` and read `references/complex-mechanical-routing.md`. Use `routing-preflight/check-routing` for Routing, `fea-preflight/prepare-fea/run-fea/run-fea-convergence` for FEA, and `review-advanced-geometry/create-ocp-loft/create-ocp-surface` for surfaces. Successful FEA/advanced-surface solving still means `review_required`.
16. For company/project mechanical knowledge, read `references/enterprise-agent-rag.md`. Local knowledge is the default; cloud RAG requires explicit enablement, `external_network`, and human approval.
17. If a task crosses two or more engineering domains among parts, holes/slots/fillets, mates, Motion, drawings/BOM, and multiformat delivery, generate a stage DAG with `apps/desktop/cad_workbench/engineering_orchestrator.py`. Serialize dependent CAD writes and retain artifacts and acceptance evidence per stage. Replan only affected stages and successors after a local change; do not claim an entire engineering task complete from one oversized prompt.

### Mechanical drawing baseline

Ordinary sketches in new parametric mechanical models must be fully defined by dimensions and relations. Read `GetConstrainedStatus()==3`
and verify driving dimensions with `sw_sketch_constraints`; do not eliminate underdefinition merely by Fixing the entire sketch.
Prefer the verified native Hole Wizard interface for standard fastener counterbores. Ordinary pockets/nonstandard geometry may still use cuts.
For identical counterbores on one plane with the same end condition, prefer `create_native_counterbore_group`
to place multiple points in one Hole Wizard positioning sketch. Split features only for differing type, specification, end condition, support face, or another stated reason.
State limits for unverified hole types or standards. Do not silently substitute geometric features and present them as native ones.

For ribs on an L-bracket or similar part, read `references/native-ribs.md` and create native Rib in a new task-owned part,
recording before/after snapshots and readback. Do not use the obsolete nine-argument `InsertRib` or report an ordinary extrusion fallback as native Rib success.
This specialized entry retains original modeling/export functions and does not expand the basic `sw_closed_loop` allowlist.

Apply these defaults whenever the skill participates in CAD, mechanical structure, or 3D-printing work:

1. A readable schematic is not a manufacturing drawing. Openings, slots, interfaces, mounting holes, and printed enclosures require overall dimensions, wall/base thickness, hole/slot sizes, and locating dimensions.
2. When the user requests Chinese common practice, national-standard style, or strict drafting, use appropriate sheet sizes/borders/title blocks, FangSong Chinese text, layered line types, center/hidden lines, real dimension entities, and technical requirements.
3. Long leaders provide local notes, not dimension chains. They must not cross views, cover holes/centerlines/dimension text, or enter the title block.
4. Prefer hole/slot tables for dense layouts. Record location, size, count, and position; tables do not excuse missing locating dimensions.
5. Visually review previews before delivery. Repair omissions, overlaps, crossed lines, and title-block intrusions before reporting completion.

### Faithful appearance and public mesh references

For cars, consumer devices, sculptures, and other real objects, distinguish a visual reference from a manufacturable parametric engineering model:

1. For original-product likeness, request/find public 3D models or multiple-view blueprints and record source, author, license, and download date. Do not claim official Class-A or scan-quality geometry.
2. Convert `.glb/.gltf/.fbx/.blend` to `.obj/.stl`; prefer OBJ for materials and STL as a material-free fallback.
3. Confirm axes and scale from bounds before import, then scale to actual nominal dimensions.
4. For Python conversion/scaling, check optional `requirements-mesh.txt` dependencies, explain their purpose if missing, and request installation.
5. Import OBJ/STL with `sw_import_mesh_reference.py`. Use `LoadFile4(path, "r", create_empty_dispatch_variant(), errors)`, not `OpenDoc6()` or `None` import data.
6. Review four views and identifying features. A nonblank preview is not proof of likeness.
7. If editable engineering structure is later required, reverse-engineer separate parts from the reference and explain that the imported mesh is not a parametric solid.

### Multicolor appearance

For bodywork, glass, lights, tires, wheels, or other multicolor models:

1. Read `references/appearance.md` and use `sw_appearance.py`; never pass a normal Python `list` directly to COM material properties.
2. Set source-part document colors first; use assembly-component overrides where needed.
3. Read RGB back with `verify_appearance()` or `apply_component_palette()` after each write. A setter return alone cannot pass.
4. Call `model.ClearSelection2(True)` before saving/capture; `sw_review.save_preview()` includes this cleanup.
5. Visually confirm that at least three expected colors are visible. Nonblank previews are insufficient.
6. For appearance problems, run `tests/solidworks_appearance_regression.py` before rebuilding the user's model.

### MCP server

When the user asks for MCP support, Codex/Claude Desktop tool integration, or reusable tools instead of repeatedly generated Python:

1. Read `mcp-server/README.md`.
2. If automatic configuration is requested, prefer `powershell -ExecutionPolicy Bypass -File mcp-server/register_all_ai_mcp.ps1 -InstallDependencies`; it attempts Codex, Claude Code, Claude Desktop, Cursor, and Windsurf registration.
3. Run the local `stdio` server with `python mcp-server/server.py`.
4. Prefer `cadstudio_write_open_format` for headless writing. Use `cadstudio_check_dfm`, `cadstudio_check_routing`, `cadstudio_routing_preflight`, `cadstudio_fea_preflight`, `cadstudio_prepare_fea`, `cadstudio_run_fea`, `cadstudio_run_fea_convergence`, `cadstudio_review_advanced_geometry`, `cadstudio_create_ocp_loft`, and `cadstudio_create_ocp_surface` for their respective gates. Use allowlisted `solidworks_*` tools for native actions.
5. Do not expose arbitrary Python/VBA execution. New MCP tools must reuse verified `scripts/sw_*.py` wrappers.
6. Serialize SolidWorks COM operations; the server's global lock reduces session conflicts.
7. Use `examples/08_mini_fan_motion_assembly.py` as a baseline for modeling, assembly, mates, and Motion Study. It does not promise perfect fillet/chamfer appearance.

### Moving assemblies

For interactive dragging, hinges, coupled gears, or real mechanical mates:

1. Read the moving-assembly workflow in `references/assembly.md`; also read `references/motion-study.md` if Motion Study or a motor is explicitly requested.
2. Prefer `resolve_component()`, `get_assembly_entity()`, `find_largest_cylinder_face()`, `add_mate5_checked()`, `add_concentric_mate_by_cylinders()`, and `add_gear_mate_by_cylinders()` in `sw_assembly.py`.
3. Use concentric mates with `lock_rotation=False`; do not fully lock shafts, gears, or covers with three reference planes.
4. Use real Gear Mates, not script animation presented as mechanical coupling.
5. Verify real `MateConcentric`, `MateGearDim`, and other MateGroup children with `collect_mate_feature_summary()` or feature traversal.
6. For a real study, reuse `sw_motion.create_motion_study()`, `add_constant_speed_rotary_motor_by_cylinders()`, and `calculate_and_play()`.
7. After calculation, call `sw_motion.validate_motion_studies()` or MCP `solidworks_validate_motion_study`. Check type, duration, motor count, results, and `results_out_of_date=False`. A timeline, animation, or `Calculate=True` is insufficient.
8. Additional pose-driven or Mate Controller animation may demonstrate motion, but disclose that animation is not interactive freedom. Final verification is dragging successfully in SolidWorks.

## GPT / Kimi / Claude macro strategy

LLM-generated VBA must pass through `scripts/sw_macro_guard.py`:

1. **Model routing**: GPT uses concise prompts; Kimi, Claude, and unknown models receive strict formatting instructions requiring VBA source only.
2. **Local fallback**: after output/parsing failure, select a built-in VBA cube/cylinder/extrusion/sketch template by task keywords rather than immediately giving up.
3. **Output validation**: check `SldWorks`, `ModelDoc2`, `Sub`, and `End Sub` before handing code to SolidWorks; retry invalid output.
4. **Timeout/retry**: use a suggested `30s` request timeout and `1–2` parsing retries with stronger formatting instructions.

Example:

```python
from sw_macro_guard import build_prompt, fallback_macro_for_request, validate_vba_macro

prompt = build_prompt("Draw a 50 mm cylinder", model_name="claude")
macro = fallback_macro_for_request("Draw a 50 mm cylinder")
result = validate_vba_macro(macro)
assert result.ok, result.issues
```

## Rules for unwrapped APIs

Before calling a SolidWorks API not wrapped in `scripts/`:

1. Read `references/api-lookup.md`, then official API documentation or the local SDK/reference material. Confirm signatures, argument meanings, enums, returns, and version differences.
2. Never guess interfaces from memory, especially long COM signatures, `VARIANT` / by-ref parameters, enums, selection marks, and `SaveAs` APIs.
3. Retain a minimal executable script and check every return for `None` / `False`.
4. After implementation, execute it for real, save/export the target, and generate previews/review reports with `sw_review.py`.
5. Record newly discovered pitfalls, codes, compatibility patterns, and stable calls in `references/troubleshooting.md` or the relevant module reference; move reusable logic into `scripts/`.

## Result review

After generating, modifying, importing, or exporting CAD, review the result unless the user explicitly waives review:

1. Check COM returns, features, save/export status, and file size.
2. Refresh the task model with `model.ForceRebuild3(False)` and `model.ViewZoomtofit2()`.
3. Export `isometric/front/top/right` previews and `*_review_report.json` using `scripts/sw_review.py::run_review()`.
4. Inspect `evaluation.status`, `evaluation.issues`, `checks`, and screenshots/BMPs. Confirm the main body, proportions/orientation, required components, overlaps/floating parts, filenames, and output paths.
5. Repair the script and regenerate before reporting problems resolved; saving alone is insufficient.

Example:

```python
from sw_review import run_review

model.ForceRebuild3(False)
report, report_path = run_review(
    model,
    r"C:\temp\review",
    basename="car",
    expected_outputs=[r"C:\temp\car.sldprt", r"C:\temp\car.step"],
)
print(report_path)
print(report["evaluation"])
```

## Key notes

- **Units**: API lengths use **meters**. `mm(50)` converts 50 mm to 0.05 m; `deg(90)` converts degrees to radians.
- **Versions**: `SldWorks.Application` is the version-independent connection ProgID. The upstream shorthand described broad compatibility; it does not establish verified support on every version.
- **Selection**: prefer object-level `Select2()` when a COM reference is available. Planes can use `SelectByID2("PLANE")`; sketches must not rely solely on `SelectByID2("SKETCH")`.
- **Sketches**: prefer `with sketch(model, "Front Plane") as sketch_name:` for entry/exit. `sw_part.py` caches the sketch object to avoid Chinese-language SW2024 name-selection failures.
- **Component insertion**: prefer `sw_assembly.add_component()`. When Chinese-language SW2024 `AddComponent4` returns `None`, the wrapper tries `AddComponent5`, silently loads the part, reactivates the assembly, and retries.
- **Appearance**: for color-critical work, prefer multipart assemblies. Marshal material arrays as `SAFEARRAY(double)` and verify RGB readback.
- **VARIANT**: wrap by-ref arguments with `VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)`.
- **Plane names**: `start_sketch()` supports English `"Front/Top/Right Plane"` and Chinese localized aliases documented in `references/part-modeling.md`.
- **Sketch coordinates**: use the local sketch-plane coordinate system in meters.
- **Moving assemblies**: resolve components before selecting mate entities. `GetCorresponding()` maps part faces/features to assembly context; concentric mates should leave rotation unlocked.
- **Motion Study**: load `swmotionstudy.tlb`. `CreateMotionStudy` / `Activate` / `Calculate` may be properties under pywin32; use `sw_motion.motion_member()` for compatibility.
