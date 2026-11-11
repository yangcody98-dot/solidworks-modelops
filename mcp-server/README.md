# SolidWorks MCP Server

This directory provides a local `stdio` MCP server exposing headless open-format tools and allowlisted SolidWorks COM operations. MCP, CAD Studio, the skill, and the CLI share capability definitions and data protocols.

SolidWorks is a Windows desktop COM application unsuited to concurrent remote clients. The server therefore defaults to `stdio` and serializes all SolidWorks actions with a global lock.

## Requirements

- Windows 10/11
- Using only `cadstudio_write_open_format` does not require SolidWorks/AutoCAD.
- Native `solidworks_*` tools require SolidWorks installed and launched at least once to complete COM registration.
- Python 3.8+
- Python dependencies:

```powershell
pip install -r mcp-server\requirements.txt
```

## Starting the server

From the repository root:

```powershell
python mcp-server\server.py
```

An MCP client normally launches this command as a child process; there is no need to keep it running manually.

## Automatic client registration

The bundled registration tool attempts to register the `solidworks` server with:

- Codex
- Claude Code
- Claude Desktop
- Cursor
- Windsurf

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\mcp-server\register_all_ai_mcp.ps1 -InstallDependencies
```

Register selected clients only:

```powershell
powershell -ExecutionPolicy Bypass -File .\mcp-server\register_all_ai_mcp.ps1 -InstallDependencies -Clients codex,claude-code,cursor
```

The Node.js variant can be used directly by the `npx` installer or CI:

```powershell
node .\mcp-server\register_all_ai_mcp.js --install-dependencies
```

After registration, check each client:

```powershell
codex mcp list
claude mcp list
```

> The repository's `npx` installer runs the multiclient registration tool automatically. Importing a skill alone in some clients does not run installation scripts; execute the registration commands locally.

## Codex-only registration

To register only Codex:

```powershell
powershell -ExecutionPolicy Bypass -File .\mcp-server\register_codex_mcp.ps1 -InstallDependencies
```

## Manual configuration

Replace paths with your local checkout:

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "python",
      "args": [
        "C:\\path\\to\\solidworks-automation-skill\\mcp-server\\server.py"
      ]
    }
  }
}
```

If your client supports CLI registration, a corresponding command is:

```powershell
codex mcp add solidworks -- python C:\path\to\solidworks-automation-skill\mcp-server\server.py
claude mcp add --scope user solidworks -- python C:\path\to\solidworks-automation-skill\mcp-server\server.py
```

## Exposed tools

| Tool | Purpose | Changes SolidWorks state? |
|---|---|---|
| `cadstudio_write_open_format` | Write STEP/IGES/BREP/STL/OBJ/GLB/DXF/SVG/PDF/PNG, preview manifest/scene, and geometry/hash evidence from allowlisted local `.cadstudio.json` | No |
| `cadstudio_build_dxf_preview_scene` | Convert allowlisted DXF entities read-only to `.scene.json` without overwriting an existing file | No |
| `cadstudio_check_dfm` | Check machining, sheet metal, laser cutting, or 3D printing rules on NeutralCadDocument with supplier profiles and B-Rep evidence; missing inputs block, and passing rules still require human review | No |
| `cadstudio_check_routing` | Check neutral Routing endpoints, segments, lengths, bend radii, collisions/clearances, supports, and BOM | No |
| `cadstudio_routing_preflight` | Probe Routing type libraries, add-in registration, and license evidence; block if evidence is missing | No |
| `cadstudio_fea_preflight` | Probe CalculiX/Elmer availability without running arbitrary commands | No |
| `cadstudio_prepare_fea` | Generate versioned CalculiX `.inp` from FEA 1.0/1.1 requests without arbitrary scripts | No |
| `cadstudio_run_fea` | Run allowlisted linear/restricted nonlinear static CalculiX jobs and parse displacement, stress, and convergence evidence | No |
| `cadstudio_run_fea_convergence` | Run 3–8 allowlisted mesh levels and compare displacement/stress changes in the last two | No |
| `cadstudio_review_advanced_geometry` | Validate neutral surface/mold plans and return pilot/blocked gate evidence | No |
| `cadstudio_create_ocp_loft` | Create real ruled Loft STEP/BREP/STL from allowlisted closed sections and reopen B-Rep for verification | No |
| `cadstudio_create_ocp_surface` | Create smooth Loft, straight/arc Sweep, closed-shell Knit, or open-surface Thicken from strict JSON with sampled continuity evidence | No |
| `solidworks_health_check` | Check dependencies, SolidWorks detection, Motion type library, and optional live connection | No |
| `solidworks_connect` | Connect to/start SolidWorks and return the active document summary | No |
| `solidworks_new_document` | Create a part/assembly/drawing | Yes |
| `solidworks_create_basic_part` | Create a box/cylinder part, optionally save and color the document | Yes |
| `solidworks_open_document` | Open an existing SolidWorks document | Yes |
| `solidworks_add_component` | Insert a part/subassembly into the active assembly and optionally fix it | Yes |
| `solidworks_set_component_fixed` | Fix or float components matched by name keyword | Yes |
| `solidworks_save_document` | Save or Save As the active document | Yes |
| `solidworks_close_documents` | Close the active/all documents | Yes; unsaved changes may be discarded |
| `solidworks_add_coincident_mate` | Add a coincident mate between specified planes/features of two components | Yes |
| `solidworks_add_distance_mate` | Add a distance mate between specified planes/features of two components | Yes |
| `solidworks_add_concentric_mate` | Add a concentric mate filtered by cylinder radius, optionally locking rotation | Yes |
| `solidworks_set_appearance` | Set document or component appearance color | Yes |
| `solidworks_export_active` | Export the active document as STEP/STL/IGES/Parasolid/PDF/DXF | Yes; writes files |
| `solidworks_update_dimension` | Edit an exact named dimension and return before/after, rebuild, and save evidence | Yes |
| `solidworks_set_custom_properties` | Write/read file-level or configuration-specific properties | Yes |
| `solidworks_batch_export_files` | Batch multiple files/formats and verify this run's artifacts | Yes; writes files |
| `solidworks_export_assembly_bom` | Export component/property BOM CSV with mandatory human review | Yes; writes files |
| `solidworks_pack_and_go` | Package documents and references with native Pack and Go | Yes; writes files |
| `solidworks_review_active` | Export BMP views and a JSON review report | Yes; writes files |
| `solidworks_create_hole_feature` | Create blind/through/counterbore/countersink holes or obround slots and return parameter evidence | Yes |
| `solidworks_inspect_hole_features` | Read B-Rep hole segments, compound holes, and slot ends; verify positions | No |
| `solidworks_add_rotary_motor` | Create a Motion Study and constant-speed motor in the active assembly | Yes |
| `solidworks_inspect_motion_studies` | Read studies, motor/force counts, and result freshness | No |
| `solidworks_validate_motion_study` | Gate delivery on duration, type, motor count, result existence, and freshness | No |

