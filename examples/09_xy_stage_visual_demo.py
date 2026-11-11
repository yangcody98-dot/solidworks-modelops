"""Build an independent, colored STEP assembly for a genuine SolidWorks preview.

This is a static visualization example, separate from the v0.1 transaction
benchmark. Generic motors, bearings and grooved shafts are illustrative
envelopes; no load, motion, fit or manufacturing certification is claimed.
Requires the optional OCP dependencies in requirements-occt.txt. Rendering
additionally requires an open, licensed SolidWorks session and COM packages.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def build(out_dir):
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Fuse
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakePrism
    from OCP.GProp import GProp_GProps
    from OCP.gp import gp_Ax1, gp_Ax2, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.STEPCAFControl import STEPCAFControl_Writer
    from OCP.STEPControl import STEPControl_AsIs
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopLoc import TopLoc_Location
    from OCP.XCAFDoc import XCAFDoc_ColorGen, XCAFDoc_DocumentTool

    output = Path(out_dir).resolve()
    output.mkdir(parents=True, exist_ok=False)

    def box(w, d, h):
        return BRepPrimAPI_MakeBox(gp_Pnt(-w/2, -d/2, 0), w, d, h).Shape()

    def cylinder(radius, height, x=0, y=0, z=0):
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(x, y, z), gp_Dir(0, 0, 1)), radius, height).Shape()

    def cut(shape, tool):
        operation = BRepAlgoAPI_Cut(shape, tool)
        if not operation.IsDone():
            raise RuntimeError("Demo boolean cut failed")
        return operation.Shape()

    def fuse(a, b):
        operation = BRepAlgoAPI_Fuse(a, b)
        if not operation.IsDone():
            raise RuntimeError("Demo boolean union failed")
        return operation.Shape()

    def move(shape, x=0, y=0, z=0, axis=None, angle=0):
        if axis:
            rotation = gp_Trsf()
            rotation.SetRotation(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(*axis)), math.radians(angle))
            shape = shape.Moved(TopLoc_Location(rotation))
        shift = gp_Trsf()
        shift.SetTranslation(gp_Vec(x, y, z))
        return shape.Moved(TopLoc_Location(shift))

    def plate(w, d, h, holes=(), window=None):
        shape = box(w, d, h)
        if window:
            shape = cut(shape, move(box(*window, h+2), z=-1))
        for x, y, radius in holes:
            shape = cut(shape, cylinder(radius, h+2, x, y, -1))
            shape = cut(shape, cylinder(radius+2, 3, x, y, h-2.5))
        return shape

    def bolt():
        shape = fuse(cylinder(2.5, 10, z=-10), cylinder(4.25, 5))
        polygon = BRepBuilderAPI_MakePolygon()
        for i in range(6):
            polygon.Add(gp_Pnt(2.2*math.cos(i*math.pi/3), 2.2*math.sin(i*math.pi/3), 2))
        polygon.Close()
        socket = BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeFace(polygon.Wire()).Face(), gp_Vec(0, 0, 4)).Shape()
        return cut(shape, socket)

    def rail(length):
        shape = fuse(box(length, 15, 10), move(box(length, 9, 4), z=10))
        for x in range(-int(length/2)+18, int(length/2)-8, 32):
            shape = cut(shape, cylinder(2.3, 16, x, 0, -1))
            shape = cut(shape, cylinder(4, 4, x, 0, 11))
        return shape

    def grooved_shaft(length):
        shape = cylinder(4.4, length)
        for i in range(6, int(length)-6, 6):
            shape = fuse(shape, cylinder(5.1, 1.0, z=i))
        return shape

    def motor():
        core = box(40, 40, 46)
        for z in range(4, 44, 5):
            core = fuse(core, move(box(46, 46, 1.6), z=z))
        return core

    dark = (0.28, 0.34, 0.40)
    silver = (0.71, 0.75, 0.79)
    steel = (0.56, 0.60, 0.65)
    blue = (0.18, 0.40, 0.60)
    black = (0.09, 0.10, 0.12)
    bronze = (0.69, 0.48, 0.22)
    orange = (0.84, 0.31, 0.12)
    mount_holes = [(x, y, 3.3) for x in (-140, 140) for y in (-95, 0, 95)]
    carriage_holes = [(x, y, 2.3) for x in (-12, 12) for y in (-10, 10)]
    tabletop_holes = [(x, y, 2.8) for x in (-55, 0, 55) for y in (-55, 55)]
    table = plate(150, 150, 14, tabletop_holes, (65, 65))
    for y in (-40, 40):
        table = cut(table, move(box(95, 5, 5), y=y, z=11))

    prototypes = {
        "base": (plate(320, 250, 16, mount_holes, (145, 82)), dark),
        "x_rail": (rail(270), steel),
        "y_rail": (rail(175), steel),
        "carriage": (plate(36, 32, 18, carriage_holes), blue),
        "carriage_cap": (plate(40, 34, 3, carriage_holes), silver),
        "middle_plate": (plate(220, 190, 14, [(x, y, 2.8) for x in (-75, 75) for y in (-75, 75)], (105, 80)), silver),
        "top_plate": (table, (0.62, 0.67, 0.72)),
        "bearing": (cut(box(28, 34, 28), move(cylinder(5.5, 36), y=18, z=15, axis=(1, 0, 0), angle=90)), blue),
        "bearing_foot": (plate(40, 48, 6, [(x, y, 2.8) for x in (-14, 14) for y in (-17, 17)]), silver),
        "motor": (motor(), black),
        "motor_flange": (plate(48, 48, 5, [(x, y, 2.3) for x in (-18, 18) for y in (-18, 18)]), silver),
        "motor_hub": (cylinder(12, 4), silver),
        "coupling": (cut(cylinder(10, 22), cylinder(3.2, 24, z=-1)), silver),
        "screw_x": (grooved_shaft(242), silver),
        "screw_y": (grooved_shaft(180), silver),
        "nut": (cut(cylinder(11, 20), cylinder(5.2, 22, z=-1)), bronze),
        "end_cap": (box(16, 20, 3), black),
        "bolt": (bolt(), black),
        "washer": (cut(cylinder(5, 1.2), cylinder(2.7, 3, z=-1)), steel),
        "foot": (cut(cylinder(12, 10), cylinder(3.2, 12, z=-1)), black),
        "datum_strip": (box(205, 3, 2), orange),
    }
    prototype_checks = []
    for name, (shape, _) in prototypes.items():
        properties = GProp_GProps()
        BRepGProp.VolumeProperties_s(shape, properties)
        valid = BRepCheck_Analyzer(shape).IsValid()
        volume = properties.Mass()
        if not valid or not math.isfinite(volume) or volume <= 0:
            raise RuntimeError(f"Invalid positive-volume prototype: {name}")
        prototype_checks.append({"name": name, "valid": valid, "volume_mm3": volume})

    placements = []
    def add(kind, x=0, y=0, z=0, axis=None, angle=0):
        placements.append({"kind": kind, "xyz_mm": [x, y, z], "axis": axis, "angle_deg": angle})
    def fasteners(points, z):
        for x, y in points:
            add("washer", x, y, z)
            add("bolt", x, y, z+1.2)
    add("base")
    fasteners([(x, y) for x, y, _ in mount_holes], 13.5)
    for x in (-135, 135):
        for y in (-90, 90):
            add("foot", x, y, -10)
    for y in (-75, 75):
        add("x_rail", 0, y, 16)
        fasteners([(x, y) for x in range(-117, 118, 32)], 27)
        for x in (-65, 65):
            add("carriage", x, y, 30)
            add("carriage_cap", x, y, 48)
            fasteners([(x+dx, y+dy) for dx in (-12, 12) for dy in (-10, 10)], 51)
    add("middle_plate", 0, 0, 51)
    for x in (-65, 65):
        add("y_rail", x, 0, 65, (0, 0, 1), 90)
        fasteners([(x, y) for y in range(-69, 70, 32)], 76)
        for y in (-48, 48):
            add("carriage", x, y, 79)
            add("carriage_cap", x, y, 97)
            fasteners([(x+dx, y+dy) for dx in (-12, 12) for dy in (-10, 10)], 100)
    add("top_plate", 0, 0, 100)
    fasteners([(x, y) for x, y, _ in tabletop_holes], 111.5)
    # Axis X: the local Z shaft direction rotates onto X.
    add("screw_x", -121, 0, 38, (0, 1, 0), 90)
    add("nut", -10, 0, 38, (0, 1, 0), 90)
    for x in (-122, 122):
        add("bearing_foot", x, 0, 16)
        add("bearing", x, 0, 23, (0, 0, 1), 90)
        fasteners([(x+dx, dy) for dx in (-14, 14) for dy in (-17, 17)], 22)
    add("coupling", -152, 0, 38, (0, 1, 0), 90)
    add("motor", -203, 0, 38, (0, 1, 0), 90)
    add("motor_flange", -157, 0, 38, (0, 1, 0), 90)
    add("motor_flange", -208, 0, 38, (0, 1, 0), 90)
    add("motor_hub", -152, 0, 38, (0, 1, 0), 90)
    # Axis Y: local Z rotates onto positive Y.
    add("screw_y", 0, -90, 87, (1, 0, 0), -90)
    add("nut", 0, -10, 87, (1, 0, 0), -90)
    for y in (-91, 91):
        add("bearing_foot", 0, y, 65, (0, 0, 1), 90)
        add("bearing", 0, y, 72)
        fasteners([(dx, y+dy) for dx in (-17, 17) for dy in (-14, 14)], 71)
    add("coupling", 0, -122, 87, (1, 0, 0), -90)
    add("motor", 0, -173, 87, (1, 0, 0), -90)
    add("motor_flange", 0, -127, 87, (1, 0, 0), -90)
    add("motor_flange", 0, -178, 87, (1, 0, 0), -90)
    add("motor_hub", 0, -122, 87, (1, 0, 0), -90)
    add("datum_strip", 0, -101, 65)
    for x in (-142, 142):
        for y in (-75, 75):
            add("end_cap", x, y, 16)

    document = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    colors = XCAFDoc_DocumentTool.ColorTool_s(document.Main())
    root_label = tool.NewShape()
    TDataStd_Name.Set_s(root_label, TCollection_ExtendedString("ModelOps_XY_Stage_Demo"))
    occurrences = Counter()
    for placement in placements:
        kind = placement["kind"]
        shape, color = prototypes[kind]
        shape = move(shape, *placement["xyz_mm"], placement["axis"], placement["angle_deg"])
        # SolidWorks is Y-up; rotate the complete Z-up demo as a rigid whole.
        shape = move(shape, axis=(1, 0, 0), angle=-90)
        label = tool.AddShape(shape, False)
        occurrences[kind] += 1
        name = f"MO_{kind}_{occurrences[kind]:03d}"
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(name))
        colors.SetColor(label, Quantity_Color(*color, Quantity_TOC_RGB), XCAFDoc_ColorGen)
        component = tool.AddComponent(root_label, label, TopLoc_Location())
        TDataStd_Name.Set_s(component, TCollection_ExtendedString(name))
    tool.UpdateAssemblies()
    path = output / "ModelOps_XY_Stage_Demo.step"
    writer = STEPCAFControl_Writer()
    writer.SetColorMode(True)
    writer.SetNameMode(True)
    if not writer.Transfer(document, STEPControl_AsIs) or writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError("Colored STEP assembly export failed")
    report = {"purpose": "independent static assembly visualization", "modeling_backend": "OCCT/OCP",
              "component_count": len(placements), "prototype_checks": prototype_checks,
              "component_groups": dict(occurrences), "step_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
              "component_colors": {name: list(color) for name, (_, color) in prototypes.items()},
              "step_bytes": path.stat().st_size,
              "limitations": ["Generic component envelopes, not supplier models", "No load/motion/fit validation",
                              "Separate from the basic-part ModelOps v0.1 benchmark"]}
    (output / "demo_geometry_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
    return path, report


def render_in_solidworks(path):
    from PIL import Image
    import sw_closed_loop_native as native
    from sw_appearance import set_component_appearance
    from sw_model_context import capture_document_state
    path = Path(path).resolve()
    output = path.parent
    geometry = json.loads((output / "demo_geometry_report.json").read_text(encoding="utf-8"))
    report = {"preview_backend": "SolidWorks", "status": "failed"}
    with native._execution_lock():
        sw = native._attach()
        c, _, review, _ = native._helpers()
        original = c.get_com_member(sw, "ActiveDoc")
        original_identity = native._document_identity(original) if original is not None else None
        before = capture_document_state(original) if original is not None else None
        initial = list(c.get_com_member(sw, "GetDocuments") or [])
        original_identities = [native._document_identity(m) for m in initial]
        previous_directory = c.get_com_member(sw, "GetCurrentWorkingDirectory")
        model = None
        owned = False
        try:
            if not c.get_com_member(sw, "SetCurrentWorkingDirectory", str(output)):
                raise RuntimeError("Cannot isolate STEP import directory")
            data = sw.GetImportFileData(str(path))
            errors = c.VARIANT(c.pythoncom.VT_BYREF | c.pythoncom.VT_I4, 0)
            model = sw.LoadFile4(str(path), "r", data, errors)
            if model is None or native._document_identity(model) in original_identities:
                raise RuntimeError("STEP import did not create an independent document")
            owned = True
            report["solidworks_revision"] = str(c.get_com_member(sw, "RevisionNumber"))
            report["document_type"] = c.get_com_member(model, "GetType")
            if report["document_type"] != 2:
                raise RuntimeError("STEP must import as an assembly; check SolidWorks import settings")
            components = list(c.get_com_member(model, "GetComponents", False) or [])
            report["imported_components"] = len(components)
            if not components or len(components) != geometry["component_count"]:
                raise RuntimeError("Imported component count does not match the generated assembly")
            palette = geometry["component_colors"]
            color_checks = []
            for component in components:
                name = str(c.get_com_member(component, "Name2")).lower()
                kind = next((k for k in sorted(palette, key=len, reverse=True) if f"mo_{k}_" in name), None)
                if kind is None:
                    raise RuntimeError(f"Unrecognized imported demo component: {name}")
                color_checks.append(set_component_appearance(component, palette[kind]))
            report["appearance_readback_verified"] = all(color_checks)
            if not report["appearance_readback_verified"]:
                raise RuntimeError("SolidWorks component color readback failed")
            model.ForceRebuild3(False)
            audit, audit_path = review.run_review(model, str(output / "review"), basename="xy_stage",
                                                expected_outputs=[str(path)])
            required_checks = ("model_available", "previews_created", "previews_not_blank", "expected_outputs_exist")
            if (audit.get("evaluation", {}).get("status") not in {"pass", "warn"}
                    or not all(audit["checks"].get(k) is True for k in required_checks)):
                raise RuntimeError("Native assembly preview checks failed")
            bmp = review.save_preview(model, output / "xy-stage-hero.bmp", width=2560, height=1440)
            hero_check = review.inspect_bmp_preview(bmp)
            if (hero_check["likely_blank"] or hero_check.get("error")
                    or (hero_check["width"], hero_check["height"]) != (2560, 1440)):
                raise RuntimeError("Native hero preview is blank, unreadable, or has unexpected dimensions")
            png = output / "xy-stage-hero.png"
            with Image.open(bmp) as raster:
                raster.save(png)
            report.update(status="passed", image=str(png), review_report=str(audit_path),
                          preview_checks=audit["checks"], hero_not_blank=True,
                          image_sha256=hashlib.sha256(png.read_bytes()).hexdigest())
        except Exception as exc:
            report.update(status="failed", error=str(exc))
            raise
        finally:
            cleanup_errors = []
            try:
                if owned:
                    identity = native._document_identity(model)
                    title = c.get_com_member(model, "GetTitle")
                    matches = [m for m in (c.get_com_member(sw, "GetDocuments") or [])
                               if c.get_com_member(m, "GetTitle") == title]
                    if len(matches) != 1 or native._document_identity(matches[0]) != identity:
                        raise RuntimeError("Preview cleanup identity is ambiguous")
                    sw.CloseDoc(title)
                    if identity in [native._document_identity(m) for m in (c.get_com_member(sw, "GetDocuments") or [])]:
                        raise RuntimeError("Imported demo document remained open after cleanup")
            except Exception as exc:
                cleanup_errors.append(f"Close demo: {exc}")
            try:
                native._restore_active(sw, before["document"] if before else None)
                active = c.get_com_member(sw, "ActiveDoc")
                active_identity = native._document_identity(active) if active is not None else None
                report["original_active_identity_restored"] = active_identity == original_identity
                report["original_active_document_unchanged"] = before == (capture_document_state(original) if original is not None else None)
                if not report["original_active_identity_restored"] or not report["original_active_document_unchanged"]:
                    raise RuntimeError("Original active document identity or captured state changed")
            except Exception as exc:
                cleanup_errors.append(f"Restore active document: {exc}")
            try:
                if not c.get_com_member(sw, "SetCurrentWorkingDirectory", previous_directory):
                    raise RuntimeError("Could not restore the SolidWorks working directory")
                report["working_directory_restored"] = c.get_com_member(sw, "GetCurrentWorkingDirectory") == previous_directory
                if not report["working_directory_restored"]:
                    raise RuntimeError("Working directory readback did not match")
            except Exception as exc:
                cleanup_errors.append(f"Restore working directory: {exc}")
            if cleanup_errors:
                report.update(status="failed", cleanup_errors=cleanup_errors)
            (output / "demo_solidworks_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8", newline="\n")
            if cleanup_errors:
                raise RuntimeError("; ".join(cleanup_errors))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--step-only", action="store_true")
    args = parser.parse_args()
    step, geometry = build(args.out_dir)
    result = {"step": str(step), "components": geometry["component_count"]}
    if not args.step_only:
        result.update(render_in_solidworks(step))
    print(json.dumps(result))
