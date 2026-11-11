# AutoCAD API verification

## Official source priority

1. Autodesk AutoCAD API overview: ObjectARX, Managed .NET, Visual LISP, and ActiveX environments.
   - https://aps.autodesk.com/developer/overview/autocad-api
2. AutoCAD Developer and ObjectARX Help: Managed .NET, ActiveX/VBA, DXF Reference, AutoLISP, and Core Console.
   - https://help.autodesk.com/view/OARX/2027/ENU/
3. Managed .NET Developer's Guide: C# plugins, transactions, document locks, entities, dimensions, layouts, and plotting.
   - https://help.autodesk.com/view/OARX/2027/ENU/?guid=GUID-C3F3C736-40CF-44A0-9210-55F6A939B6F2
4. ObjectARX SDK: C++/C# extensions, database structures, graphics, and native commands.
   - https://aps.autodesk.com/developer/overview/objectarx-autocad-sdk
5. APS Design Automation: cloud DWG batch processing without a desktop.
   - https://aps.autodesk.com/en/docs/design-automation/v3

## GitHub references

- ADN-DevTech `acad-api-skill`: rules for agents generating AutoCAD/Civil 3D/Plant 3D .NET plugins.
  - https://github.com/ADN-DevTech/acad-api-skill
- ADN-DevTech `autocad-automation-apps`: AutoLISP, C++ CRX, and .NET bundle examples for APS Design Automation.
  - https://github.com/ADN-DevTech/autocad-automation-apps
- `reclosedev/pyautocad`: Python ActiveX wrappers with coordinate, object-iteration, and lightweight API patterns.
  - https://github.com/reclosedev/pyautocad
- AutoCAD .NET Wizards: Visual Studio templates for AutoCAD .NET projects.
  - https://github.com/ADN-DevTech/AutoCAD-Net-Wizards

## Verification workflow

1. Choose COM/ActiveX, AutoLISP/SCR, .NET, ObjectARX, or APS.
2. Search exact names, such as `ModelSpace AddLine ActiveX AutoCAD` or `DocumentLock AutoCAD .NET`.
3. Read target-version documentation and record the signature, argument types, units, return value, exceptions, and version limits.
4. Prefer official Autodesk/ADN examples. Learn patterns from third parties rather than copying directly.
5. Run a minimal test, save its output, and review it with `acad_review.py`.
6. If documentation and behavior differ, record the version, language, error code, and workaround in `troubleshooting.md`.

## Common COM/ActiveX objects

- `AutoCAD.Application`: entry point; exposes `Visible`, `Documents`, and `ActiveDocument`.
- `Document`: drawing, including `ModelSpace`, `PaperSpace`, `Layers`, `Blocks`, `SelectionSets`, `SaveAs`, and `SendCommand`.
- `ModelSpace`: creates lines, circles, polylines, text, and dimensions.
- `Layer`: color, linetype, and visibility.
- `AcadEntity`: common properties including `Layer` and `Color`; most entities support `GetBoundingBox`.

## Common methods to verify

- Line: `ModelSpace.AddLine(startPoint, endPoint)`
- Circle: `ModelSpace.AddCircle(centerPoint, radius)`
- Lightweight polyline: `ModelSpace.AddLightWeightPolyline(points2d)`
- Text: `ModelSpace.AddText(text, insertionPoint, height)`
- Multiline text: `ModelSpace.AddMText(insertionPoint, width, text)`
- Save: `Document.SaveAs(path)`
- Command: `Document.SendCommand(command)`
- View: `Application.ZoomExtents()`

Behavior may differ across versions, language packs, and LT/full editions. Do not promise advanced objects or formats before testing.

## .NET plugin route

Use .NET when COM is hard to maintain or the task needs transactions, document locks, selection filters, command registration, panels, or events:

1. Match the target framework and SDK references to the AutoCAD version.
2. Use `CommandMethod` for command entry points.
3. Make database changes inside transactions and lock the active document correctly.
4. Load the DLL with `NETLOAD` or a debugging configuration.
5. Once it works, consider a bundle or APS Design Automation activity.

## Source-use requirements

- Do not guess enums, save types, plot settings, or command arguments from memory.
- Use forums to identify terms and symptoms, then verify important details officially.
- Do not copy code with an unclear license into the user's project.
- Distinguish cloud APS from local AutoCAD COM. Local COM scripts do not automatically run in CI.
