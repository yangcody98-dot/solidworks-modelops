# SolidWorks ModelOps 技能与入口映射

本仓库的根 skill 为 `solidworks-modelops`，统一入口是 `scripts/sw_modeling.py`。
v0.1 为 pilot：基础零件创建、任务副本中的命名线性尺寸修改、磁盘检查点与新副本恢复。
继承的专项脚本保留各自的验证边界，不自动获得统一入口的检查点或恢复保证。

## 根入口

| 文件 | 职责 |
| --- | --- |
| [SKILL.md](../SKILL.md) | AI Agent 路由、写入边界与验收约定 |
| [README.md](../README.md) | 安装、完整 CLI、支持范围与测试说明 |
| [agents/openai.yaml](../agents/openai.yaml) | 根 skill 的 Agent 展示与默认提示 |
| [scripts/sw_modeling.py](../scripts/sw_modeling.py) | `validate`、`run`、`inspect`、`checkpoints` |
| [scripts/sw_checkpoints.py](../scripts/sw_checkpoints.py) | 检查点发布、文件 hash 核验与复制恢复 |
| [scripts/sw_modeling_regression.py](../scripts/sw_modeling_regression.py) | 创建、修改、失败恢复、独立进程重开的同题回归 |
| [capabilities.yaml](../capabilities.yaml) | 各能力等级、限制与证据范围 |

请求示例为 [create](../examples/modeling_create.json)、[edit](../examples/modeling_edit.json)、
[restore](../examples/modeling_restore.json)。编辑和恢复示例需要填入实际源文件/检查点信息；
[回归 suite](../examples/modeling_regression_suite.json) 会关联本次生成的测试工件。

## 复用层与专项

| 模块或子技能 | 使用场景 | 与统一入口的关系 |
| --- | --- | --- |
| `sw_closed_loop` / `sw_closed_loop_native` | 四动作计划、有限反馈、任务自有原生零件 | create 复用执行引擎与原生适配器 |
| `sw_document_data` | 精确尺寸名称与回读 | edit 复用尺寸更新，额外执行归属和验收检查 |
| `sw_sketch_constraints` | 普通及吸收子草图、尺寸和关系证据 | 供交付和恢复审查使用 |
| [solidworks-vibecad](../subskills/solidworks-vibecad/SKILL.md) | 自然语言需求转参数化计划 | 按需规划；超出四动作范围不能直接交给统一执行器 |
| [solidworks-fillet-chamfer-cnc](../subskills/solidworks-fillet-chamfer-cnc/SKILL.md) | 多圆角/倒角 CNC 零件 | 独立专项流程，按能力清单与实际报告复核 |
| [solidworks-threaded-holes](../subskills/solidworks-threaded-holes/SKILL.md) | 螺纹孔与螺纹表达 | 独立专项；区分装饰、参考线和实体牙型 |
| [autocad-automation](../subskills/autocad-automation/SKILL.md) | AutoCAD 与二维交付 | 继承专项，不属于 ModelOps 的原生零件事务接口 |

统一入口以外的装配、Motion、工程图、FEA 等任务，按根 skill 的专项路由选择文档，
并回读 [capabilities.yaml](../capabilities.yaml) 的限制。不能因为存在参考文档就把能力记为已完成。

## 检查与扩展

执行 `python scripts/validate_skill.py` 检查必需文件、根 skill 元数据及 Python/JSON 语法；
离线 pytest 和原生回归的具体命令见 [README.md](../README.md)。这些检查分别报告，
文件完整或离线测试通过不能代替本机 SolidWorks 建模证据。

增加新的统一动作时，先定义 JSON 校验与可测量验收条件，再补任务归属、检查点与失败恢复行为，
添加离线和原生回归案例，最后更新根 SKILL、README、能力清单和本文。
增加独立专项时，将实现和资源置于 `subskills/<name>/` 并更新同一组现有入口文件；
本仓库不依赖 `SUBSKILLS.md` 或 `project.yaml` 作为注册入口。

## 继承资料

[上游自动化指南](../references/upstream-automation-guide.md)、CAD Studio 产品说明与桌面原型
用于保留技术上下文。其名称、发布流程或主页描述的是上游项目，不能作为本项目的下载或安装入口。
来源和许可见 [NOTICE.md](../NOTICE.md)。
