# 复杂孔槽自动化

## 支持范围

`scripts/sw_hole_features.py` 使用草图和切除特征创建以下结构：

- 定深盲孔。
- 完全贯穿孔。
- 通孔 + 圆柱沉孔的两级复合孔。
- 通孔 + 指定包含角的锥形沉头孔。
- 两端为半圆的直槽，支持贯穿或定深。
- 按显式坐标创建的孔阵列。

`sw_hole_features.py` 保留以上几何孔接口。另有 `sw_native_holes.py` 的
`create_native_counterbore(model, position_mm, hole_diameter_mm, counterbore_diameter_mm, counterbore_depth_mm, name=...)`
使用真实 `HoleWizard5`，已在 SW2025 的 ISO/M8 圆柱沉孔上进行实测。标准紧固沉孔优先走原生接口，
而不是把两次切除称为孔向导特征；其他尚未验证的孔向导类型不得凭记忆拼接长参数。

原生接口回读 `HoleWzd`、Type14、`ThruHoleDiameter`、`CounterBoreDiameter`、
`CounterBoreDepth`、贯穿条件、ISO 标准和实际二维定位坐标。其返回值仅 `feature` 字段是 COM 句柄，
其他字段可写入 JSON。孔定位子草图需在退出前用 `sw_sketch_constraints` 补足尺寸和约束，
并在最终审查中确认状态3。自动生成的孔向导轮廓由原生特征参数控制，不删掉其合法内部锚点。
两个接口的单位不同：原生新接口使用 mm，原几何接口仍使用米。

同规格多孔使用 `create_native_counterbore_group(model, positions_mm, hole_diameter_mm,
counterbore_diameter_mm, counterbore_depth_mm, name=...)`。它只创建一个 `HoleWzd`，
在该特征的同一个二维位置草图中添加所有定位点，并补齐尺寸和关系。模型坐标先经
`ModelToSketchTransform` 转为草图坐标；退出后按逆变换回读全部点，核对数量、孔位和完全定义状态。
输入位置必须互不重复且属于同一平面面片。不同规格或不同支承面应建立独立特征。

## 单位与基准

- 所有输入长度使用米，建议由 `sw_connect.mm()` 转换。
- `center`、`start`、`end` 是目标草图平面的局部二维坐标。
- 默认基准面是 `Front Plane`，中文版由 `sw_part.start_sketch()` 自动兼容。
- 创建参数证据同时输出米和毫米字段，但毫米字段只用于报告，不回传 COM。

## 示例

```python
from sw_connect import mm
from sw_hole_features import (
    create_blind_hole,
    create_counterbore_hole,
    create_countersink_hole,
    create_semicircular_slot,
)

blind = create_blind_hole(model, (mm(20), mm(20)), mm(8), mm(10), name="H1_盲孔")
counterbore = create_counterbore_hole(
    model,
    (mm(50), mm(20)),
    hole_diameter=mm(6),
    counterbore_diameter=mm(12),
    counterbore_depth=mm(4),
    name="H2_沉孔",
)
countersink = create_countersink_hole(
    model,
    (mm(80), mm(20)),
    hole_diameter=mm(5),
    countersink_diameter=mm(10),
    included_angle_deg=90,
    name="H3_沉头",
)
slot = create_semicircular_slot(
    model,
    (mm(30), mm(50)),
    (mm(60), mm(50)),
    width=mm(10),
    depth=0,
    name="S1_半圆端槽",
)
```

## 验收证据

创建函数返回的是参数证据，不是几何验收结论。交付前必须继续执行：

1. `sw_review.collect_geometry_measurements()` 读取 B-Rep 圆柱面。
2. `sw_review.validate_hole_positions()` 验证孔径和孔轴线位置。
3. 对盲孔深度、沉孔深度和沉头角度回读特征参数，或用剖视图人工复核。
4. 半圆槽端部圆柱面必须进入 `slot_arc_candidates`，不能被计入圆孔数量。
5. 复合孔应在 `compound_holes` 中出现同轴多直径孔段。

推荐每个孔至少记录：孔型、规格、数量、基准边定位、中心距、深度/贯穿状态、尺寸公差和证据来源。

## 已知限制

- 锥形沉头使用通孔入口圆边的角度/距离倒角。入口边按圆心、半径和基准面位置筛选，不依赖临时边线名称；倒角后仍必须查看剖视图确认入口方向。
- B-Rep 单独不能可靠区分盲孔和通孔；必须与创建参数或特征定义回读交叉验证。
- 当前孔阵列按显式孔位逐个建特征，优先保证可审计性；大量规则阵列后续可增加 Linear/Circular Pattern 封装。
