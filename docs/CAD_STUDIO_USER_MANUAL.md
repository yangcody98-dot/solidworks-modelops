# CAD Studio user manual — inherited reference

> Historical upstream CAD Studio documentation. It describes the upstream desktop application, frontend, and installers, which ModelOps v0.1 does not distribute. Its claims and version baselines are historical, not the current ModelOps capability contract. Start with the [ModelOps README](../README.md).

CAD Studio was designed for mechanical engineers, students, and designers. Desktop and Skill/CLI/MCP entry points share CAD Core, job contracts, capability metadata, and evidence; files and task records remain local by default.

## 1. Historical workflow scope

The upstream workflow planned basic parts, enclosures, fixtures, and assemblies from natural language; unverified sheet metal and other capabilities were blocked or routed to manual review. Inputs included SLDPRT, SLDASM, STEP, STL, DWG, DXF, PDF, and reference images. Feature requests included through/blind/counterbored/countersunk/threaded holes, obround and semicircular slots, and hole patterns.

Open-format output included `.cadstudio.json`, STL, OBJ, DXF, SVG, PDF, PNG, and reports without vendor CAD. Native SLDPRT/SLDASM/SLDDRW/DWG required the applicable CAD software and a verified backend. Software, material, process, and stages could be selected automatically or manually. Combined projects followed requirements → concept → parts → assembly → motion/interference → drawings → delivery, with approval and review gates.

## 2. Environment

### Desktop application

- 64-bit Windows 10 22H2 or Windows 11; Microsoft Edge WebView2 Runtime, with installer guidance when missing.
- Recommended memory: 8 GB; 16 GB or more for complex assemblies.

### Agent CLI

Install and sign in to at least one supported CLI. CAD Studio includes no model credits and stores no API keys; the CLI or CC Switch manages accounts, plans, proxies, and routing. npm installation requires Node.js 20 or newer. On managed computers, use the official installer or an administrator-approved installation.

| Agent | Official documentation | Installation | Check |
| --- | --- | --- | --- |
| Codex CLI | <https://developers.openai.com/codex/cli/> | `npm install -g @openai/codex` | `codex --version`, `codex login status` |
| Claude Code | <https://docs.anthropic.com/en/docs/claude-code/setup> | Official Windows installer or PowerShell instructions | `claude --version`, then `claude` to sign in |
| Gemini CLI | <https://github.com/google-gemini/gemini-cli> | `npm install -g @google/gemini-cli` | `gemini --version`, then `gemini` to sign in |
| OpenCode | <https://opencode.ai/docs/> | `npm install -g opencode-ai` | `opencode --version`, `opencode auth login` |

Restart CAD Studio after installation. If PowerShell finds the CLI but the application does not, check the npm global directory in the user's `PATH`, or set `CODEX_BIN`, `CLAUDE_BIN`, `GEMINI_BIN`, or `OPENCODE_BIN` to the executable's absolute path.

### Native CAD

Use 64-bit Python 3.10 or later; Python 3.11/3.12 was recommended. Python, CAD, and the operating system should have matching 64-bit architecture. The historical native baselines were SolidWorks 2024, SolidWorks 2026 SP01.1, and AutoCAD 2024. Only capabilities explicitly listing 2026 in `capabilities.yaml` were verified on that release; SolidWorks 2025 and other combinations were compatibility targets in this historical snapshot. Consult the current registry and ModelOps validation record for later evidence.

```powershell
python -m pip install "pywin32>=305" "comtypes>=1.2.0"
python scripts\cad_studio.py doctor
```

`remediations` provides official component URLs and installation commands, also shown in Settings/Help. A missing optional backend blocks its formats only.

### Open-format backend

The upstream headless backend writes actual `.cadstudio.json`, STEP, IGES, BREP, STL, OBJ, GLB, DXF, SVG, PDF, and PNG from NeutralCadDocument, with geometry evidence, Preview Manifest, fallback images, and SHA-256.

```powershell
python scripts\cad_studio.py write-open-format `
  --input .\part.cadstudio.json `
  --out-dir .\output `
  --formats cadstudio step iges brep stl obj glb dxf svg pdf png

python scripts\cad_studio.py preview-dxf `
  --input .\drawing.dxf `
  --output .\output\drawing.scene.json
