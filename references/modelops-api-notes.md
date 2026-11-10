# ModelOps 新接口查证

统一执行器复用随包已验证的 `update_dimension_mm`、保存、打开和上下文接口。
对尺寸单位额外使用 `IDimension.GetType()`，拒绝把角度或整数参数按毫米写入。

- 官方方法：`IDimension.GetType() -> int`
- 枚举：`swDimensionParamTypeDoubleLinear=0`、`DoubleAngular=1`、`Integer=2`、`Unknown=-1`
- 官方来源：
  - https://help.solidworks.com/2024/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDimension~GetType.html
  - https://help.solidworks.com/2024/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swDimensionParamType_e.html
- 驱动状态复用草图审查中的 `DrivenState`，不改变 driven dimension。
- `update_dimension_mm()` 的接口成功结果还需与 `after_mm.current` 比较，不能仅依赖返回码。
- 检查点是保存后的原生工件，不是任意 Python 副作用的事务；恢复只管理本次任务的零件副本。

版本兼容和实机回归结果单独记录，不外推未经测试的 SW 版本或零件类型。
