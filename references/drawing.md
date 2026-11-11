# Drawing API reference

## Creating views

### Standard orthographic views

```python
drawing.Create3rdAngleViews2(partPath)  # Third-angle projection
drawing.CreateFirstAngleViews2(partPath) # First-angle projection
```

### Custom views

```python
view = drawing.CreateDrawViewFromModelView3(
    ModelName,     # str: part/assembly path
    ViewName,      # str: view orientation (see below)
    X, Y, Z        # float: insertion position (meters)
)
```

View orientation names:
| Name | Description |
|---|---|
| `*Front` | Front |
| `*Back` | Back |
| `*Top` | Top |
| `*Bottom` | Bottom |
| `*Left` | Left |
| `*Right` | Right |
| `*Isometric` | Isometric |
| `*Trimetric` | Trimetric |
| `*Dimetric` | Dimetric |

### View scale

```python
view.ScaleRatio = (1.0, 2.0)  # Scale 1:2
view.ScaleRatio = (2.0, 1.0)  # Scale 2:1
```

## Dimensions

### Automatic dimensions (Model Items)

```python
drawing.InsertModelAnnotations3(
    InsertType,    # int: 0=entire model
    AnnotationType, # int: 32768=model dimensions marked for drawing
    DuplicateDims, # bool
    AutoArrange,   # bool
    UseDoc,        # bool
    UseView        # bool
)
```

> Dynamic pywin32 proxies in SW2024/2026 commonly expose `InsertModelAnnotations3` on the drawing
> `IModelDoc2`, rather than `IModelDocExtension`. The wrapper tries the document first,
> then supports older Extension proxies. `32` means geometric tolerances; `32768` means model dimensions
> marked for drawing. A `False` return or
> missing dimension-entity readback must not be reported as verified dimension evidence.
>
> This API imports only existing model `DisplayDimension` objects. For an undimensioned rectangular sketch
> or a part with only extrusion parameters, first call `sw_part.auto_dimension_sketch()` in sketch-edit mode
> or create model dimensions through explicit parametric modeling steps. The drawing API does not invent dimensions.
>
> The capability registry separately records this path as `drawing_dimension_insertion=verified` (SW2024/2026).
> Historical SW2026 SP01.1 regression read back three real views and six real dimension entities in three consecutive runs.
> Complete drawing delivery remains `drawings_and_bom=pilot`: dimension layout, hole/slot location chains,
> borders, title blocks, and BOM require human visual review.

### SW2026 dimension-text bounds evidence

Local reflection of `SolidWorks.Interop.sldworks.dll` confirmed:

- `IAnnotation.GetPosition()` returns an annotation anchor.
- `IAnnotation.GetTextFormat(index)` / `GetTextFormatCount()` return text formatting.
- `ITextFormat.CharHeight`, `WidthFactor`, and `CharSpacingFactor` expose font dimensions.
- `IDisplayDimension.GetText(swDimensionTextParts_e)` reads user text fragments.
- `IAnnotation` has no native dimension-text bounding-box API. Do not call or claim a `GetBox()` method.

Therefore `scripts/sw_drawing.py::estimate_dimension_text_box()` produces conservative estimated bounds only:

1. Center the bounds at `IAnnotation.GetPosition()`.
2. Estimate unrotated width and height from character count, `CharHeight`, `WidthFactor`, and `CharSpacingFactor`.
3. Since the API does not supply text rotation, use the rectangle's diagonal to construct a square envelope covering any rotation.
4. Use padding `max(1 mm, 0.4 * CharHeight)`; missing fields use conservative defaults and lower confidence.
5. In SW2026, `GetText(0)` may omit the formatted primary dimension value; reserve eight monospaced characters when it is unavailable.

Keep these report fields; never present estimated bounds as native evidence:

```json
{
  "box_source": "estimated",
  "box_confidence": "low | medium | unavailable",
  "box_evidence": {
    "native_bounding_box_available": false,
    "method": "annotation_position_text_format_arbitrary_rotation_envelope",
    "padding_m": 0.001,
    "orientation_assumption": "unknown_angle_conservative_square_envelope"
  }
}
```

