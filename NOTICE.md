# 来源与新增说明

SolidWorks ModelOps 包含从以下项目继承和修改的代码、文档与资源：

- **SolidWorks Automation Skill**
- 上游仓库：<https://github.com/wzyn20051216/solidworks-automation-skill>
- 上游许可：MIT License
- 原版权声明：`Copyright (c) 2026 SolidWorks Automation Skill Contributors`

原始版权及 MIT 许可全文保留于 [LICENSE](LICENSE)。发布软件的副本或实质性部分时，应继续保留上述版权与许可。

## 继承部分

本仓库继承了上游的 SolidWorks 连接、零件、草图约束、文档数据、闭环执行、审查、导出及相关专项模块、参考资料和测试。存在于仓库中的继承模块不自动构成本版本统一入口的已验证能力。

## 本轮新增与整合

本轮在上游基础上增加或整合：

- 统一的 JSON 建模请求入口与校验；
- 受限的新建及精确命名线性尺寸编辑流程；
- 任务自有工作副本、磁盘检查点及 hash 核验恢复；
- 回归套件入口、相关离线测试和发布文档/CI 配置。

这些新增内容与上游保留模块共同组成 v0.1 pilot。具体行为、边界和验证结果以当前源代码、[README.md](README.md) 及真实运行报告为准。本说明不将上游全部工作归为本轮原创，也不把计划中的功能表述为已完成。

SolidWorks 是 Dassault Systèmes SolidWorks Corporation 的商标。本项目独立维护，不由该公司提供、授权背书或认证。使用原生 SolidWorks 功能须自行具备适用的软件使用授权。
