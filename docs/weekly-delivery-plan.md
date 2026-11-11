# CAD Studio staged delivery plan — historical record

> Inherited upstream roadmap and results. Historical test counts, timings, versions, install paths, and UI claims below were not rerun for ModelOps and do not define its current capability contract. Some referenced upstream frontend/release tools are intentionally absent from this package. Use [README](../README.md), [capabilities.yaml](../capabilities.yaml), and [VALIDATION.md](VALIDATION.md) for ModelOps.

Each week committed to a buildable, testable, recoverable capability set. Features without native CAD review remained `pilot`, `reference_only`, or `not_implemented`.

| Stage | Goal | Acceptance target |
| --- | --- | --- |
| Week 1 | Local installation discovery, reliability diagnostics, STL/GLB/OBJ/DXF preview foundation | Detect both CAD products; Python/Rust/frontend tests pass; nonblank preview pixels and narrow-window screenshots |
| Week 2 | Separate project/conversation/task/file/review modules and reduce `App.tsx` | Project-switch P95 < 150 ms; migration counts match; deleting projects does not delete CAD deliveries |
| Week 3 | SolidWorks dimensions, batch export, properties/BOM, Pack and Go | Native golden-workflow regression; ledger rejects stale files |
| Week 4 | Drawing views/hole callouts, AutoCAD layer/dimension/border checks, DXF layer preview | Headless DXF checks pass; AutoCAD 2024 ActiveX drawing regression remained `blocked` and must not be reported passed |
| Week 5 | Assembly checks, configuration pilot, artifact comparison/regeneration | Complete capability gates, errors, retry, and human-review evidence |
| Week 6 | 20 stability runs, Windows self-hosted CI, installer regression, v0.4 release | No duplicate CAD instances or orphan workers; 90% first-run success target for golden workflows |

## Week 1 record

- Detected historical installations at `E:\Solidworks\SOLIDWORKS\SLDWORKS.exe` and `D:\AutoCAD 2024\acad.exe`; discovery included public shortcuts and COM registration.
- `cad-studio doctor` returned product, version, source, and path; exported diagnostics retained only filenames.
- Three.js loaded STL, GLB/GLTF, and OBJ on demand; read-only DXF covered `LINE`, `CIRCLE`, `LWPOLYLINE`.
- STEP/IGES and DWG used native exported previews rather than direct browser parsing; placeholders were not accepted as geometry.

## Week 2 record

- `App.tsx` decreased from 3968 to approximately 3479 lines. Project/task/conversation/review/file components and domain modules replaced further growth in one file.
- Project search, archive/restore, duplicate, rename, and confirmed deletion were recorded. Duplication copied metadata/path references, not tasks, conversations, or CAD deliveries.
- Bulk cleanup excluded queued, running, and approval-pending tasks.
- SQLite retained `app_state` snapshots and created project/conversation/message/job indexes; `app_store_migration_status` compared source and index counts.
- Playwright checks at 1440×900 and 900×700 had no console errors; historical `performance.measure("cad-studio.project-switch")` was approximately 18 ms against the 150 ms target.
- Historical results: frontend build passed, 15 Rust tests passed, 118 Python tests passed. Native artifacts remained subject to capability and human-review gates.

## Week 3 and SolidWorks 2026 SP01.1 records

- SolidWorks 2024 part, dimension, property, assembly, BOM, and batch-export workflows passed native regression.
- Early SW2024 Pack and Go enumeration returned only the top assembly; dependency auditing/fallback gates prohibited accepting incomplete packages.
- Historical discovery adapted to `E:\SolidWroks2026\SOLIDWORKS\SLDWORKS.exe`, revision `34.1.1`, `sldworks.tlb`, and Motion/Routing libraries.
- Three consecutive drawing runs produced 3 actual views and 6 dimension entities, with current-run SLDPRT, SLDDRW, PDF, and nonblank previews.
- Final Pack and Go code passed three consecutive native runs: 1 SLDASM + 2 SLDPRT per run, `document_count=3`, statuses `[0,0,0]`, `missing_dependencies=[]`, no staging fallback.
- `comtypes` fallback preferred the active instance and exited only instances owned by that run; no `SLDWORKS.exe` remained after the final two runs or cleanup run.
- `pack_and_go` remained `pilot`: external references, Toolbox, configurations, compressed components, and linked drawings lacked a consecutive regression matrix.

