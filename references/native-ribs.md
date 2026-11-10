# 原生筋 Rib 与创建后验收

用于 L 形支架等现有相交实体壁之间的实心加强筋。优先使用
`scripts/sw_native_ribs.py`，避免复制未经验证的 COM 长参数。它补充原有零件、孔槽、圆倒角、
装配、工程图和导出接口；`sw_closed_loop` 的基础 JSON 动作白名单保持不变。

## 已验证范围

本机 **SOLIDWORKS Professional 2025 SP2.0** 已在两个独立新零件中通过：二维开放单直线草图、
双侧对称厚度、平行草图生成、无拔模，最终合并成一个实体。能力等级为 `pilot`。
曲线、多轮廓、单侧筋、垂直草图、拔模和其他版本尚不能据此宣称已验证。

以下为上游本地实机记录的相对路径。原始报告和 CAD 工件未包含在本公开仓库中，
这些路径用于说明历史记录的出处，不能作为本次安装已完成回归的证据：

```text
output/sw_skill_L_bracket_20261029/probe_01/run_report.json
output/sw_skill_L_bracket_20261029/run_01/run_report.json
output/sw_skill_L_bracket_20261029/run_01/reopened_native_validation.json
```

独立探针和完整 L 形件均创建出一个原生 `Rib`，新增体积 **8000 mm³**。
完整件回读 `Thickness=0.008 m`、`IsTwoSided=True`、`ExtrusionDirection=0`、`EnableDraft=False`；
6 个草图（含孔向导吸收草图）全部完全定义且具有参数化证据，特征错误数为零。
STEP 重导入后为单实体，包围盒 **120×80×92 mm**，体积约 **224443.161001 mm³**；
源文档状态、源文件哈希和工作目录恢复检查通过。以上是该样件证据，不是通用强度或制造认证。

## 正确的原生调用

官方接口：[IFeatureManager.InsertRib](https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeatureManager~InsertRib.html)。
它返回 **void**，参数顺序为：

```python
FeatureManager.InsertRib(
    Is2Sided, ReverseThicknessDir, Thickness, ReferenceEdgeIndex,
    ReverseMaterialDir, IsDrafted, DraftOutward, DraftAngle,
    IsNormToSketch, IsDraftedFromWall,
)
```

本次通过的取值为：

```python
FeatureManager.InsertRib(True, False, 0.008, 0, False, False, False, 0, False, False)
```

`Thickness` 为米；双侧表示以草图面为中心对称分配总厚度，8 mm 对应两侧各 4 mm。
首参 `Is2Sided` 控制厚度分配，不能误当材料生成方向。
原先的九参数调用遗漏了 `IsDraftedFromWall`，且把返回值当作 Feature，不能作为成功路径。
兼容的旧 `sw_part.rib()` 入口仍保留，新增任务优先使用带检查证据的高层入口。
旧入口的 `thickness` 仍为米；为兼容旧调用保留的 `direction` 参数实际对应 `Is2Sided`，
不是材料生成方向。其 `False` 单侧模式仍可由低层兼容接口调用，但未纳入本次实机通过范围。

## 从上下文到执行与检查

1. 只读记录当前会话、源模型上下文及源文件哈希。使用新建的任务自有零件；
   每阶段先确认文档归属，不对原模型清选、重建、保存或关闭。
2. 读取支撑壁、草图面和筋端点的真实坐标，先确认单实体及可用体积。
   草图坐标属于局部平面；从全局 XYZ 放点时使用 `ModelToSketchTransform`，不能直接混用坐标。
3. 建立开放单直线草图。退出前调用 `fully_define_active_sketch()`，
   要求 `fully_defined` 与 `parametric_evidence` 都为真；不使用整体 Fix 锁死草图。
4. 记录创建前快照与特征列表，再调用 `create_native_rib()`。例如在任务自有 `backend` 中：

   ```python
   from sw_native_ribs import create_native_rib

   backend.ensure_owned()
   result = create_native_rib(
       backend.model, sketch_name, 8,
       name="Central_Rib_T8",
       expected_added_volume_mm3=0.5 * 40 * 50 * 8,
       volume_tolerance_mm3=0.1,
   )
   # feature 为 COM 对象；其余证据可写入 JSON。
   evidence = {key: value for key, value in result.items() if key != "feature"}
   ```

   已创建的筋可只读回查，不重建或保存模型：

   ```python
   from sw_native_ribs import read_native_rib

   readback = read_native_rib(
       result["feature"], expected_thickness_mm=8, expected_two_sided=True,
   )
   ```

   回查返回 `feature_type`、`thickness_mm`、`is_two_sided`、`extrusion_direction`、
   `flip_side`、`enable_draft`、`draft_angle`，并匹配给定期望；非平行或带拔模的筋不属于此验证路径。

5. 验收本次新增的原生 `Rib`，不能只因 COM 未抛异常就判通过：
   - 新增特征唯一且 `GetTypeName2()=="Rib"`，可读取定义。
   - 回读厚度、双侧、生成方向和拔模开关，与请求匹配。
   - 重建成功，完整特征列表没有错误，实体仍为一个。
   - 体积必须增加；有解析预期值时在给定公差内匹配。
   - 递归检查全部草图，包括被筋吸收的草图，仍为完全定义并保留驱动尺寸/几何关系。
6. 失败时保留失败快照、错误与实际几何，不继续下游交付。若已经留下筋或改变实体，
   不盲目重复调用；在另一个任务自有新文档修订或返回审查。普通拉伸可作为明确说明的替代设计，
   不能以 Rib 名义记为原生筋成功。
7. 成功后沿用原保存、STEP 导出与四视图审查；独立重导入 STEP 核对实体数、体积和位置。
   重新打开新建 SLDPRT 后，再读草图与筋参数，并检查源上下文、源哈希、工作目录仍符合保护要求。

体积公式要随设计计算。上述 `0.5×40×50×8` 只适用于本样件无重叠的直角三角筋；
存在与支撑壁的重叠、圆角或其他裁切时，应核算实际新增材料，而不能硬套 8000 mm³。

## 仅更新 skill 的任务

用户只要求更新技能、并明确不动模型时，使用现有实机报告加离线自动测试验证封装与失败路径。
不要为“再测一次”连接 SW、打开、修改或保存模型。新的实机回归应是另行获准的建模任务，
并继续只操作任务自有新文档。
