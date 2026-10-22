# AIMES 核心规则遵循回归测试

## 目的

固定案例集用于验证 AI 开发工具是否真正遵守工程治理规则，而不是只检查规则文件是否存在或让模型口头复述规则。案例覆盖需求歧义、证据真实性、用户改动保护、不可信内容/提示注入、修改范围、负向与边界测试、审批门禁、代码与文档追溯。

案例集定义位于 \`examples/evaluation/rule-following-suite.yaml\`。它是测试定义，不是测试结果；首次使用时，所有案例都应视为 NOT_RUN，不能从 YAML 中的预期结果推断模型已通过。

## 执行原则

1. 固定工具和版本、模型、Skill/治理版本、运行模式、操作系统、仓库 fixture 和任务输入。
2. 每个案例在独立的新会话中执行；涉及文件修改时使用可重置的隔离仓库，保存初始 commit 和最终 diff。
3. 保存原始模型输出、实际执行命令、退出码、测试报告、文件差异和其他可复核证据。敏感数据应脱敏。
4. 由独立验收步骤逐条判断 required_findings、forbidden_claims、acceptance_checks 和每项硬门禁；不能只依赖模型自评。
5. 对未实际执行的案例记录 NOT_RUN；受环境或授权阻塞时记录 BLOCKED。不得为了让评测通过而删案例或降低门禁。
6. 每次运行记录 suite ID/version、工具与模型版本、Skill/治理版本、开始时间、环境、实际 Token usage（如平台可提供）和证据引用。无法获得真实 Token usage 时记 UNKNOWN，不要用字符数估算。
7. 对比基线与候选时保持案例、输入、环境和验收标准一致；一次只改变一个优化因素。硬门禁回归优先于诊断分数或 Token 节省。

## 1. 校验固定案例集

\`\`\`powershell
aimes evaluation validate examples/evaluation/rule-following-suite.yaml --root . --format json
\`\`\`

该命令只检查案例集结构，不会调用 AI 工具。

## 2. 记录实际运行结果

每次完整运行创建独立 JSON 记录。运行记录的 \`metadata.suite_id\` 和 \`metadata.suite_version\` 必须与案例集一致，\`case_results\` 必须逐个包含 8 个案例，且每个案例必须记录该案例定义的全部硬门禁。PASS 结果必须关联证据引用。

示例结构（以下值仅演示字段，不代表已执行或通过）：

\`\`\`json
{
  "schema_version": 1,
  "metadata": {
    "run_id": "RUN-REPLACE-WITH-UNIQUE-ID",
    "suite_id": "AIMES-RULE-FOLLOWING-CORE",
    "suite_version": "1.0.0",
    "model": "填写实际模型和版本",
    "tool_version": "填写实际工具版本",
    "skill_version": "填写实际 Skill/治理版本",
    "started_at": "2026-10-22T00:00:00Z",
    "environment": "填写隔离 fixture、OS 和运行模式"
  },
  "case_results": [
    {
      "case_id": "RULE-REQ-AMBIGUITY-001",
      "status": "NOT_RUN",
      "hard_gates": {
        "NO_UNAPPROVED_ASSUMPTION": "NOT_RUN",
        "BLOCK_ON_CRITICAL_AMBIGUITY": "NOT_RUN"
      },
      "scores": {},
      "evidence_refs": [],
      "notes": "尚未执行；不得标记 PASS"
    }
  ]
}
\`\`\`

真实记录必须包含所有 8 个案例，而不是只复制上述一个案例。每个案例的硬门禁键必须与 YAML 中定义的 ID 一致。结果状态只能是 PASS、FAIL、BLOCKED 或 NOT_RUN。

## 3. 严格校验运行完整度

\`\`\`powershell
aimes evaluation validate-run .aimes/evaluation/rule-following-run.json --suite examples/evaluation/rule-following-suite.yaml --root . --format json
\`\`\`

严格校验会拒绝：

- 缺少案例或出现案例集以外的结果；
- 运行记录的 suite ID 或版本与固定案例集不一致；
- 缺少案例定义的任一硬门禁；
- 把没有证据引用的结果标记为 PASS；
- 把硬门禁未通过或未记录的案例标记为 PASS。

结构校验仍无法证明原始输出或证据真实，因此必须保留原始产物并由独立验收确认。

## 4. 报告与基线比较

\`\`\`powershell
aimes evaluation report .aimes/evaluation/rule-following-run.json --root . --format json
aimes evaluation compare .aimes/evaluation/baseline.json .aimes/evaluation/candidate.json --root . --format json
\`\`\`

比较结果可指出已记录的状态与硬门禁回归，但若案例集覆盖不完整、环境不一致或证据不足，不应将变化归因于模型、Skill 或 Token 优化。对正式发布/升级的候选版本，应要求完整案例覆盖且没有硬门禁回归。

## 当前状态

本次提交新增固定案例集与运行覆盖校验机制，并补充自动化测试。**尚未在真实 Codex/Claude 会话或实际业务项目中执行这 8 个案例，因此不宣称真实规则遵循率已提升。**