```

DXF conversion reads only LINE, CIRCLE, ARC, LWPOLYLINE, POLYLINE, TEXT, MTEXT, and DIMENSION, with a 50 MB/200000-entity input limit. Unsupported entities are recorded as limitations; conversion does not execute scripts or overwrite scenes.

The historical OCCT scope covered boxes, cylinders, Boolean unions, cylindrical holes, and a separate restricted closed ruled Loft entry, with validity, volume, bounds, and topology readback. Smooth Loft and other complex features remained `blocked` in that snapshot. Native SLDPRT/SLDASM/SLDDRW/DWG must be `blocked` without vendor software or an authorized SDK; renaming an extension cannot provide native output.

```powershell
python scripts/cad_studio.py doctor
```

Capabilities are governed by `capabilities.yaml`. Configurations/design tables, sheet metal, and weldments were not marked delivered. Restricted CalculiX linear statics and OCP closed ruled Loft remained `pilot`; absent solver results, mesh convergence, or surface-quality evidence could not constitute complete engineering delivery.

```powershell
python scripts\cad_studio.py check-dfm --input .\part.cadstudio.json --output .\output\dfm.json --profile .\supplier-profile.json
python scripts\cad_studio.py routing-preflight
python scripts\cad_studio.py check-routing --input .\route.json --output .\output\routing_report.json
python scripts\cad_studio.py fea-preflight --solver auto
python scripts\cad_studio.py prepare-fea --input .\fea.json --out-dir .\output\fea
python scripts\cad_studio.py run-fea --input .\fea.json --out-dir .\output\fea --timeout 120
python scripts\cad_studio.py review-advanced-geometry --input .\surface-plan.json --output .\output\surface_report.json
python scripts\cad_studio.py create-ocp-loft --input .\loft.json --out-dir .\output\loft
```

Drawing/BOM results included views, actual dimensions, BOM rows, model/drawing relationships, and findings. Model-dimension insertion with dimension-entity readback was verified separately on SW2024 and SW2026 SP01.1; SW2026 produced 3 actual views and 6 dimensions in three consecutive runs. Complete drawing delivery remained `pilot`: sheet size, layout, chains, hole tables, title blocks, and BOM required manual review.

AutoCAD backends were tracked independently: headless DXF, allowlisted commands, COM, and .NET. Local AutoCAD 2024 COM proxies were unstable. The separate Managed API backend passed consecutive allowlisted runs producing and reopening DWG, exporting PDF/PNG, and reading entities/layers/dimensions. Preflight rechecked the last three reports and artifact hashes, returned `verified` for intact evidence, and downgraded damaged evidence. This did not authorize arbitrary DWG operations or plugin code.

```powershell
python subskills\autocad-automation\scripts\acad_dotnet_preflight.py
python subskills\autocad-automation\scripts\acad_dotnet_regression.py
python subskills\autocad-automation\scripts\acad_dotnet_regression.py --real-cad
```

Use `--install-sdk` only with explicit authorization. It installs the .NET SDK from Microsoft and does not download proprietary Autodesk DLLs. If `dotnet.exe` on PATH provides only a runtime, preflight also searches the user SDK directory. Desktop plugins require a trusted path or signature. Native regression records `SECURELOAD/FILEDIA/BACKGROUNDPLOT`, changes them only in an exclusive Core Console, and restores them on exit.

## 3. Historical installers

The upstream installer was `CAD-Studio-<version>-Setup-x64.exe` from its GitHub Releases; run it and launch CAD Studio from Start. The installed binary was `cad-studio.exe`.

The portable archive was `CAD-Studio-<version>-Windows-x64-Portable.zip`. Extract it fully to a writable directory and run `CAD Studio.exe`; retain the adjacent `skill` resources. Historical unsigned builds could trigger SmartScreen's unknown-publisher notice; verify the release SHA-256 before running. These installers are not ModelOps releases.

## 4. First use

1. Check environment status in Help and select an installed Agent in Settings.
2. If using CC Switch, read its status. Only routing name, model, endpoint, and management status are returned from the user's SQLite/JSON configuration, never keys.
3. Choose an independent output directory, install Python dependencies, and start the required CAD application.
4. Start the local executor. Submit tasks after its running status and PID appear.

## 5. Example modeling workflow

Choose New Task/Modeling, then a part, assembly, or enclosure template. A sample request was:

```text
Create a 120 x 80 x 8 mm mounting plate in 6061 aluminum.
Add a 6.6 mm through hole at each corner, 10 mm from both adjacent edges.
Add a central upper-face counterbore, 20 mm diameter and 4 mm deep.
Chamfer the perimeter 1 x 45 degrees.
Output SLDPRT, STEP, a PDF drawing, and four-view PNGs in the current output directory.
```

Leave unspecified software/material/process selections on automatic mode, keep actual hole/cut geometry enabled, enable local CAD automation when required, and review the execution plan before execution or approval.

For existing files, use Import, select CAD/drawing/image input, state what to preserve and change, and explicitly request a new output file.

## 6. Combined engineering projects

Plans separated requirements, CAD/skill routing, part features, mates/interference, Motion Study, GB/T drawings/BOM/tolerances, and export/ledger/review. A local revision such as changing M6 to M8 should rerun only affected stages and downstream dependents.

Retries from failed, blocked, cancelled, or review-required tasks retained read-only snapshots of prior status, artifacts, drawing/BOM evidence, review gates, and errors. The default retained the last 20 rounds of metadata. New outputs used versioned directories/names; snapshots retained paths, sizes, hashes, and evidence, not copied CAD contents, and did not delete earlier deliverables. Missing critical dimensions, tolerances, loads, strength, or safety parameters required clarification or an explicit concept-stage result.

## 7. Interface and routing

The sidebar showed project history; historical titles referring to Codex did not fix the selected provider. Overview covered tasks/import/environment; Modeling covered part/assembly/fixture/sheet-metal/enclosure/reverse tasks; Features covered holes/slots/threads/openings/patterns; Drawings covered GB/T, tolerances, BOM, and conversion; Review covered native opening, dimensions, features, artifacts, and risks.

Delivery classified `ready`, review required, blocked, or incomplete evidence using current artifacts, domain evidence, and manual gates. It displayed version history, relations, backend diagnostics, rotatable STL/GLB/GLTF/OBJ, and read-only DXF/image previews. Settings covered Agent, CC Switch, worker, output, and knowledge; Help covered setup and environment.

Agent CLI selection chooses Codex, Claude Code, Gemini CLI, or OpenCode. CC Switch chooses the provider, endpoint, and model used by that CLI. Selecting Claude also changed the execution button, executor, and route list; synchronizing CC Switch should not switch back to Codex. CC Switch was optional; otherwise the CLI's local login/configuration applied.

## 8. Historical approval and review policy

The upstream policy required approval for controlling desktop CAD, accessing files outside the workspace, external network/cloud knowledge, full-access execution, file deletion, and Git push. This describes upstream policy; apply the current task's authorization and host policy when using ModelOps.

Before marking a task passed, record review notes and confirm native opening; critical dimensions, tolerances, datums, and hole locations; actual cut geometry; mates/interference/motion direction; and current file existence, timestamps, and versions.

## 9. Local storage and troubleshooting

- Default output: the user's `Documents/CADAutomationWorkbench`; queue/settings: `com.wzyn.cadstudio` under user application data.
- Wallpapers, project paths, task events, and ledgers remain local. API keys are not written to settings or jobs.
- Engineering context can leave the machine when cloud RAG is explicitly enabled or the selected CLI itself uses the network. Do not upload confidential queues, logs, or task JSON to public issues.
- Missing Agent: run `--version` in PowerShell, restart, or set the applicable `*_BIN` variable.
- Missing Python: install 64-bit Python 3 with Add Python to PATH, restart, and start the worker.
- Missing CAD: verify installation and launch SolidWorks once manually. Discovery checked COM registration, public shortcuts, standard folders, and common `D:`/`E:` install paths. Installed-but-stopped is not an installation failure.
- Missing CC Switch models: update CC Switch and save configuration; supported sources included `~/.cc-switch/cc-switch.db` and legacy `config.json`.
- Waiting for approval: inspect the reason and explicitly approve; the worker does not infer approval.
- Many sidebar entries: these are persisted task history, not feature menus. Back up deliverables before deleting application data.

## 10. Provenance and support

For upstream issues, provide application/install version, Windows/Python/CAD/CLI versions, reproduction steps, redacted errors, and CC Switch route details; never include API keys.

Upstream CAD Studio source, retained as provenance rather than a ModelOps download link:
<https://github.com/wzyn20051216/solidworks-automation-skill>.
Use the [ModelOps README](../README.md) for this repository's installation and usage.
