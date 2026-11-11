# Importing high-fidelity mesh reference models

When a user requests an original-product appearance, 1:1 replica, or a faithful model of a car, consumer device, or sculpture, first distinguish an editable engineering solid from a visual reference. For visual fidelity, prefer a public 3D model or multiple-view blueprint; do not repeatedly refine low-fidelity prisms built from scratch.

## Appropriate uses

- The user explicitly wants a faithful real-product appearance, such as an original Xiaomi SU7 or a 1:1 reconstruction from published images.
- Presentation, proportion checks, visual reference, or a basis for later reverse engineering.
- Mesh or DCC inputs such as `.glb`, `.gltf`, `.obj`, `.stl`, `.fbx`, or `.blend`.

Not appropriate when:

- The user needs editable mechanical features, manufacturing drawings, Class-A surfaces, or sheet-metal construction.
- Internal structure, assembly constraints, tolerances, or manufacturing features are required. Remodel or reverse-engineer separate parts; do not describe a triangle mesh as an engineering solid.

## Choosing a route

1. Obtain reliable input: prefer the user's model, then a public downloadable model, then front/side/top/rear blueprints for outline reconstruction.
2. Record the URL, author, license, and download date. A noncommercial designation does not waive attribution or share-alike requirements.
3. Preserve source GLB/FBX/OBJ files alongside converted OBJ/STL files and write a `manifest.json`.
4. Normalize scale and axes: inspect bounds first, then scale to actual nominal dimensions. Common vehicle axes are `X=width`, `Y=height`, `Z=length`.
5. Prefer OBJ: it is more likely to retain materials, transparent glass, lights, and interiors. STL is robust but generally loses materials.
6. Visually inspect four views after SolidWorks import. A rule-based pass may establish file existence/nonblank previews, not resemblance to the requested object.

## Converting GLB/FBX/BLEND

SolidWorks support for these formats is inconsistent; convert them first:

- With Blender: import and export OBJ/STL, keeping the texture directory.
- With Python: read GLB using `trimesh` and export OBJ/STL; prefer OBJ when preserving materials.
- Do not directly convert high-polygon models to STEP. Thousands of triangular B-Rep faces can hang SolidWorks `LoadFile4` or disconnect RPC.

### Optional Python dependencies

Mesh conversion is not required for ordinary SolidWorks modeling. Before inspecting, scaling, or exporting textures from GLB/GLTF/OBJ/STL, check:

| Library | Purpose |
|---|---|
| `trimesh` | Read GLB/GLTF/OBJ/STL, compute bounds, export OBJ/STL/PLY |
| `pygltflib` | Inspect GLTF/GLB metadata and resources in detail |
| `numpy` | Scale transforms and axis operations |
| `Pillow` | Texture image I/O and preview support |

Check command:

```powershell
python - <<'PY'
import importlib.util
for name in ["trimesh", "pygltflib", "numpy", "PIL"]:
    print(name, "OK" if importlib.util.find_spec(name) else "MISSING")
PY
```

If missing, explain the dependency and ask the user to install it:

```powershell
python -m pip install -r SKILL_DIR\requirements-mesh.txt
```

Opening an existing OBJ/STL for SolidWorks import may not require these libraries. Converting GLB/FBX/BLEND or rescaling to real dimensions usually does.

Scale example:

```python
import numpy as np
import trimesh

scene = trimesh.load(r"E:\source\SU7.glb", force="scene")
mesh = scene.dump(concatenate=True)

# Source axes: X=width, Y=height, Z=length; target dimensions are in meters.
target_extents = np.array([1.963, 1.455, 4.997])
scale = target_extents / scene.extents
center_xz = np.array([
    (scene.bounds[0][0] + scene.bounds[1][0]) / 2,
    0,
    (scene.bounds[0][2] + scene.bounds[1][2]) / 2,
])

vertices = mesh.vertices.copy()
vertices[:, 0] = (vertices[:, 0] - center_xz[0]) * scale[0]
vertices[:, 1] = (vertices[:, 1] - scene.bounds[0][1]) * scale[1]
vertices[:, 2] = (vertices[:, 2] - center_xz[2]) * scale[2]
mesh.vertices = vertices

mesh.export(r"E:\work\reference_scaled_m.obj")
mesh.export(r"E:\work\reference_scaled_m.stl")
```

## Stable SolidWorks import call

Prefer:

```powershell
python scripts\sw_import_mesh_reference.py `
  E:\work\reference_scaled_m.obj `
  E:\work\reference_obj.SLDPRT `
  --units m `
  --model-type graphics `
  --review-dir E:\work\review_obj
```

Important details:

- Do not open OBJ/STL as ordinary parts with `OpenDoc6()`; some SW2024 installations return `errors=2097152`.
- Do not pass `None` as the third `LoadFile4()` argument for OBJ/STL; it can cause a type mismatch.
- Use `LoadFile4(path, "r", create_empty_dispatch_variant(), errors)`.
- STEP/STP/IGES/IGS still use the foreign-CAD path in `sw_connect.open_document()`: `GetImportFileData()` plus `LoadFile4(..., "r", import_data, errors)`.
- Import high-polygon appearance models as `graphics` by default. Use `surface` or `solid` only when explicitly attempting solid repair.

## Review criteria

After import, check at least:

1. The output `.SLDPRT` exists and has a reasonable size.
2. `run_review()` exports `isometric/front/top/right` views.
3. The isometric view shows the main appearance, and front/side/top proportions match the target.
4. Recognizable details exist: for a car, roofline, lights, wheels, side windows, and front/rear fascia.
5. Selection highlighting does not contaminate colors/materials; call `ClearSelection2(True)` before screenshots.
6. Explain that a mesh reference is not an official parametric surface model. Manufacturing-quality work requires subsequent part-by-part reverse engineering.

## Historical SU7 lessons

- Unsuccessful approach: manually script layered prisms/capsule shells and keep adding lights, wheels, and glass. Refining such a base still misses an original-SU7 brief.
- Successful approach: find a public SU7 mesh, retain source/license information, convert to OBJ/STL, scale to `4997 × 1963 × 1455 mm`, then import into SolidWorks.
- API pitfall: `OpenDoc6()` failing on OBJ/STL does not prove file corruption. `LoadFile4()` also fails with `None`; pass an empty Dispatch variant.
- Material lesson: OBJ is more likely than STL to preserve glass, tail-light, interior, and wheel materials. Keep STL as a material-free fallback.
- Review lesson: an automated pass does not establish SU7 fidelity. Inspect previews for identifying details, proportions, and displaced parts.
