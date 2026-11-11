# SolidWorks MCP server design

## Architecture

```text
Codex / Claude / other MCP clients
        ↓ stdio MCP
mcp-server/server.py
        ↓ Python COM / pywin32
SolidWorks Desktop
```

SolidWorks is a Windows desktop COM application, not a native MCP service. The MCP server exposes validated `scripts/sw_*.py` wrappers as controlled tools so agents do not generate large ad hoc scripts for every task.

## Transport choice

Use `stdio` by default:

- It suits local desktop applications.
- The client launches the server as a child process with straightforward configuration.
- It exposes no network port, reducing the attack surface.

HTTP is not the default:

- SolidWorks COM is generally tied to the current desktop user's session.
- Concurrent clients can corrupt document state.
- Remote access additionally needs authentication, Origin checks, and desktop-session isolation.

## Registering multiple clients

The installer calls `mcp-server/register_all_ai_mcp.js` to register common local AI clients where possible:

- Codex: `codex mcp add solidworks -- <python> <server.py>`.
- Claude Code: `claude mcp add --scope user solidworks -- <python> <server.py>`.
- Claude Desktop: user-level `claude_desktop_config.json`.
- Cursor: global `~/.cursor/mcp.json`.
- Windsurf: global `~/.codeium/windsurf/mcp_config.json`.

Notes:

1. Local MCP configuration changes occur only when running the `npx` installer or registration script. Importing a skill usually does not execute installation scripts.
2. Clients may require a restart or manual trust confirmation before loading a new MCP server.
3. A skill cannot directly install local MCP for a cloud web product without a local configuration interface.
4. JSON configuration writes create `.bak-*` backups; CLI clients remove an existing server of the same name before reregistering.

## Concurrency policy

`mcp-server/server.py` serializes all tools with a global `RLock` because:

- SolidWorks COM automation is not a general thread-safe service.
- Concurrent document activation, entity selection, or saves can corrupt shared state.
- Motion Study and mate creation depend on the current selection set.

Before each tool call, the server attempts `pythoncom.CoInitialize()` so its MCP worker thread can use COM.

## Tool names

Prefixes reflect backend boundaries: `cadstudio_` covers headless open formats, DFM, Routing, FEA, and advanced-geometry gates; `solidworks_` means real SolidWorks COM operations.

CAD Studio gate tools:

- `cadstudio_write_open_format`
- `cadstudio_build_dxf_preview_scene`
- `cadstudio_check_dfm`
- `cadstudio_check_routing`
- `cadstudio_routing_preflight`
- `cadstudio_fea_preflight`
- `cadstudio_prepare_fea`
- `cadstudio_run_fea`
- `cadstudio_run_fea_convergence`
- `cadstudio_review_advanced_geometry`
- `cadstudio_create_ocp_loft`
- `cadstudio_create_ocp_surface`

Native SolidWorks tools:

- `solidworks_connect`
- `solidworks_new_document`
- `solidworks_open_document`
- `solidworks_save_document`
- `solidworks_close_documents`
- `solidworks_export_active`
- `solidworks_review_active`
- `solidworks_add_rotary_motor`

## Safety boundaries

The initial tool surface does not expose:

- Arbitrary Python execution.
- Arbitrary VBA macro execution.
- Direct file deletion.
- Hidden bulk-close or overwrite actions on user files.

Before adding a hazardous tool, at minimum:

1. Make actions explicit in the name, such as `delete`, `overwrite`, or `close_all`.
2. Restrict paths and parameter ranges in its input schema.
3. Return structured results describing the actual impact.
4. Document `destructiveHint=True`.

## Suggested extension order

Prioritize useful tools with low ambiguity:

1. Documents/export: open, save, export, review.
2. Assemblies: insert components, find by name, create concentric/coincident mates.
3. Motion Study: rotational/linear motors, calculate/play.
4. Part modeling: controlled sketch and feature primitives.
5. Drawings: orthographic views, BOM, PDF export.
6. Headless capabilities: DFM profiles, neutral Routing review, restricted CalculiX linear/nonlinear analysis and mesh sequences, OCP ruled/smooth Loft, Sweep/Knit/Thicken, and planning review for other complex geometry.

Defer:

- Arbitrary sketch constraint solving.
- General smooth Loft, complex sweeps, G1/G2/Class-A, and mold-quality B-Rep generation.
- Large contact problems, automatic penetration acceptance, collision simulation, and safety certification.

## Response format

Tools return JSON by default for continued LLM processing. `response_format="markdown"` is also available for human reading.

Error responses should include:

- `error_type`
- `message`
- `suggestion`

Do not expose raw Python tracebacks to MCP clients.
