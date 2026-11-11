# Examples

This directory contains SolidWorks automation examples, progressing from basic parts to more advanced workflows.

## Example list

### 01_basic_part.py

Create a basic cylindrical part.

**Topics:**

- Connect to SolidWorks
- Create a part document
- Sketch a circle
- Extrude a feature
- Save the file

**Prerequisites:**

- SolidWorks is running
- `C:\temp\` exists

---

### 02_complex_part.py

Create a rectangular plate with holes.

**Topics:**

- Multiple sketches and features
- Extruded cuts for holes
- Chamfers and fillets
- Face selection

**Prerequisites:**

- SolidWorks is running

---

### 03_assembly.py

Create an assembly.

**Topics:**

- Insert components
- Coincident and concentric mates
- List components

**Prerequisites:**

- Prepare two part files:
  - `C:\parts\base.sldprt`
  - `C:\parts\shaft.sldprt`
- Alternatively, adjust the paths in the script

---

### 04_batch_export.py

Export files in a batch.

**Topics:**

- Batch file processing
- STEP export
- Error handling

**Prerequisites:**

- `.sldprt` files in `C:\parts\`
- Alternatively, adjust the paths in the script

---

### 05_drawing.py

Create a drawing.

**Topics:**

- Create a drawing document
- Standard three-view drawing
- Automatic dimensions
- Notes
- PDF export

**Prerequisites:**

- A part file at `C:\parts\mypart.sldprt`
- Alternatively, adjust the path in the script

---

### 06_friendly_api.py

Create and export a part through the `SolidWorksSession` API.

**Topics:**

- Create, save, and export with `SolidWorksSession`
- Enter and exit sketches with `with sketch(...)`
- Reduce hard-coded sketch names and repeated path handling

**Prerequisites:**

- SolidWorks is running, or the script may launch it
- `C:\temp\` is writable

---

### 07_motion_study_rotary_motor.py

Add a Motion Study rotary motor to an existing fan assembly.

**Topics:**

- Create and activate a Motion Study
- Load the Motion Study type library
- Add a constant-speed 60RPM motor using shaft or impeller cylindrical faces
- Calculate and play the study

**Prerequisites:**

- An existing fan assembly
- The impeller's concentric mate allows rotation and its component is not fixed
- Adjust `assembly_path` and the component-name keywords in the script

---

### 08_mini_fan_motion_assembly.py

Generate a desktop mini-fan benchmark assembly.

**Topics:**

- Create four parts: base, center post, bladed impeller, and circular front guard
- Create an assembly and insert the components
- Add coincident and concentric mates, leaving impeller rotation unlocked
- Fix the base, post, and guard while leaving the impeller floating
- Create a Motion Study and add a constant-speed 60RPM rotary motor
- Export a review report

**Prerequisites:**

- SolidWorks is running, or the script may launch it
- `C:\temp\solidworks_mini_fan_demo\` is writable

**Notes:**

- This is a stability benchmark, not a finished appearance model.
- Fillets and chamfers are not acceptance criteria. Automatic edge selection varies by version and language; improve that selection strategy separately.

---

### 09_xy_stage_visual_demo.py

Build the independent 226-component XY positioning stage shown on the repository homepage. Geometry is generated with OCCT/OCP, exported as a colored STEP assembly, then imported and previewed in SolidWorks. This static visual example is separate from the unified executor's part benchmark.

Run from the repository root with a new output directory. Install `requirements-occt.txt` as well as the regular dependencies; preview rendering also requires Pillow and an open, licensed SolidWorks session. See [SHOWCASE.md](../docs/SHOWCASE.md) for commands, provenance, and the recorded checks.

---

## Run an example

1. Install the dependencies:

```bash
pip install pywin32
```

2. Start SolidWorks.
3. Run the example:

```bash
python 01_basic_part.py
```

## Adjust paths

Change the file paths to match your environment:

```python
# Input path
part_path = r"C:\your\path\part.sldprt"

# Output path
output_path = r"C:\your\output\file.step"
```

## Troubleshooting

### Cannot connect to SolidWorks

Check that SolidWorks is running and Python has the same architecture, usually 64-bit.

### Reference plane not found

English and Chinese installations use different plane names:

- English: "Front Plane", "Top Plane", "Right Plane"
- Chinese object-name literals: `"前视基准面"`, `"上视基准面"`, `"右视基准面"`

These Chinese strings are native selection names and must match the installed interface language.

### Feature creation fails

Check:

1. The sketch is closed.
2. Units are correct; use `mm()`.
3. The intended entities are selected.

For more details, read [troubleshooting.md](../references/troubleshooting.md).
