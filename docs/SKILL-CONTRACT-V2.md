# AIMES Skill 契约 V2

## 1. 目标与兼容策略

Skill 不再仅被视为提示词文件，而是具备可验证元数据的工程组件。V2 将生命周期、停止条件、失败恢复、完成判据、副作用与幂等性纳入注册表。

- `schema_version: 1`：继续兼容现有 Skill 注册表。
- `schema_version: 2`：新 Skill 建议采用；缺少 V2 契约字段时校验失败。
- V1 记录不会被自动改写，也不会因为兼容而被视为满足 V2。
- Skill 成功不代表业务任务自动进入 `VERIFIED`；任务状态仍由 AIMES 统一证据门禁决定。

## 2. V2 新增字段

| 字段 | 类型 | 目的 |
|---|---|---|
| `lifecycle_stage` | 枚举 | `proposed`、`review`、`pilot`、`verified`、`released`、`monitoring`、`deprecated` |
| `stop_conditions` | 非空列表 | 明确何时必须停止，不允许继续执行受阻操作 |
| `failure_recovery` | 非空列表 | 失败后保留哪些产物、如何降级及从何处恢复 |
| `completion_criteria` | 非空列表 | 定义可检查的完成条件，避免以模型自述作为验收 |
| `approval_required` | 布尔值 | 声明运行此 Skill 是否需要人工审批；不授予 Skill 自行批准的权限 |
| `side_effects` | 非空列表 | 声明文件写入、命令执行、网络调用等潜在副作用 |
| `idempotency` | 枚举 | `idempotent`、`guarded` 或 `non_idempotent`，为重试策略提供依据 |

V2 记录若把 `validation_status` 标为 `VERIFIED`，还必须提供非空 `evaluation_suite` 和 `evidence`。注册表校验只检查记录完整性，不会代替真实评测。

## 3. 运行约束

1. **权限最小化：** `required_capabilities` 描述运行所需能力，`forbidden_actions` 描述禁止行为；Skill 权限不得高于用户、工具和项目规则。
2. **审批不自授：** `approval_required: true` 表示调用链必须满足外部审批条件，Skill 不能自行批准需求、发布或绕过质量门禁。
3. **停止优先：** 遇到阻断级未知、权限不足、权威来源冲突或硬门禁失败时，停止受影响的写操作；允许继续不受影响的只读分析。
4. **恢复不猜测：** 恢复前检查基线、工作区和已生成产物；不得重复执行未知是否已完成的非幂等操作。
5. **完成须有证据：** 所有必需步骤须已执行或记录合理跳过原因；输出契约、未解决问题和验证结果必须明确。
6. **未知不晋级：** 未执行的测试、不可观测的 Token usage 或未验证的工具行为必须保持 `NOT_RUN` / `UNKNOWN` / `BLOCKED`。

## 4. 使用方式

在仓库根目录执行：

```powershell
aimes skill validate examples/skills/registry.example.yaml --root . --format json
```

CI 同样执行该示例校验，避免 Schema、验证器与文档发生漂移。

## 5. 下一步

V2 先提供可检查的契约和兼容性门禁。后续仍需增加：

- Skill 执行记录：任务 ID、基线 commit、Skill 版本、工具/模型版本、输入来源、步骤、输出引用、实际命令与证据。
- 工作流状态机：进入条件、成功条件、失败分支、取消与恢复。
- 独立评测：基线与候选版本使用相同任务集，检查硬门禁不退化，并记录真实 usage；缺少真实 usage 时不得估算填充。