## Basic assembly examples

Create a cylindrical part:

```json
{
  "shape": "cylinder",
  "radius_mm": 25,
  "depth_mm": 50,
  "output_path": "C:\\temp\\cylinder.SLDPRT",
  "color": "#BFC4C8"
}
```

Insert and fix a component in the active assembly:

```json
{
  "path": "C:\\temp\\base.SLDPRT",
  "x_mm": 0,
  "y_mm": 0,
  "z_mm": 0,
  "fix_component": true
}
```

Add a concentric mate preserving rotation:

```json
{
  "component_a_keyword": "stand",
  "component_b_keyword": "impeller",
  "radius_a_min_mm": 4.5,
  "radius_a_max_mm": 5.5,
  "radius_b_min_mm": 11,
  "radius_b_max_mm": 13,
  "lock_rotation": false
}
```

Add an axial distance mate:

```json
{
  "component_a_keyword": "stand",
  "component_b_keyword": "impeller",
  "feature_a_name": "Front Plane",
  "feature_b_name": "Front Plane",
  "distance_mm": 42
}
```

## Motion Study example

The active document must be an assembly containing a stationary shaft/post and an impeller. The impeller's concentric mate must not lock rotation, and the component must not be fixed.

Example arguments:

```json
{
  "shaft_component_keyword": "stand",
  "rotor_component_keyword": "impeller",
  "shaft_radius_min_mm": 4.5,
  "shaft_radius_max_mm": 5.5,
  "rotor_radius_min_mm": 10.5,
  "rotor_radius_max_mm": 11.5,
  "rpm": 60,
  "study_name": "Impeller_60RPM_Cycle",
  "motor_name": "ImpellerMotor_60RPM",
  "duration_seconds": 4,
  "calculate": true,
  "play": false
}
```

Create a compound counterbore:

```json
{
  "feature_kind": "counterbore",
  "center_x_mm": 20,
  "center_y_mm": 15,
  "diameter_mm": 6,
  "secondary_diameter_mm": 12,
  "secondary_depth_mm": 4,
  "plane_name": "Front Plane",
  "feature_name": "H1_Counterbore"
}
```

Validate the Motion Study:

```json
{
  "study_name": "Impeller_60RPM_Cycle",
  "expected_study_type": 1,
  "minimum_duration_seconds": 4,
  "minimum_motor_count": 1,
  "require_results": true
}
```

## Design principles

- Do not expose arbitrary Python/VBA execution through MCP.
- Use `cadstudio_` for headless/gate tools and `solidworks_` for native tools to avoid naming collisions with other servers.
- Serialize COM operations to reduce desktop-session instability.
- Include suggested next actions in errors so the agent can correct failures.

## Known limits

- The inherited MCP surface covers boxes/cylinders, compound holes/slots, component insertion, common mates, fixed/floating states, appearances, export/review, rotational motors, Motion result gates, and controlled DFM/Routing/FEA/advanced-geometry entries.
- The inherited conservative scope permits real restricted closed ruled-Loft STEP/BREP creation and reopening; smooth lofts, sweeps, freeform surfaces, G1/G2, and molds are otherwise described as structured-plan gates. Consult `capabilities.yaml` and the specific OCP tool contract for current restricted implementations.
- Motion/Simulation license differences affect calculation. Missing valid add-ins or authorization return `blocked`; the server does not bypass licensing.
