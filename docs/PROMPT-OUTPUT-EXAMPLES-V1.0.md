# AIMES 提示词输出示例库 V1.0

本文件为 Skills 提供共享 Few-Shot 示例。示例用于表达契约，不应被当作当前项目的真实事实。复制时必须替换占位符，并保留未知状态。

## 正例：证据与状态分离

```yaml
result:
  status: UNKNOWN
  conclusion: "尚不能确认该接口的运行时兼容性"
  evidence:
    - source: "src/example.py:20-31"
      kind: static_inspection
      supports: "静态代码中存在该调用路径"
  not_verified:
    - "未执行集成测试"
  next_action: "在具备依赖的环境中运行集成测试"
```

为什么正确：证据来源明确，结论范围受限，未执行的验证没有被包装成 PASS。

## 反例：把推断写成事实（禁止）

```yaml
result:
  status: PASS
  conclusion: "运行时完全兼容"
  evidence: []
```

为什么错误：没有运行时证据却声明 PASS；证据为空；结论超出检查范围。

## 正例：文件选择计划

```yaml
file_selection_plan:
  task: "分析订单服务的输入校验"
  budget:
    max_files: 8
    max_bytes: 120000
    policy: "先读入口、契约和直接依赖；命中不足再扩展"
  files:
    - path: "src/orders/handler.py"
      priority: P0
      reason: "目标请求入口"
      expected_evidence: "参数解析与校验路径"
    - path: "tests/test_orders.py"
      priority: P1
      reason: "现有行为与边界测试"
      expected_evidence: "可观察行为与回归约束"
  exclusions:
    - path: "vendor/"
      reason: "当前问题无证据表明需要读取第三方源码"
  approval: "只读且在预算内可自动继续；超预算或涉及敏感文件时先确认"
```

## 反例：无边界全量读取（禁止）

```yaml
file_selection_plan:
  files: ["整个仓库"]
  reason: "尽可能多了解项目"
```

为什么错误：没有可审计的文件清单、优先级、预算或读取理由。

## 输出校验规则

- 正例是格式与决策边界示范，不是保证模型行为的证据。
- 所有路径、行号、版本和工具结果必须来自实际观察；示例占位符不能作为事实输出。
- 反例用于负向评测；不能把反例内容复制到最终结论中。
