# AutoCAD engineering practices

## Plan before drawing

- Write a brief covering units, scale, origin, layers, linetypes, text height, dimension style, output paths, and acceptance checks.
- Establish discipline-specific standards and company templates for mechanical, architectural, or electrical drawings. Without a template, use neutral layers rather than claiming standard compliance.
- Draw real dimensions at 1:1 in ModelSpace. Use Layout for borders, viewports, and plot scale.
- Choose an origin that supports positioning: mechanical parts often use a corner or center; layouts use a project datum.

## Layers and objects

- Create layers first. At minimum, distinguish `OUTLINE`, `CENTER`, `HIDDEN`, `DIM`, `TEXT`, and `CONSTRUCTION`.
- Put temporary guides on `CONSTRUCTION` and remove or freeze them as required before completion.
- Use blocks for repeated components. Keep names stable and attributes in uppercase English to reduce locale issues.
- Explicitly check external references, fonts, linetypes, and plot styles as delivery dependencies.

## Dimensions and annotations

- Derive dimensions, text, and lineweights from the standard. Without one, add necessary notes without claiming a final construction drawing.
- Dimension styles may depend on the template; confirm `DIMSTYLE` before creating COM dimensions.
- Set text height for the intended scale. Fixed ModelSpace heights may become unreadable when plotted.
- Establish mechanical-part datums, then overall dimensions, positions, and hole/slot specifications. Specifications do not establish position.
- Each cutout needs specification, position, and quantity. Display holes need diameters and datum-edge offsets; screw holes need diameter and center distance; interface cutouts need width, height, and center height; water ports need diameter, horizontal location, and both center heights.
- Use hole, slot, or combined schedules for dense layouts. Entries must map to datum dimensions in views; quantity alone or a vague drawing reference is insufficient.
- Leaders are for short notes, not key dimensions. Do not cross other views, holes, centerlines, dimension text, or title blocks.

## Chinese mechanical drafting conventions

For GB/T-style, strict-standard, or Chinese mechanical drafting requests, check:

- Sheet/border: common A3 landscape size `420×297`, left binding margin `25`, other margins `5`, and lower-right title block with common width `180`.
- Fonts: prefer FangSong for Chinese text and consistent typography for requirements, title blocks, view names, and hole/slot tables.
- Layers/linetypes: separate thick/thin continuous, centerline, hidden-line, dimension, text, border, and cutout/section layers. Centerlines and hidden lines must not be ordinary solid lines.
- Dimensions: use native entities such as `AcDbRotatedDimension`, not ordinary lines/text assembled to resemble dimensions.
- Cutouts: enclosure drawings need overall dimensions, wall/floor thickness, and specifications/positions for screen cutouts, interfaces, water ports, vents, screw holes, and bosses.
- Layout: dimensions, text, and tables must not enter the title block or cover main views. Move views or split tables if needed.

Examples of incomplete drawings:

- `4× screw bosses φ8, pilot holes φ2.6` without center distances and edge offsets cannot define machining positions.
- `7×4×30 grille` without the group center, first-slot position, or pitch cannot locate the slots.
- `2× water-port through holes φ13.5` without horizontal positions and both center heights cannot locate the holes.
- A long leader crossing centerlines, hole outlines, or other views resembles unwanted guides. Replace it with dimensions or a hole/slot schedule.

## Automation code

- Centralize dimensions at the script top or in the JSON brief.
- Check COM results, then output existence and size after save/export.
- Prefer the object model. Use `SendCommand` for missing APIs, existing commands, or legacy workflows.
- `SendCommand` may be asynchronous. Wait, save, and inspect rather than checking only that it was sent.
- SelectionSet names persist; delete a same-name set before replacement.
- A bad drawing should not abort a batch. Record the failed file and stage.

## Review approach

Minimum checks:

- Files exist and sizes are reasonable.
- Entity counts/types match the brief.
- Expected objects occupy the correct layers.
- Overall bounds match the intended order of magnitude.
- Main geometry is visible after `ZoomExtents`.

Higher-risk checks:

- Missing text, attributes, external references, linetypes, or fonts.
- DXF/PDF consistency with DWG.
- Sheet scale, plotter, CTB/STB, orientation, and margins.
- Whether batch edits overwrote originals.

## Practical judgment

- Establish repeatability and correctness before visual polish.
- DWG is a structured database; screenshots alone cannot prove properties, layers, or block references.
- Prefer .NET for complex plugins instead of hundreds of business-logic lines in `SendCommand` strings.
- Upgrades affect target frameworks, ObjectARX SDK, and plugin loading. Live-test each major version.
- LT, education/network licenses, or sessions without desktops may restrict automation. Check the environment first when behavior is unexpected.