## Weeks 4–6 records

- DXF review schema 2.0 covered entity types, layers, bounds, actual DIMENSION entities, hole centers/diameters, border/title-block candidates, and nonblank PNG pixels.
- AutoCAD 2024 version detection passed, but dynamic `Documents.Count`, `Documents.Add`, `Layers`, and `SelectionSets.Add` proxies were unstable. Native DWG drawing was `not_implemented` in the registry; interactive troubleshooting remained available and headless DXF stayed `pilot`.
- Assembly interference returned `pass/warn/blocked` with counts, items, and manual gates. Configuration inspection returned names/current configuration/limits without design-table batch editing.
- SHA-256 comparisons classified added/removed/changed/unchanged artifacts; regeneration preserved prior output, prohibited overwrite, and required review.
- `scripts/stability_regression.py` ran 20 lifecycle simulations for connection, cancellation, and exiting only task-created instances.
- Historical `scripts/release_check.py` checked UI/Tauri/Cargo version agreement, unique capability IDs, and release files; `.github/workflows/windows-cad-regression.yml` ran native tests only on CAD-equipped self-hosted Windows. Public runners did not fabricate native passes. These upstream release tools are not ModelOps release entry points.

## Next four-week expansion record

- Drawing review returned sheets, views, actual dimensions, tables, frame templates, and manual-review fields; BOM added model/drawing/report traceability.
- Automation Job 2.0 added `drawingEvidence`, `bomEvidence`, `reviewFindings`, `artifactRelations`, and worker classification into `blocked`, `failed`, or `review_required`. Delivery grouped model/drawing/BOM/preview/report; Job 1.0 retained legacy-field reading.
- AutoCAD statuses remained independent: headless DXF `pilot`, allowlisted scripts `pilot`, COM `blocked`. A user-local .NET SDK 8 and AutoCAD 2024 plugin passed `NETLOAD`, native DWG reopen, PDF/PNG, and entity/layer/dimension checks, raising that .NET backend to `pilot` at this stage.
- .NET allowed only `CADSTUDIOPROBE/CADSTUDIOCREATE`, not arbitrary AutoLISP/SCR/C#. AutoCAD 2025–2026 and signed desktop deployment remained unverified.
- `tests/cad_studio_weekly_regression.py` and `tests/solidworks_week4_drawing_regression.py` required explicit `--real-cad` or self-hosted native CI.

## Versioned retry and delivery-gate record

- Before rerunning terminal jobs, read-only `runHistory` retained the latest 20 rounds of artifacts, errors, drawing/BOM evidence, and review state without recursively copying history.
- `retryPolicy` recorded predecessor ID, restart stage, failed-stage-and-downstream scope, preservation, and no-overwrite policy. Worker reused the DAG and required versioned output in the execution prompt.
- Delivery classified `ready/review_required/blocked/failed/incomplete` from current artifacts, domain evidence, review, and blockers; file existence or sidebar completion alone was insufficient.
- Current artifacts, version history, SHA-256 changes, traceability, and AutoCAD diagnostics shared one preview to avoid duplicate rendering on narrow windows.
- Historical `ai_team/delivery-gate-e2e.cjs` used Chromium at 1440×900 review-pending and 760×900 approved states, checking overflow, duplicate previews, and manual approval before ready-for-delivery display.

## Weeks 7–12: headless geometry and 2D writing

