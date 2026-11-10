---
name: solidworks-modelops
description: SolidWorks 参数化建模、命名尺寸修改、检查点恢复与同题回归验证。用于在任务副本中创建或修改零件，测量真实几何、核对草图约束并交付原生文件和STEP；其他机械专项按需调用随包模块。
---

# SolidWorks ModelOps

用一个 JSON 接口贯通需求计划、原生建模、改尺寸、检查点与验收。当前统一执行器为 **pilot**，
仅覆盖基础零件；随包保留的专项能力不自动成为统一事务接口的一部分。

## 入口

先运行 `python scripts/sw_preflight.py`。原生操作需要 Windows、Python COM 依赖，以及已打开且有合法许可的 SolidWorks。
依赖缺失时说明所需组件；本技能安装和运行不包含 SolidWorks 软件或许可证。

统一入口：

```powershell
python scripts/sw_modeling.py validate --request examples/modeling_create.json
python scripts/sw_modeling.py run --request examples/modeling_create.json --out-dir output/create-001
python scripts/sw_modeling.py inspect --source C:\CAD\part.sldprt
python scripts/sw_modeling.py checkpoints --root output/create-001/checkpoints
```

`validate` 不连接 CAD。`inspect` 仅读取已打开的指定零件，不激活或打开文件。
`run` 的输出目录必须是新目录。完整请求示例与使用说明见 [README](README.md)。

## 选择模式

- **create**：把需求整理为旧版 operation plan；支持 `sketch_rectangle`、`sketch_circles`、`extrude_boss`、`extrude_cut`。
  规格与验收要求来自用户给定尺寸、实测或明确标注的设计假设。完整参数规划可按需读
  [VibeCAD](subskills/solidworks-vibecad/SKILL.md)。
- **edit**：给出源 `SLDPRT` 和精确 `dimension@feature` 名称；支持当前配置下正线性驱动尺寸的 `set_dimension`。
  可先用 `inspect` 的 `dimensions` 查真实名称。源文件有未保存修改时停止，避免混淆磁盘快照与内存模型。
- **restore**：给出检查点根目录和 ID，验证文件摘要后复制至新文件，再由 SolidWorks 重开核对几何、特征、尺寸和草图。

修改与恢复仅支持无外部依赖的单配置零件。原件和原会话中的文档作为只读保护对象；
所有写入都发生在本次任务自有的新文档或磁盘副本中。

## 验收与失败处理

1. create/edit 请求必须有可测量的最终几何要求；不能把空条件、保存成功或截图非空作为规格通过。
2. 每个通过验收的步骤保存工作件，并生成不可变检查点：原生文件、SHA-256、测量上下文与步骤信息。
3. 孔位、孔径、实体数、体积及包围盒按明确公差核对。包围盒为 SW 近似数据，不当作精密尺寸链证明。
4. 交付检查普通及吸收草图的完全定义、驱动尺寸、特征错误和 STEP 独立重开结果；同时查看四视图，确认设计意图。
5. 修改失败时停止后续步骤，从最后完整检查点恢复到新副本并测量验证。
   `status=recovered` 表示恢复成功但原任务失败，`task_succeeded=false`，CLI 返回 2。
   没有有效检查点或恢复证据不足时返回失败；不缩孔、减厚或删除必需特征来通过验收。

输出以 `modeling_report.json` 为准。报告需检查 `status`、`task_succeeded`、`source_protection`、
`delivery` 或 `recovery`。恢复工件不冒充原需求的成功交付。

## 专项路由

统一白名单以外的任务，按需复用随包专项脚本，并明确其不具有本入口的自动检查点保证：

| 任务 | 先读 |
|---|---|
| 多圆角/倒角 CNC 零件 | [CNC 专项](subskills/solidworks-fillet-chamfer-cnc/SKILL.md) |
| 螺纹孔与螺纹表达 | [螺纹专项](subskills/solidworks-threaded-holes/SKILL.md) |
| 原生孔向导、原生筋 | [孔槽](references/complex-hole-features.md)、[筋](references/native-ribs.md) |
| 装配、可拖动配合、运动算例 | [装配](references/assembly.md)、[Motion](references/motion-study.md) |
| 工程图、BOM、多格式交付 | [工程图](references/drawing.md)、[导出](references/export.md) |
| 其他继承能力与执行经验 | [上游工作流](references/upstream-automation-guide.md) |

[capabilities.yaml](capabilities.yaml) 区分继承能力与新入口的验证范围，未验证功能不得外推。
未封装的 SW API 先按 [API 查证](references/api-lookup.md) 核实，再实现并实机验收。
螺旋参考线、装饰螺纹与实体牙型分别说明；动画、真实配合与受力验证分别验收。

## 同题回归

```powershell
python scripts/sw_modeling_regression.py validate
python scripts/sw_modeling_regression.py run --out-dir output/regression-001
```

四题依次验证：创建四孔板、厚度 8→12 mm、实际改到 14 mm 后因错误期望而恢复至 12 mm、
独立 Python 进程恢复检查点。使用解析体积、四孔规格及位置、约束、导出重开和源文件哈希检查。
离线测试与真实 SolidWorks 回归分开记录，测试数量不等同工程认证。

## 许可与来源

随包基础自动化模块派生自 MIT 许可的 `wzyn20051216/solidworks-automation-skill`。
保留 [LICENSE](LICENSE) 与 [NOTICE](NOTICE.md)，公开报告和例子使用本次生成的样件，不包含用户项目模型。
