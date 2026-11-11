# File export reference

## Export formats

| Format | Extension | ExportData required | Description |
|---|---|---|---|
| STEP | `.step` `.stp` | No | General 3D exchange |
| IGES | `.igs` `.iges` | No | Legacy exchange format |
| STL | `.stl` | No | 3D printing / mesh |
| Parasolid | `.x_t` `.x_b` | No | Precision kernel format |
| PDF | `.pdf` | Yes (IExportPdfData) | Drawing export |
| DXF/DWG | `.dxf` `.dwg` | No | 2D drawings / flat patterns |
| 3D PDF | `.pdf` | Yes | PDF with embedded 3D |
| eDrawings | `.eprt` `.easm` `.edrw` | No | Lightweight viewing format |

## SaveAs error codes

| Value | Name | Description |
|---|---|---|
| 0 | swGenericSaveError | Generic error |
| 1 | swReadOnlySaveError | Read-only file |
| 2 | swFileNameEmpty | Empty filename |
| 3 | swFileNameContainsAtSign | Filename contains @ |
| 5 | swFileSaveFormatNotAvailable | Format unavailable |
| 6 | swFileSaveAsDoNotOverwrite | Do not overwrite existing file |
| 9 | swFileSaveAsInvalidFileExtension | Invalid extension |

## SaveAs warning codes

| Value | Name | Description |
|---|---|---|
| 1 | swFileSaveWarning_RebuildError | Rebuild error |
| 2 | swFileSaveWarning_NeedsRebuild | Rebuild required |
| 4 | swFileSaveWarning_ViewsNeedUpdate | Views need updating |

## STL export quality

```python
# Set STL output quality
# swUserPreferenceIntegerValue_e.swExportStlUnits = 78
model.SetUserPreferenceIntegerValue(78, 0)  # 0=Fine, 1=Coarse

# Set custom deviation and angle tolerance
# swSTLDeviation
model.SetUserPreferenceDoubleValue(0x00000F, 0.005)  # Deviation (meters)
# swSTLAngleTolerance
model.SetUserPreferenceDoubleValue(0x000010, 0.174)  # Angle tolerance (radians, about 10 degrees)
```

## Batch conversion example

```python
import os
from sw_connect import open_document

def batch_convert(sw, input_dir, output_dir, input_ext=".sldprt", output_ext=".step"):
    """Convert all matching files in a directory."""
    os.makedirs(output_dir, exist_ok=True)

    for filename in os.listdir(input_dir):
        if filename.lower().endswith(input_ext):
            input_path = os.path.join(input_dir, filename)
            base = os.path.splitext(filename)[0]
            output_path = os.path.join(output_dir, base + output_ext)

# Open; STEP/STP/IGES/IGS automatically use LoadFile4(..., "r", ...)
            errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            model = open_document(sw, input_path, silent=True)

            if model:
                # Export
                model.Extension.SaveAs(output_path, 0, 1, None, errors, warnings)
                sw.CloseDoc(model.GetTitle())
                print(f"Converted: {filename} -> {base + output_ext}")
```

## Auditable batch export

`scripts/sw_export.py::batch_export_formats()` supports multiple inputs and output formats, recording for each output:

- The SolidWorks API return value.
- File existence and byte count.
- Whether the file signature changed during this run.
- Whether the user had already opened the source document.

Existing files are not overwritten by default, and documents already open by the user are not closed. If equal source basenames would produce the same target, block the batch instead of letting the last write replace an earlier result.

## Pack and Go

`scripts/sw_delivery.py::pack_and_go()` uses native `IModelDocExtension.GetPackAndGo()`, `IPackAndGo.SetSaveToName()`, and `IModelDocExtension.SavePackAndGo()`. These signatures were historically cross-checked against local SW2024/2026 Interop, type libraries, and official API Help.

Compatibility: official documentation and Interop expose zero-argument `GetPackAndGo()` returning `IPackAndGo`, but local SW2024/2026 pywin32 objects reported a parameter-not-optional error. The wrapper tries the official pywin32 call first, then native early-bound `comtypes`, preserving the pywin32 error context. `comtypes` first attaches to the active instance; it may quit an instance only when this fallback demonstrably created it.

Safety boundaries:

1. The active document must already be saved to disk.
2. A nonempty target directory is refused unless `overwrite=True` is explicit.
3. Pre-save `GetDocumentNames()` enumeration is not the final success criterion. Run `SavePackAndGo()`, then audit files actually written in this run against `GetDependencies2`. `AddExternalDocuments` adds external attachments, not missing native assembly parts.
4. Return per-file sizes, SHA-256, and `produced_this_run`. Nonzero status codes, no real new files, or missing staging sources must not report success.
5. In three historical local SW2026 SP01.1 regressions, both pre-save enumeration and written output contained one `.SLDASM` and two `.SLDPRT` files: `document_count=3`, all status codes 0, `missing_dependencies=[]`, and no staging fallback.
6. If another version or complex assembly still omits dependencies after saving, the default `fallback_policy=stage_dependencies` uses `GetDependencies2` to create a `backend=solidworks-native+staged_dependencies`, `status=pilot` package with `cadstudio-pack-manifest.json`. Use `fallback_policy=blocked` for strict native semantics.
7. In either mode, manually sample external references, Toolbox parts, configurations, suppressed components, and linked drawings.

Missing dependencies in strict mode return stable gate fields: `status=blocked`, `stage=review`,
and `error_code=SW_PACK_AND_GO_DEPENDENCY_ENUMERATION_INCOMPLETE`. Default staging returns
`status=pilot`, `error_code=SW_PACK_AND_GO_NATIVE_ENUMERATION_INCOMPLETE`: the package can proceed to reviewed delivery but is not native Pack and Go.

Before exporting each format, batch export activates the source and reads back `ActiveDoc.GetPathName()`. SW2024
exporters such as STL may use the active document even if `IModelDoc2.Extension.SaveAs()` on another document reports success.
Stop on a path mismatch to avoid exporting an assembly component as the intended part's STL.

## Coordinates when splitting STEP and rebuilding an assembly

When splitting a complex STEP/Compound into separate STEP files for stable SolidWorks import, do not assume
each imported part uses a local origin. Some exporters preserve original absolute coordinates;
`AddComponent5(..., x=0, y=0, z=0)` may then place every part's bounding-box center at the assembly origin, stacking all components.

Store these manifest fields together:

- `label`: stable component name.
- `step`: split STEP path.
- `color_hex`: expected color.
- `bbox.center_mm` / `bbox.center_m`: global bounding-box center before splitting/export.
- `bbox.size_mm`: size for post-import verification.

Insert at `bbox.center_m` and sample the assembled bounds, key component transforms, and four views before saving.

```python
center = item["bbox"]["center_m"]
component = add_component(
    assembly,
    item["native_path"],
    x=center[0],
    y=center[1],
    z=center[2],
    sw=session.sw,
)
```

Verification priorities:

1. Overall vehicle, frame, or enclosure dimensions should be close to the source STEP.
2. Component count alone is insufficient: count and color readbacks can pass even when every component overlaps at the origin.
3. Pair `run_review()` results with visual PNG/BMP inspection.
