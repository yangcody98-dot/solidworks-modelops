# Week 1: JavaScript CAD preview research — historical snapshot

> Inherited upstream research, not a current ModelOps feature or performance claim. Research date: 2026-07-31. Counts came from public GitHub REST repository metadata and change over time; they have not been refreshed for this translation.

| Project | Stars | Forks | License | Fit | Historical decision |
| --- | ---: | ---: | --- | --- | --- |
| [three.js](https://github.com/mrdoob/three.js) | 114,133 | 36,455 | MIT | WebGL scenes, GLTF/STL/OBJ loaders, interaction | CAD Studio preview foundation |
| [Online3DViewer](https://github.com/kovacsv/Online3DViewer) | 3,617 | 759 | MIT | Multi-format browser viewer, including STEP/IGES/STL/OBJ | Evaluate format adaptation and UI later |
| [replicad](https://github.com/sgenoud/replicad) | 661 | 78 | MIT | Browser OpenCascade parametric modeling | Future experiment reference; excluded from that week's runtime |
| [three-cad-viewer](https://github.com/bernhard-42/three-cad-viewer) | 380 | 65 | MIT | Three.js CAD viewer components | Reference tree, selection, and camera interaction |
| [occt-import-js](https://github.com/kovacsv/occt-import-js) | 278 | 54 | LGPL-2.1 | OpenCascade WASM STEP/IGES/BREP import | No direct inclusion in the MIT bundle before process-isolation and license review |
| [ThatOpen/engine_components](https://github.com/ThatOpen/engine_components) | 691 | 204 | MIT | BIM/IFC components and 3D engine | Not a close fit for mechanical CAD; not introduced |

## Historical implementation boundary

- Prefer STL, GLB/GLTF, and OBJ for SolidWorks artifacts; dynamically import Three.js loaders to avoid blocking first paint.
- Read-only browser DXF fallback covers `LINE`, `CIRCLE`, and `LWPOLYLINE`; parsing errors must be explicit and cannot be reported as successful CAD execution.
- Actual STEP/IGES and DWG geometry previews come from native SolidWorks/AutoCAD PNG or mesh exports; wireframe placeholders do not establish solid geometry.
- Access local paths only through Tauri `convertFileSrc`. Redact diagnostics; do not upload CAD files, prompts, or keys.

## Proposed follow-up

1. Evaluate `occt-import-js` in a separate worker; complete legal and bundle-size review before deciding on browser STEP previews.
2. Compare Online3DViewer with the current Three.js component for large-model load time, memory, and narrow-window interaction.
3. Add structured DXF layers, dimensions, and borders; fall back to native AutoCAD BMP/PNG for complex entities.
