# 交付报告示例（AIMES Core 8.3 固定标题）

本文件仅演示格式，不代表任何真实任务已执行或验证通过。

## DELIVERY
- task_id: DEMO-TASK-001
- risk_level: R1
- report_level: R1
- project: aimes-example
- tool_and_version: example-agent 0.0
- base_commit: 0000000
- final_commit: 1111111
- result: VERIFIED

## FILES
- src/example.py | 实现演示功能 | behavior_change: yes

## TRACEABILITY_UPDATED
- DEMO-FEAT-001 -> DEMO-TEST-001 已登记；其余 N/A（演示范围）

## VERIFICATION
- check: 单元测试
  command_or_test_id: python -m unittest tests/test_example.py
  exit_code_or_result: 0
  scope: src/example.py
  evidence_path: .aimes/reports/test-example.log
  commit: 1111111
  status: PASS
- check: 端到端演示
  command_or_test_id: N/A
  exit_code_or_result: N/A
  scope: N/A
  evidence_path: N/A
  commit: N/A
  status: NOT_RUN

## UNRESOLVED / RISKS
- 演示数据未覆盖并发场景 | 低 | 下一步补充用例

## GIT_STATUS
- branch: demo
- working_tree: clean
- protected_user_changes: none

## TEMP_CLEANUP
- audited_candidates: .aimes/tmp/DEMO-TASK-001/
- deleted_or_archived: N/A（未授权删除）
- approval_reference: N/A

## NEXT
- 补跑端到端演示 | 依赖浏览器环境
