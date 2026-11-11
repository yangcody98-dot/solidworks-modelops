# SolidWorks Fillet Chamfer CNC

`solidworks-fillet-chamfer-cnc` is the CNC fillet and chamfer subskill from the `solidworks-automation` repository. It provides a repeatable workflow for machined parts with multiple fillets, chamfers, holes, slots, lightening pockets, and STEP output.

## Use cases

- CNC aluminum mounts, connector blocks, brackets, base plates, and counterbored mounting plates.
- Large outer-profile fillets, top and bottom edge chamfers, and hole-mouth chamfers.
- Lightening pockets, obround slots, counterbores, and locating holes.
- Reliable edge selection, STEP export, and review from multiple views.

## Core principles

Topology, edge selection, and feature order are the main challenges:

1. Start with simple base geometry.
2. Place large fillets and outer-edge chamfers before hole and slot cuts where possible.
3. Add holes, slots, and pockets after finishing the main body's edges.
4. Add small hole-mouth chamfers last.
5. Prefer `edge.Select2()` over `Edge1` names or coordinate picks.
6. Run `sw_review.run_review()`.

## Quick command

Run from the repository root:

```powershell
py subskills\solidworks-fillet-chamfer-cnc\scripts\create_cnc_mount_template.py `
  --output-dir C:\CADAutomationWorkbench\solidworks_fillet_chamfer_output
```

## Layout

```text
solidworks-fillet-chamfer-cnc/
├── SKILL.md
├── README.md
├── manifest.yaml
├── agents/
├── references/
│   └── cnc-fillet-chamfer-lessons.md
└── scripts/
    └── create_cnc_mount_template.py
```

## Related capabilities

- Parent skill: `solidworks-automation`
- Upstream planning: `solidworks-vibecad`
- For models containing threaded holes, also use `solidworks-threaded-holes`.
