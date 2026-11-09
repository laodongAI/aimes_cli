---
name: vue-frontend-engineering
description: 对 Vue 3 前端实现执行组件化、Composable、Pinia 状态边界、API 分层、TypeScript 类型、性能和组件测试规范；Vue 页面、组件、前端重构或组件复用任务必须调用。
skill_id: SKL-CORE-VUE-001
version: 1.0.0
status: PROPOSED
---

# Skill：Vue 前端组件化与工程实现

## 目标与边界
在遵循项目技术栈、设计系统和批准架构的前提下，确保 Vue 前端具备清晰组件边界、可复用能力、可测试状态和可维护结构。默认面向 Vue 3 + TypeScript；若项目不是该技术栈，标记不适用并路由到通用工程 Skill。

## 触发条件
Vue 页面/组件开发、Vue 组件重构、公共组件/Composable、Pinia Store、前端代码复用、Vue 性能和可测试性治理。涉及视觉/交互设计同时调用 frontend-design 或 ui-quality-review；涉及主题/公共组件契约调用 design-system-governance。

## 必需输入
task_id, approved_requirements, project_stack_and_versions, target_pages_or_modules, existing_component_inventory.

## 前置检查
读取项目规则、前端目录索引、package.json、构建配置、组件库和设计 Token；确认 Vue、TypeScript、Pinia、Router、UI 库版本和真实 lint/typecheck/test 命令；搜索相似组件、Composable、Store、API service、类型和测试；检查 Git 基线和授权范围。

## 工作流程
### 1. 页面与组件职责
- Page/View：路由入口、页面级数据组合和布局编排，不承载所有业务细节。
- Feature/Business Component：封装明确业务概念、局部状态和交互，通过 Props/Emits/Slots 协作。
- Shared UI Component：只提供通用展示/交互，不直接调用业务 API，不依赖具体页面路由。
- Composable：封装可复用响应式逻辑、请求生命周期、表单行为或复杂状态转换；不渲染 UI。
- API/Service：集中请求、DTO 映射、错误映射和取消；组件不重复拼接 URL、headers 和错误解析。
- Store：只保存确需跨页面共享且有明确生命周期的状态；临时 UI 状态留在组件。
- Types：公共 Props、DTO、枚举和领域类型明确声明，避免 any 和不一致的重复定义。

### 2. 组件抽取判断
以下信号触发抽取评估：跨页面复用；独立业务语义；复杂状态/交互可独立测试；独立维护或权限边界。仅仅代码长不是唯一理由。抽取前确认调用场景语义/变化原因是否相同、Props/Emits/Slots 是否稳定、是否会出现大量布尔 Props/页面特判/万能组件，以及抽取是否降低维护成本。

### 3. Vue 3 编码规则
- 按项目约定优先使用 script setup + TypeScript + Composition API。
- Props/Emits 显式声明；不得直接修改 Props；父子通信使用 Emits 或明确的双向模型契约。
- 复杂业务逻辑移入命名清晰的 Composable 或应用服务；派生状态使用 computed。
- watch 只处理必要副作用；避免复制 computed、相互监听循环或隐式同步。
- API 调用集中在 service/client；处理加载、错误、空结果、超时、取消、重复提交和过期响应。
- Pinia 不作为所有状态默认容器；Store 说明共享范围、生命周期、持久化和清理策略。
- 列表使用稳定业务 key；复杂模板判断提取 computed/函数。
- 组件卸载清理订阅、监听器、定时器和请求；避免内存泄漏。
- 样式遵循 Token、作用域和组件变体；避免全局污染、无理由深度穿透和重复硬编码。
- 异步操作防止竞态，旧请求不得覆盖新查询结果；按项目能力使用 AbortController 或请求序号。

### 4. 文件组织
遵循项目既有结构。没有约定时可按 feature/domain 分组，页面、组件、composables、services、types、tests 就近组织。共享组件与业务组件分开；不得为满足目录模板批量迁移文件。

### 5. 测试与验证
组件测试覆盖 Props/Emits/Slots、交互和空/加载/失败/禁用状态；Composable 测试覆盖响应式状态、边界、取消和清理；页面测试覆盖关键流程与 API 失败反馈；共享组件变更检查所有调用点和回归。运行项目真实 lint、typecheck、unit、build 和可用浏览器测试；未执行标记 NOT_RUN/BLOCKED。

## 输出契约
component_map, reuse_decisions, props_emits_contracts, composable_and_store_boundaries, api_dependencies, test_matrix, frontend_review_findings, verification_results.

## 禁止事项
禁止巨型 SFC；禁止复制已有公共组件、API 请求、表单校验和权限逻辑；禁止万能组件和过多布尔 Props；禁止所有状态都进 Pinia；禁止子组件直接修改 Props 或跨层访问父组件内部变量；禁止吞异常、忽略错误/空态/竞态；禁止未验证宣称构建或视觉测试通过。

## 完成判据
组件/页面职责清晰；复用决策有证据；Props/Emits/Composable/Store/API 边界明确；测试覆盖适用交互和异常；最终 Diff 与验证状态可复核。

## 评测案例
- 新增相似页面：先检索并复用表格/筛选/表单组件。
- 大型 SFC：拆清页面编排、业务组件、Composable 和 API 层职责。
- 子组件修改 Props：改用 Emits/明确模型契约。
- 两个页面业务语义不同：不强制合并成万能组件。
- 多页面重复请求处理：提取 API client/service 或 composable，并验证竞态和错误处理。
- Store 混入临时弹窗状态：评估回归局部状态并明确生命周期。
- 未执行浏览器测试：标记 NOT_RUN，不宣称视觉通过。
