# 基于模型上下文的建模闭环

将用户需求整理为结构化动作计划，读取真实模型数据，逐步执行并验收。使用现有
`sw_part`、`sw_review` 等封装；原有专项建模、装配、工程图和导出接口继续保留。

## 入口

```powershell
python scripts/sw_preflight.py
python scripts/sw_closed_loop.py observe --out output/context.json
python scripts/sw_closed_loop.py validate --plan examples/closed_loop_plate.json
python scripts/sw_closed_loop.py run --plan examples/closed_loop_plate.json --out-dir output/closed_loop_run_01
```

- `observe` 只读当前模型与会话，输出路径不能已存在。没有活动文档时明确返回 `model: null`。
- `validate` 不连接 CAD。检查操作白名单、有限数值、引用顺序和验收条件。
- `run` 要求 SW 已打开，且输出目录不存在；仅在新建零件文档执行。活动原模型只作为只读参考，
  不对其重建、解析轻化组件、清选、保存或关闭。源文件哈希、原文档状态与恢复结果写入报告。
- 本入口不执行现有模型的原地修改。若任务需要该能力，沿用原专项流程并遵守用户的文件保护要求。

## 计划与真实模型的连接

Agent 负责把需求转成动作计划。计划是 JSON 数据，不是可执行 Python/VBA；不把用户文字传给 `eval`。
数值来自用户明确尺寸、实际模型测量或注明的设计假设。完整例子见 `examples/closed_loop_plate.json`。

支持四种操作：

原生筋另走 `sw_native_ribs.create_native_rib()` 专项封装和
[原生筋验收流程](native-ribs.md)，不在下表的 JSON 动作白名单中。
专项脚本仍应复用任务自有文档保护与“前快照 → 创建 → 回读 → 后快照 → 几何验收”的流程，
不能把普通拉伸特征记作 Rib，也不能因新增专项能力而绕过计划验证。

| op | params（长度单位 mm） |
|---|---|
| `sketch_rectangle` | `plane`, `cx_mm`, `cy_mm`, `width_mm`, `height_mm` |
| `sketch_circles` | `plane`, `circles: [{x_mm,y_mm,radius_mm}]` |
| `extrude_boss` | `sketch_id`, `depth_mm` |
| `extrude_cut` | `sketch_id`, `depth_mm`, `through_all`, `reverse` |

`id` 标识计划步骤，`sketch_id` 引用之前成功建立的草图；不依赖界面上碰巧出现的 `Sketch1`。
草图坐标是对应基准面的局部坐标；验收包围盒和孔位是模型全局坐标，不应混用。

参数可从真实上下文取数，例如：

```json
{"from_context":"geometry.bbox_size_mm.2","scale":1,"offset_mm":0}
```

- `from_context` 使用当前步骤执行前的实际模型测量；`from_source` 使用执行开始时的只读源模型快照。
- 白名单路径为 `geometry.bbox_size_mm.0/1/2`、`geometry.volume_mm3`、`geometry.body_count`。
- 数值按 `value * scale + offset_mm` 计算；调用者须匹配物理单位。缺失数据或非法数值立即停止，
  不用模板默认尺寸掩盖失败。只有少量标量绑定，不等同任意面/边的持久引用或自动逆向建模。
- `expect` 可检查 `body_count`、`bbox_size_mm`、`volume_mm3`、`feature_ok`、`holes`；
  `requirements` 是最终验收条件列表。可显式设置包围盒、体积和孔位公差。
- 包围盒来自 SW 的近似包围盒 API；不能冒充精密尺寸链证据。孔位检查来自 B-Rep 圆柱面，
  不单凭圆柱面宣称已证明盲孔/通孔。

## 检查与有限修正

每个动作记录执行前后快照、解析后的参数、返回值、重建结果和实际几何验收结果。
矩形和圆草图退出前会生成驱动尺寸与几何关系并读取完全定义状态；交付前递归核对吸收的子草图。
欠定义、过定义、缺少驱动尺寸或用整体 Fix 锁死的普通草图会阻止交付。孔向导原生轮廓仅在
父特征及驱动参数证据完整时允许其内部锚点。几何正确和参数化建模合格是两个独立检查。
拉伸必须增加实体体积，切除必须减少体积且保留实体；读不到体积不能判通过。

切除方向可在计划中显式声明一个备用方案：

```json
"fallback_params": [{"reverse": true}]
```

只有失败操作未创建特征，且完整特征列表、实体数、体积与包围盒证明未变，才尝试备用方向；
一轮计划最多重试一次。不自动缩小孔径、改变厚度或删掉必需特征以“通过”验收。
其他失败返回 `needs_revision` 与上下文、失败检查和下一步建议，后续步骤不执行。
Agent 应根据这些真实反馈修订计划，并在新输出目录重新运行；不能只修改报告为通过。

## 与原 VibeCAD 的关系

`compile_design_plan` 可以适配明确的底板、通孔和通孔阵列旧计划。原 `plan_from_brief.py`
及其模板和执行摘要入口保持不变。默认完整 CNC 模板中的圆角、倒角、口袋、关闭旧文档等操作
尚未加入新闭环的执行白名单，会在任何 CAD 写入前明确拒绝，包含标为可选的步骤也不会静默删除。
此时应使用原 CNC 专项流程，或由用户确认一个明确简化的设计，再生成新的动作计划。

## 产物与验收范围

输出含输入计划、源上下文、每步 `events.jsonl`、`run_report.json`；成功时另有唯一命名的
SLDPRT、STEP、四视图和原有 review 报告。STEP 需重新导入独立文档，核对实体数、体积及位置。
STEP 导入期间仅把 SW 工作目录临时设为本次输出目录，完成或失败后均恢复并回读核对，避免把导入子件路径落到用户项目目录。
恢复动作和源文件保护失败会使整个任务失败，不能因为模型看起来正确而忽略。

本能力为 `pilot`：当前只覆盖基础零件动作。结果仍需工程复核；没有实现官方私有模型、
任意自然语言自动设计、全装配拓扑推理或自动工程认证。自动测试运行新建隔离零件，不使用用户模型做破坏性测试。