- `scripts/headless_occt_service.py` used an isolated OCP subprocess for actual STEP/IGES/BREP/STL/OBJ/GLB, with validity, volume, bounds, and topology readback. Golden cases covered boxes, cylinders, unions, and cylindrical holes.
- `scripts/headless_cad_writer.py` retained `.cadstudio.json`, versioned no-overwrite output, SHA-256, and `producedThisRun`; missing OCP or unsupported features returned `pilot/blocked` instead of partial meshes presented as complete solids.
- Historical results: 7 OCP/open-format and version-preservation regressions passed; complex surfaces, sheet metal, weldments, and parametric features were still unimplemented at that stage.
- DXF writing added `OUTLINE/HOLES/CENTER/DIMENSION/FRAME/TITLE/TEXT`, actual linear/diameter DIMENSION entities, hole centerlines, and optional A4/A3/A2/A1 GB/T-style frames/title fields.
- SVG/PDF/PNG used the same DXF through ezdxf/matplotlib, with explicitly labeled simplified fallback if dependencies were absent; no DWG writing.
- Historical results: 10 2D-writing/DXF-review/PreviewScene tests passed. Frame layout, Chinese fonts, and final manufacturability still required visual review; level stayed `pilot`.

## Weeks 13–20: previews, DXF inspection, and demo boundaries

- `ModelViewport`: on-demand GLB/GLTF/STL/OBJ, standard views, orthographic/perspective cameras, selection, on-demand rendering, and disposal. WebGL/decoder failures used the Manifest PNG fallback.
- `DxfViewport`: worker-parsed DXF/PreviewScene, layers, selection, dimensions/text, and Evidence references; `.scene.json` was routed explicitly.
- Historical Chromium E2E covered desktop, 760px, and 390px windows, Canvas pixels, overflow, provenance, and fallbacks. The independent 20 MB/30 FPS benchmark was unfinished; no performance attainment was claimed.
- `scripts/dxf_preview_scene.py` allowed LINE/CIRCLE/ARC/LWPOLYLINE/POLYLINE/TEXT/MTEXT/DIMENSION, capped at 50 MB/200,000 entities; unsupported entities produced warnings only and no scripts ran.
- `cad-studio preview-dxf` and `cadstudio_build_dxf_preview_scene` required a new `.scene.json` and rejected overwrite.
- Seven fixed help demos—mounting plate, perforated bracket, CPU enclosure, small assembly, GB/T frame, FEA contour, Routing path—were marked `demo-showcase/isDemo` and excluded from delivery decisions.
- E2E covered backend scenes, raw DXF workers, seven demos, and WebGL PNG fallback. FEA/Routing visuals were educational only; actual solving/native Routing required separate gates and returned `blocked` without dependencies.

## Week 21: engineering gates

- DFM added supplier profiles, normalized units, bound B-Rep evidence, and tamper checks; passing rules still yielded `review_required`.
- Routing reviewed neutral endpoints/segments/length/radius/collision-clearance/support spacing/BOM; SW2026 type-library discovery without add-in/license evidence left native writing `blocked`.
- FEA added Schema 1.0, CalculiX/Elmer preflight, and allowlisted CalculiX input. Historical CalculiX 2.23 runs solved restricted linear statics and parsed displacement, stress, and convergence evidence.
- Advanced geometry/mold gates used OCP 7.9.3.1.1 to generate/reopen restricted closed ruled Loft STEP/BREP; smooth Loft, continuity, and molds remained unfinished at that stage.
- CLI/MCP allowlists added `check-routing`, `routing-preflight`, `fea-preflight`, `prepare-fea`, `run-fea`, `review-advanced-geometry`, `create-ocp-loft`, with protocol validation.

## Historical weeks 1–20 audit boundary

Code/evidence covered project/delivery gates, open-format geometry, basic 2D drawing structure, Preview Manifest/Scene, desktop/Skill/CLI/MCP entry points, browser fallbacks, DFM profile/B-Rep evidence, neutral Routing review, restricted CalculiX linear statics, and restricted OCP closed ruled Loft.

Native self-hosted or human review remained necessary for final SolidWorks drawing/BOM visual quality, native AutoCAD DWG, smooth/continuous complex surfaces, FEA mesh convergence and safety, native SOLIDWORKS Routing writing, and the 20 MB/30 FPS target. Unverified capabilities were not treated as completed or as artifacts produced by the current run.
