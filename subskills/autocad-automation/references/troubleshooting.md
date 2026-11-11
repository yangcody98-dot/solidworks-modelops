# AutoCAD automation troubleshooting

## Python dependencies

Symptom: `ModuleNotFoundError: No module named 'win32com'`.

Remedy:

```powershell
python -m pip install pywin32
python -m pywin32_postinstall -install
```

With multiple Python installations, install into the interpreter running the scripts.

## AutoCAD COM is unavailable

Symptoms: `Invalid class string`, `Operation unavailable`, or failure to create `AutoCAD.Application`.

1. Confirm Windows desktop AutoCAD is installed.
2. Launch it manually once to finish COM registration and first-run setup.
3. Check for a service session without a desktop, remote GUI restrictions, or restricted permissions.
4. With multiple versions, try `AutoCAD.Application` first; inspect registered version-specific ProgIDs if necessary.

## AutoCAD is open without an active document

Symptom: connection succeeds but `ActiveDocument` access fails.

Create a drawing with `Documents.Add()` or explicitly open the target DWG.

## Layers or ModelSpace access fails after document creation

Symptom: `Layers` access on the result of `Documents.Add()` raises `AttributeError: Add.Layers`.

With AutoCAD 2024 and pywin32 dynamic proxies, the result may not be a stable `AcadDocument` proxy. Rebind after creation:

```python
app.Documents.Add()
doc = app.ActiveDocument
```

`scripts/acad_session.py` implements `new_document()` this way.

## SendCommand appears ineffective

Common causes:

- Missing final newline.
- Asynchronous execution followed by saving before completion.
- Localized command names.
- A command waiting for input.

Recommendations:

- Prefer the COM object model.
- Prefix commands with `_.`, for example `_.ZOOM _E`.
- Supply all arguments and final newlines explicitly.
- Wait, then verify with `acad_review.py`.

## Save failures or overwrite risks

- Use absolute output paths.
- Create directories before saving.
- Save a copy before editing an existing DWG.
- Close other applications holding the target file.
- Record failures and stop derivative exports when saving fails.

## DXF export fails

Symptoms: `Document.SaveAs("xxx.dxf")` fails, or AutoCAD returns unreadable COM error text.

Use `Document.Export(fileBase, "DXF", selectionSet)` rather than relying on extension-based `SaveAs` inference.
ActiveX `Export` requires a `SelectionSet` even for a full drawing; a temporary empty set can be used. `scripts/acad_session.py` wraps this in `export_dxf()`.

## Traces contain unexpected outlines, ellipses, triangles, or colors

Symptoms:

- The user identifies unexplained outer outlines or extra geometry.
- Large arcs/polylines surround a portrait, ellipses/polylines appear on the face, triangles appear near logos, or colored waves surround splashes.
- Review finds non-source layers such as `PORTRAIT_OUTLINE`, `BODY_OUTLINE`, `JERSEY_OUTLINE`, `FACE_FEATURES`, `LOGO_GEOMETRY`, `WATER_SPLASH`, `JERSEY_STRIPE`, `TEXT_LOGO`, `TEXT_BRAND`, or `REVIEW_NOTES`.

Causes:

- Manually added outlines, facial details, logos, splashes, or text intended to improve resemblance.
- Users interpreting those additions as real entities or erroneous guides rather than retouching.
- Review notes and scores contaminating final ModelSpace.

Remedy:

1. For faithful tracing, retain only vectorized source lines such as `TRACE_DARK` and `TRACE_LIGHT`.
2. Remove or disable manual enhancements and construction layers; a verbal explanation is insufficient.
3. Put review notes, scores, and parameters in JSON/Markdown reports, not ModelSpace.
4. Require zero entities on prohibited layers:

```python
aux_layers = [
    "PORTRAIT_OUTLINE", "BODY_OUTLINE", "JERSEY_OUTLINE",
    "OUTER_GUIDE", "CONSTRUCTION", "FACE_FEATURES",
    "LOGO_GEOMETRY", "WATER_SPLASH", "JERSEY_STRIPE",
    "TEXT_LOGO", "TEXT_BRAND", "REVIEW_NOTES",
]
assert all(layer_counts.get(name, 0) == 0 for name in aux_layers)
```

5. If enhancement or reconstruction is explicitly requested, isolate additions on separate layers and state that they are manual enhancements that can be disabled.

Lessons:

- Recognizability does not justify guessed geometry. Faithful tracing prioritizes clean output without extra entities.
- Colored guides, ripples, replacement text, and construction geometry can reduce trust even if they improve a technical score.
- Include negative acceptance checks: no extra guides, in-drawing explanations, or non-source decoration.

## COM temporarily rejects calls or returns unreadable errors

Symptoms:

