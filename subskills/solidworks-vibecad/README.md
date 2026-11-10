# SolidWorks VibeCAD

`solidworks-vibecad` 是 `solidworks-automation` 仓库里的参数化设计规划子技能，用来把自然语言机械设计需求转换为结构化设计计划、制造规则检查、SolidWorks API 执行摘要和审查门禁。

## 为什么放在子技能里

这个方向的价值不在于临时生成宏，而在于把重复机械设计沉淀成可复用工程资产：

```text
行业知识库 + 参数 schema + 提示词模板 + 稳定 API 封装 + 自动审查
```

因此它应该作为 SolidWorks 自动化大仓库的一部分，和 CNC 圆角/倒角、螺纹孔、装配、MCP 等能力并列管理。

## 当前能力

- 从自然语言需求生成参数化设计计划 JSON。
- 内置 M3-M12 攻丝底孔、通孔、CNC 圆角/倒角、最小壁厚等规则。
- 给 LLM 提供严格规划提示词，避免直接输出不稳定宏。
- 生成 SolidWorks API 执行摘要，明确每一步对应父技能的哪个稳定封装。
- 生成审查门禁，要求保存、导出、多视角预览和 review report。

## 目录

```text
solidworks-vibecad/
├── SKILL.md
├── README.md
├── manifest.yaml
├── knowledge/
│   └── manufacturing_rules.yaml
├── prompts/
│   └── solidworks_parametric_planner.md
├── schemas/
│   └── design_plan.schema.json
├── scripts/
│   ├── plan_from_brief.py
│   └── sw_execution_outline.py
├── examples/
│   ├── motor_mount_brief.txt
│   ├── motor_mount_plan.json
│   └── motor_mount_execution.md
└── references/
    └── vibecad-roadmap.md
```

## 快速运行

在 `solidworks-automation` 仓库根目录执行：

```powershell
py subskills\solidworks-vibecad\scripts\plan_from_brief.py `
  --brief-file subskills\solidworks-vibecad\examples\motor_mount_brief.txt `
  --out subskills\solidworks-vibecad\examples\motor_mount_plan.json

py subskills\solidworks-vibecad\scripts\sw_execution_outline.py `
  --plan subskills\solidworks-vibecad\examples\motor_mount_plan.json `
  --out subskills\solidworks-vibecad\examples\motor_mount_execution.md
```

## 示例输出

示例需求会识别：

- 底板：`90 x 60 x 8 mm`
- 固定孔：`M5` 螺丝通孔，通孔直径 `5.5 mm`
- 中心孔：`22 mm`
- 外轮廓圆角：`R6`
- 顶边倒角：`C1`
- 审查：`SLDPRT + STEP + parameters_json + review_report_json + isometric_preview`

## 实际执行与反馈

父技能新增 `scripts/sw_closed_loop.py`，接通模型只读快照、计划动作、真实几何检查和有限反馈修正。
从父技能根目录运行：

```powershell
python scripts/sw_closed_loop.py validate --plan examples/closed_loop_plate.json
python scripts/sw_closed_loop.py run --plan examples/closed_loop_plate.json --out-dir output/closed_loop_run_01
```

输出目录必须不存在，写入仅发生在新建零件。当前支持矩形/圆草图、拉伸、切除与测量绑定，
见 [闭环说明](../../references/closed-loop-modeling.md)。原需求规划器及执行摘要继续可用。
默认完整 `cnc_mount` 中的圆角、倒角、口袋尚未进入新动作白名单；这些设计继续使用原专项工具，
不会在转换时静默删除。失败报告交由 Agent 基于真实上下文修订计划，不自动改变关键设计尺寸。
