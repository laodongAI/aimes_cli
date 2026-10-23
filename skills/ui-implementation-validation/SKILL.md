---
skill_id: SKL-CORE-UI-VERIFY-001
change_summary: "V1.0：新增 UI 响应式、可访问性、浏览器和视觉回归验证流程"
---
# Skill：UI Implementation Validation（界面实现验证）

## Purpose / 目标与边界
针对前端页面变更制定并执行与风险相称的验证，覆盖交互行为、响应式、键盘与焦点、可访问性、控制台错误和视觉回归。该 Skill 负责验证而不是设计决策；工具能力必须先确认，不能把计划当作执行证据。

## Trigger conditions / 触发条件
ui_implementation, responsive_layout, accessibility_review, visual_regression, form_interaction_change, frontend_build, browser_verification。

## Required inputs / 必需输入
task_id, changed_ui_paths, acceptance_criteria, project_context。可选：target_viewports, supported_browsers, test_commands, browser_tool, visual_baseline, accessibility_standard。

## Preconditions / 前置条件
读取项目规则与测试命令；检查 diff；确认可用浏览器、自动化测试、截图对比和无障碍工具；未知能力标记 UNKNOWN。

## Workflow / 工作流程
1. 根据变更范围建立验证矩阵：构建/静态检查、关键交互、目标视口、键盘焦点、语义和可访问名称、错误/加载/空状态、控制台和网络错误、视觉回归。
2. 优先运行项目现有测试与构建命令，不臆造命令；如果命令不存在，记录原因。
3. 若可用，使用真实浏览器（例如项目已有的 Playwright 或 Chrome DevTools）验证关键路径，并记录 URL/页面、视口、步骤、结果和证据位置。
4. 对比参考截图时固定视口和数据；区分动态内容、反锯齿和预期变化，不以像素差异单独决定缺陷。
5. 检查窄屏、缩放、长文本、表格/弹窗溢出、固定元素遮挡、触控/键盘可达性。
6. 无障碍检查至少考虑语义结构、可访问名称、键盘可达、焦点可见、错误提示关联和颜色对比；自动扫描通过不等于完整 WCAG 认证。
7. 对失败项定位原因并提出最小修复；修复后复验并保留首次失败和复验记录。
8. 输出每项状态 PASS/FAIL/NOT_RUN/BLOCKED/UNKNOWN、实际命令/方法、证据和限制。

## Outputs / 输出契约
verification_matrix, commands_executed, browser_evidence, viewport_results, accessibility_findings, visual_diff_summary, unresolved_risks, final_status。

## Safety and permissions / 安全与权限
不安装新工具或依赖，除非已授权；不发送敏感数据到外部服务；不伪造截图、浏览器状态或测试结果；不覆盖用户修改。

## Failure handling / 失败处理
浏览器不可用则执行不受影响的静态/构建检查并标记运行验证 NOT_RUN/BLOCKED；缺少截图基线时不声称视觉回归通过；工具失败时记录错误并给出人工复验步骤。

## Completion criteria / 完成判据
所有适用检查已执行或明确记录未执行原因；PASS 有可定位证据；失败和剩余风险已列出；结论没有超出实际证据范围。

## 通用执行协议（必须遵守）
1. 任何前端改动必须按项目规则执行真实浏览器验证；若环境不支持，明确标记 BLOCKED 并说明如何补验。
2. 先检查当前分支和工作区，保护未提交修改。
3. 运行项目定义的测试/构建命令，不臆造执行结果。
4. 把静态检查、构建、交互、截图和人工验收分别记录。
5. 不把自动扫描等同于完整可访问性认证。

## 评测案例
- 修改导航菜单：验证鼠标、键盘、焦点和窄屏展开行为。
- 修改表单：验证错误提示、字段关联、提交中/成功/失败状态。
- 只改 CSS 但浏览器不可用：静态检查可以报告，但视觉状态不能标 PASS。
- 视觉截图差异较大：核对数据、视口和预期变化后再判定。
