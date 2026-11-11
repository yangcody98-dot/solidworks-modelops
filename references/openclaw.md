# Controlling SolidWorks from OpenClaw

This guide helps agents invoking the skill reuse the existing `scripts/` wrappers reliably in OpenClaw instead of rewriting COM automation for each task.

## Preflight

1. Windows is required.
2. Install SolidWorks and preferably open it manually once to confirm COM works. If it cannot be detected, stop native operations and explain that SolidWorks must be installed manually.
3. `python` or `py` must be executable on PATH.
4. Install `pywin32` / `comtypes`. Run preflight first:

```bash
python {baseDir}/scripts/sw_preflight.py
```

Preflight rules:

- If `comtypes`, `win32com`, or `pythoncom` is missing, ask: `This Python environment lacks comtypes / win32com. May the agent configure the local dependencies automatically? [Y/N]`
- After confirmation, run `python -m pip install "pywin32>=305" "comtypes>=1.2.0"`.
- If declined, stop and provide the manual installation command.

5. Install the skill in one of these directories:

```text
~/.openclaw/skills/solidworks-automation/
~/.agents/skills/solidworks-automation/
```

## Recommended execution flow

1. Establish the SolidWorks version, interface language, intermediate/output paths, units, and target formats.
2. Run `sw_preflight.py`, then prefer `scripts/sw_connect.py`, `scripts/sw_part.py`, `scripts/sw_assembly.py`, `scripts/sw_drawing.py`, and `scripts/sw_export.py`.
3. If a model must generate a VBA macro, use `scripts/sw_macro_guard.py` for model routing, output validation, retry, and template fallback.
4. Split work into connection, open/new document, modeling/assembly, saving, export, and screenshot/preview review.
5. Check each return value; never assume COM succeeds.
6. Verify that saved/exported files actually exist.
7. After creating or changing a model, export at least an isometric preview. If desktop capture is available, also inspect the current SolidWorks window.

## Minimal import template

When executing Python through OpenClaw, use `{baseDir}` for the skill root:

```python
import sys
sys.path.insert(0, r"{baseDir}/scripts")

from sw_connect import connect_solidworks, mm, deg, new_document, open_document, save_document
from sw_preflight import run_preflight
from sw_part import start_sketch, end_sketch, sketch_rectangle, sketch_circle, extrude_boss, extrude_cut
from sw_export import export_to_step, export_to_stl, export_to_pdf
from sw_review import run_review

run_preflight()
```

## Guards for model-generated VBA

When asking GPT / Kimi / Claude for VBA, do not send raw model output directly to SolidWorks. Use `sw_macro_guard.py`:

```python
from sw_macro_guard import build_prompt, generate_macro_with_guard, validate_vba_macro

prompt = build_prompt("Draw a 50 mm cylinder", model_name="kimi")
```

Execution contract:

1. GPT-family models use concise prompts.
2. Kimi, Claude, and unknown models receive stricter output-format prompts.
3. Before execution, `validate_vba_macro()` must check for `SldWorks`, `ModelDoc2`, `Sub`, and `End Sub`.
4. Retry parsing failures `1–2` times with stronger format instructions.
5. After failed retries, select a local cube/cylinder/extrusion/sketch template from the task keywords.

## Example prompts

Examples that invoke the skill in OpenClaw:

- "In SolidWorks, create a 120x80x10 mm mounting plate with a diameter-6 hole at each corner. Save to `C:\\temp\\plate.sldprt` and export STEP."
- "Open `C:\\parts\\gearbox.sldasm`, check interference, and report the result."
- "Export `C:\\parts\\bracket.sldprt` as STL and STEP to `C:\\output\\`."

## Execution notes

- SolidWorks API lengths use meters; convert millimeter input with `mm()` first.
- `start_sketch()` supports English/Chinese reference-plane aliases; prefer `"Front Plane"`, `"Top Plane"`, or `"Right Plane"`, or their localized names.
- Before selecting a feature, face, or edge with `SelectByID2`, establish its identity and type.
- For large tasks, save `.sldprt` / `.sldasm` / `.slddrw` first and export exchange formats last.

## Completion checks

At minimum, verify:

1. `connect_solidworks()` returned a valid `sw` object.
2. Opening/creating a document returned a non-`None` model.
3. Feature calls such as `extrude_boss()` returned feature objects.
4. `save_document()` / export calls reported success.
5. Target files actually exist on disk.
6. `run_review()` exported previews and wrote `*_review_report.json`.
7. Previews match the task without blank output, wrong proportions, missing parts, wrong orientation, overlap, or floating components.

## Review example

```python
model.ForceRebuild3(False)
report, report_path = run_review(model, r"C:\temp\review", basename="result")
print(report_path)
print(report["evaluation"])
```

If the preview is wrong, revise the script and regenerate it before reporting. Saving a file alone is not completion.
