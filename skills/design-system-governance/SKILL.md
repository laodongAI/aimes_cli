---
name: design-system-governance
description: 盘点并治理设计 Token、组件契约、主题与跨页面一致性。当任务涉及 设计系统、设计令牌、主题变更、组件库、公共组件、视觉一致性 等内容时使用该 Skill。
skill_id: SKL-CORE-UI-SYSTEM-001
change_summary: "V1.0：新增项目设计系统、Token 与组件约定治理"
---# Skill：Design System Governance（设计系统治理）

## Purpose / 目标与边界
识别、建立和维护项目设计系统，包括设计 Token、组件契约、状态约定、使用示例和变更治理，确保多页面与多 AI 工具之间保持一致。它不要求所有项目采用同一套视觉风格，也不自动替换现有组件库。

## Trigger conditions / 触发条件
design_system, design_tokens, component_library, theme_change, shared_component_change, visual_consistency, design_standard_missing。

## Required inputs / 必需输入
task_id, project_context, ui_paths, existing_design_assets。可选：brand_guidelines, token_files, component_docs, screenshots, product_decisions。

## Preconditions / 前置条件
检查现有 CSS variables、主题文件、组件库、设计文档、品牌资产、测试和使用点；识别已批准规则与仅由现状推断的模式。

## Workflow / 工作流程
1. 盘点 Token、基础组件、复合组件、页面模板、主题和缺失项。
2. 将设计系统分为已批准、现有但未正式批准、建议新增三类，记录来源。
3. 统一颜色、字体、字号、间距、尺寸、圆角、阴影、层级、动效和断点的语义命名；优先沿用项目现有命名。
4. 对组件记录用途、API/Props、变体、交互状态、可访问名称、键盘行为、错误/空/加载状态和使用禁忌。
5. 检查重复 Token、硬编码值、近似颜色、重复组件和跨页面差异；区分合理例外与缺陷。
6. 新增或修改全局 Token、主题、基础组件 API 前，提供影响面、迁移策略、兼容性和回滚方案；重大变更须批准。
7. 将规范落到可被规则入口引用的项目文档，并给出可自动检查的项目（例如禁止新增未登记 Token、公共组件优先复用）。
8. 对代表性页面进行一致性抽查，输出缺口与后续治理任务。

## Outputs / 输出契约
design_system_inventory, approved_rules, inferred_patterns, proposed_tokens, component_contracts, consistency_findings, migration_plan, approval_items。

## Safety and permissions / 安全与权限
不把未批准的推断提升为强制规则；不擅自替换全局主题/组件库；不因审美偏好进行大范围格式化或重构；保护用户改动。

## Failure handling / 失败处理
未找到设计系统时标记 MISSING_STANDARD 并提出候选基线；组件库来源不明时只读盘点；公共 API 影响不明确时暂停变更并请求批准。

## Completion criteria / 完成判据
规范来源与批准状态明确；Token/组件约定可定位；跨页面差异有证据；高风险变更具备影响和回滚方案；没有虚构批准或验证。

## 通用执行协议（必须遵守）
6. 无法确认的能力或证据使用 `UNKNOWN`；未执行的检查使用 `NOT_RUN`，受环境阻塞使用 `BLOCKED`，不得把它们写成 `PASS`。
1. 先检索现有实现，不创建与已有资产重复的第二套规范。
2. Token 和策略阈值应在项目参数/Token 中注册，不散落硬编码。
3. 规范必须落到项目规则可引用的权威文件，而不是只留在聊天中。
4. 修改公共组件前检索调用方并规划回归验证。
5. 把建议、现状和批准决定分开记录。

## 评测案例
- 已存在颜色和间距变量：建议复用，不再新增同义 Token。
- 多页面按钮风格不一致：先判断是否为组件变体或真实偏差。
- 需要替换主题：先输出迁移/影响/回滚方案并请求批准。
- 没有设计规范：提出候选基线，明确未批准状态。
