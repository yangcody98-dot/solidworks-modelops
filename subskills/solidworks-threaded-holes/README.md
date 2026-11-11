# SolidWorks Threaded Holes

`solidworks-threaded-holes` is the threaded-hole subskill from the `solidworks-automation` repository. It generates reviewable tap-drill holes, thread representations, mouth chamfers, thread metadata, and STEP output.

## Use cases

- M3/M4/M5/M6/M8/M10/M12 internal threaded holes.
- Blind holes, through holes, tapped holes, and threaded mounting holes.
- Hole Wizard, ThreadFeatureData, CosmeticThread, or visible 3D helix representations.
- Delivery of `SLDPRT + STEP + parameters_json + review_report_json + preview`.

## Core principles

Native Thread creation through SolidWorks COM can vary by version and interface language. Use layered delivery:

1. Create correct tap-drill geometry.
2. Create the correct mouth chamfer.
3. Attempt a native Thread feature.
4. If it fails, attempt CosmeticThread.
5. If that remains unreliable, keep a visible 3D helix and custom properties to record the thread intent.
6. Run `sw_review.run_review()`.

## Quick command

Run from the repository root:

```powershell
py subskills\solidworks-threaded-holes\scripts\create_threaded_hole_template.py `
  --thread M6 `
  --output-dir C:\CADAutomationWorkbench\solidworks_threaded_hole_output
```

## Layout

```text
solidworks-threaded-holes/
├── SKILL.md
├── README.md
├── manifest.yaml
├── agents/
├── references/
│   └── threaded-hole-lessons.md
└── scripts/
    └── create_threaded_hole_template.py
```

## Related capabilities

- Parent skill: `solidworks-automation`
- Upstream planning: `solidworks-vibecad`
- For threaded holes in a complex CNC mount, also use `solidworks-fillet-chamfer-cnc`.