- `pywintypes.com_error: (-2147418111, ...)` during batch line/layer creation, possibly with unreadable text.
- Intermittent failures in `Layers.Item()`, `Layers.Add()`, or `ModelSpace.AddLine()` that disappear on retry.

Causes:

- Desktop AutoCAD COM is single-threaded and interactive; drawing, regeneration, opening, or export can make it temporarily busy.
- Parallel access to one instance worsens this behavior.

Remedy:

1. Serialize review, preview, and drawing COM work.
2. Use bounded retries/backoff for frequent calls, particularly layers, `AddLine`, `SelectionSets`, `Export`, and `SaveAs`.
3. Wait 1-2 seconds after opening/creating a document, then rebind `app.ActiveDocument`.
4. In large drawings, call `Regen()` / `live_update()` every few hundred entities without excessive updating.

Example:

```python
for attempt in range(12):
    try:
        ent = model.AddLine(p0, p1)
        break
    except Exception:
        if attempt == 11:
            raise
        time.sleep(0.08 + attempt * 0.04)
```

## ModelSpace is not directly iterable

Symptom: `for entity in session.model` raises `TypeError: This object does not support enumeration`.

Some AutoCAD/pywin32 dynamic proxies expose `Count` and `Item(index)` without Python iteration. Use:

```python
ms = doc.ModelSpace
for i in range(int(ms.Count)):
    entity = ms.Item(i)
```

## SaveAs cannot overwrite the open DWG

Symptom: `SaveAs(target)` reports a document-save error after generation; the target exists or is open in AutoCAD.

1. Do not force-overwrite an older file the user has open.
2. Use a new versioned/descriptive name, such as `_approved` or `_trace_only`.
3. Verify file existence and size, then export DXF and previews.

## SelectionSets or Export proxy errors

Symptoms:

- `doc.SelectionSets.Add(name)` raises `AttributeError: <unknown>.Add`.
- `doc.Export(...)` raises `AttributeError: Open.Export` or another proxy mismatch.
- DWG saves, but DXF or BMP export independently fails.

Likely causes: a busy application, wrong active-document proxy, or an unstable dynamic proxy after opening a read-only drawing.

1. Serialize operations; do not run `acad_review.py` and `acad_preview.py` together.
2. Wait after opening, then reacquire `app.ActiveDocument`.
3. Delete same-name SelectionSet remnants and use bounded retries.
4. If native BMP export fails but DWG/DXF and entity checks pass, report the preview-export failure and available evidence. Do not fabricate screenshots.

## Window screenshots are obscured or black

Symptom: an OS screenshot captures another window or only a small black image.

1. A screenshot shows the visible desktop, not necessarily the DWG's correctness.
2. Prefer `scripts/acad_preview.py`, using native `Document.Export(..., "BMP", selectionSet)`.
3. Run `Regen()` and `ZoomExtents()` first, then inspect borders, views, text, dimensions, and overlaps.
4. If an OS screenshot is still needed, establish that AutoCAD is unobscured. Obscured screenshots cannot establish success.

## The drawing process is invisible

Symptom: DWG generation succeeds but the user cannot see AutoCAD launch or watch drawing.

1. Use default `scripts/acad_draw.py` without `--fast`.
2. Ensure `live_preview` is not `false`; it should default to `true`.
3. Call `AutoCADSession.activate_window()` and `live_update()` after each step.
4. Other windows may steal focus; retain native previews as final review evidence.

## SelectionSet name conflicts

Symptom: creating a set reports an existing name.

Enumerate `doc.SelectionSets`, delete the same-name set, then create its replacement.

## Bounding-box reads fail

Some empty or proxy entities do not support `GetBoundingBox`. Record and skip those reads rather than failing the entire review.

## PDF or plot output is unreliable

PDF depends on the plotter, PC3, page setup, CTB/STB, and background plotting:

- Prefer the template's existing PageSetup.
- Disable background plotting or wait for Plot to finish.
- Check the PDF file size.
- Open critical PDFs to inspect border, orientation, scale, and lineweights.

## An exited task-owned instance is reported as running

Symptom: files and previews exist and `acad.exe` is gone, but regression reports that the launched instance did not exit within the timeout.

`Quit()` and `TerminateProcess()` can return before Windows completes exit. A single or premature check can mistake propagation delay for a leaked process.

1. Record only the PID launched by `DispatchEx` and resolved from AutoCAD's main-window handle. Never call `Quit()` or force termination when attached to the user's instance.
2. Request `Quit()` and wait for that exact PID. On timeout, terminate only that recorded task PID, wait, and confirm exit again.
3. Preserve `owned_process_id`, `quit_requested`, `forced_termination_used`, `process_exit_confirmed`, and cleanup errors. CLI exception handling must not overwrite original cleanup evidence.
4. If cleanup fails, check `Get-Process acad -ErrorAction SilentlyContinue` and investigate the recorded PID. Never close all AutoCAD processes by name.