Even when estimated bounds reveal no collision, `review_drawing_layout()` still returns
`review_required / DRAWING_LAYOUT_ESTIMATED_EVIDENCE_REQUIRES_VISUAL_REVIEW`。
Intersecting estimated bounds return `DRAWING_LAYOUT_ESTIMATED_COLLISION_RISK`. The finding must use
`evidence_source=estimated` and `confirmed_collision=false`; only native bounds evidence may support
`DRAWING_LAYOUT_COLLISION_DETECTED` as a confirmed collision.
A nonempty BMP/PDF proves only that preview artifacts exist, not that dimensions do not overlap. Final visual review is required.

A stronger non-COM approach is to export PDF through SolidWorks, then call
`sw_review.inspect_pdf_text_layout()` to read the bounds of actual vector text spans. This detects
real overlap between extractable text more reliably than character-width estimates and needs no OCR. It still cannot
prove clearance from dimension lines, geometry, or outlined fonts. Intentional title-block layering, such as a sheet-label template plus page number,
may also intersect real bounds; report overlap risk rather than automatically declaring a visual defect.
If PyMuPDF is missing, install it:

```powershell
python -m pip install -r requirements-pdf.txt
```

For dependencies installed in a custom directory, set `CADSTUDIO_PYMUPDF_PATH` to that directory.

Evidence strength is therefore: PDF vector text bounds > conservative COM anchor/font estimates > OCR.
Retain a final PDF/BMP visual review before delivery.

### Adding dimensions manually

```python
# Select two entities first
drawing.Extension.SelectByID2("Edge1@View1", "EDGE", 0, 0, 0, False, 0, None, 0)
drawing.Extension.SelectByID2("Edge2@View1", "EDGE", 0, 0, 0, True, 0, None, 0)
# Add a dimension
drawing.AddDimension2(x, y, 0)  # Dimension annotation position
```

## Notes and annotations

```python
# Add a note
note = drawing.InsertNote(text)

# Add a surface-finish symbol
drawing.InsertSurfaceFinishSymbol3(...)

# Add a weld symbol
drawing.InsertWeldSymbol(...)

# Add a datum symbol
drawing.InsertDatumTag2(...)
```

## BOM tables

```python
bom = drawing.InsertBomTable4(
    TemplateName,  # str: BOM template path (.sldbomtbt)
    X, Y,          # float: position
    BomType,       # int: 1=top-level, 2=parts-only, 3=indented
    Configuration, # str: configuration name
    TableAnchor,   # str: anchor name
    Hidden         # bool: include hidden components
)
```

## Sheet operations

```python
# Get the current sheet
sheet = drawing.GetCurrentSheet()

# Get all sheet names
names = drawing.GetSheetNames()

# Activate a sheet
drawing.ActivateSheet(sheetName)

# Add a sheet
drawing.NewSheet4(
    Name,        # str: sheet name
    PaperSize,   # int: paper size (5=A4, 6=A3, 7=A2, 8=A1, 9=A0)
    TemplateIn,  # int: 12=custom
    Scale1,      # float: scale numerator
    Scale2,      # float: scale denominator
    FirstAngle,  # bool: first-angle projection
    Template,    # str: sheet-format path
    W, H,        # float: width and height
    PropertySheet, # str
    Zone_LeftMargin, Zone_RightMargin, Zone_TopMargin, Zone_BottomMargin,
    Zone_Col, Zone_Row  # int: zones
)

# Set the sheet format
sheet.SetTemplateName(formatPath)  # .slddrt file path
```

## Exporting PDF

```python
sw = model.GetSldWorksObject()
pdf_data = sw.GetExportFileData(1)  # swExportPDFData
sheet_names = drawing.GetSheetNames()
pdf_data.SetSheets(0, sheet_names)  # 0=specified sheets

errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
model.Extension.SaveAs("output.pdf", 0, 1, pdf_data, errors, warnings)
```
