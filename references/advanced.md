# Advanced feature reference

## Contents

- [Custom properties](#custom-properties)
- [Design tables and configurations](#design-tables-and-configurations)
- [Sheet metal](#sheet-metal)
- [Weldments](#weldments)
- [Surface modeling](#surface-modeling)
- [Simulation/FEA](#simulationfea)

---

## Custom properties

```python
# Get the property manager
# Empty string = file-level properties; configuration name = configuration-specific properties
props = model.Extension.CustomPropertyManager("")

# Read a property
val = ""
resolved = ""
was_resolved = False
is_linked = False
result = props.Get6("Description", False, val, resolved, was_resolved, is_linked)
# resolved contains the evaluated value

# Write or update properties
# Types: 30=text, 2=number, 11=Yes/No, 64=date
props.Add3("Description", 30, "Spindle part Rev A", 1)  # 1=overwrite
props.Add3("Material", 30, "Steel 1045", 1)
props.Add3("Weight", 2, "2.5", 1)
props.Add3("PartNumber", 30, "PN-001-001", 1)

# Delete a property
props.Delete2("OldProperty")

# Get all property names
count = props.Count
names = props.GetNames()
```

## Design tables and configurations

### Configuration management

```python
# Get all configuration names
config_names = model.GetConfigurationNames()

# Activate a configuration
model.ShowConfiguration2(configName)

# Get a configuration object
config = model.GetConfigurationByName(configName)

# Add a configuration
config_mgr = model.ConfigurationManager
new_config = config_mgr.AddConfiguration2(
    "NewConfig",    # Name
    "Description",  # Description
    "",             # Alternate name
    0,              # Options
    "",             # Parent configuration
    "",             # Description 2
    True            # Use all parameters
)

# Change a dimension in a configuration
model.ShowConfiguration2("Config1")
dim = model.Parameter("D1@Boss-Extrude1")
dim.SystemValue = 0.05  # 50 mm (units: meters)
model.EditRebuild3()
```

### Design tables

```python
# Insert a design table from Excel
design_table = model.InsertFamilyTableOpen(excelFilePath)

# Close after editing
model.CloseFamilyTable()

# Update the design table
model.InsertFamilyTableEdit()
```

## Sheet metal

### Basic operations

```python
# Create sheet-metal features through FeatureManager
# 1. Base flange
feature_mgr.InsertSheetMetalBaseFlange2(
    Thickness,    # float: sheet thickness (meters)
    BendRadius,   # float: bend radius (meters)
    ...
)

# 2. Edge flange
feature_mgr.InsertSheetMetalEdgeFlange2(...)

# 3. Miter flange
feature_mgr.InsertSheetMetalMiterFlange(...)

# 4. Unfold
feature_mgr.InsertSheetMetalFlatPattern2()

# 5. Fold
feature_mgr.InsertSheetMetalFold()
```

### Flat-pattern export

```python
# Export the flat pattern to DXF
model.ExportToDWG2(
    dxfPath,           # str: output path
    modelPath,         # str: model path (or an empty string)
    1,                 # int: export type (1=flat pattern)
    True,              # bool: show outer outline
    True,              # bool: include bend lines
    False,             # bool: sketch entities
    False,             # bool: hidden edges
    0,                 # int: bend annotations
    None               # variant: export data
)
```

### Sheet-metal parameters

```python
# Get sheet-metal feature data
feat = model.FeatureByName("Sheet-Metal1")
sheet_metal_data = feat.GetDefinition()
thickness = sheet_metal_data.Thickness    # Sheet thickness
bend_radius = sheet_metal_data.BendRadius # Bend radius
```

## Weldments

### Cut lists

```python
def get_cut_list(model):
    """Traverse the weldment cut list."""
    feat = model.FirstFeature()
    items = []
    while feat:
        if feat.GetTypeName2() == "CutListFolder":
            props = feat.CustomPropertyManager
            # Read properties
            qty_val = ""
            qty_resolved = ""
            props.Get6("QUANTITY", False, qty_val, qty_resolved, False, False)

            desc_val = ""
            desc_resolved = ""
            props.Get6("DESCRIPTION", False, desc_val, desc_resolved, False, False)

            items.append({
                "name": feat.Name,
                "quantity": qty_resolved,
                "description": desc_resolved
            })
        feat = feat.GetNextFeature()
    return items
```

### Structural members

```python
# Insert a structural member using a weldment profile
feature_mgr.InsertStructuralWeldment5(
    ProfilePath,   # str: profile file path (.sldlfp)
    ...
)
```

## Surface modeling

```python
# Extruded surface
feature_mgr.InsertExtrudedSurface(depth, flip, dir, t1, t2, d1, d2)

# Revolved surface
feature_mgr.InsertRevolvedRefSurface(...)

# Lofted surface
feature_mgr.InsertLoftRefSurface2(...)

# Swept surface
feature_mgr.InsertSweepRefSurface(...)

# Planar region
feature_mgr.InsertPlanarRefSurface()

# Trimmed surface
feature_mgr.InsertTrimSurface2(...)

# Knit surfaces
feature_mgr.InsertSewRefSurface(True, False, 0.001)

# Thicken a surface into a solid
feature_mgr.InsertThickenSheet(thickness, False, True)
```

## Simulation/FEA

> Requires the SolidWorks Simulation add-in.

```python
# Get the Simulation add-in
cos_works = sw.GetAddInObject("SldWorks.Simulation")
if not cos_works:
    print("Simulation add-in is not installed or active")

study_mgr = cos_works.StudyManager

# Create a static study
study = study_mgr.CreateStudy(
    model,
    "StaticStudy1",
    0  # 0=Static, 1=Frequency, 2=Buckling, 3=Thermal, 5=Fatigue
)

# Assign material through SolidBody
# Add restraints (Fixed, Roller/Slider, Prescribed)
# Add loads (Force, Pressure, Gravity, Torque)

# Run the analysis
study.RunAnalysis()

# Read results
results = study.Results
# Stress, displacement, factor of safety, and other results
```

### Study types

| Value | Type | Description |
|---|---|---|
| 0 | Static | Static analysis |
| 1 | Frequency | Frequency analysis |
| 2 | Buckling | Buckling analysis |
| 3 | Thermal | Thermal analysis |
| 4 | Drop Test | Drop test |
| 5 | Fatigue | Fatigue analysis |
| 6 | Nonlinear | Nonlinear analysis |
