# 前端代理说明

## 范围

该目录包含当前用于看板演示的 Next.js 前端 MVP。  
当前阶段为纯前端实现（本地内存状态），尚未接入后端持久化与 AI 聊天能力。

## 技术栈

- Next.js 16（`app` 路由）
- React 19
- TypeScript
- Tailwind CSS 4
- 使用 `@dnd-kit` 实现拖拽
- 使用 Vitest + Testing Library 进行单元测试
- 使用 Playwright 进行端到端测试

## 目录映射

- `src/app/page.tsx`
  - 首页路由入口
  - 渲染 `KanbanBoard`
- `src/components/`
  - `KanbanBoard.tsx`：看板主状态与交互处理（拖拽、重命名、新增、删除）
  - `KanbanColumn.tsx`：列容器、投放区域、列标题编辑、卡片列表
  - `KanbanCard.tsx`：可排序卡片视图与删除操作
  - `KanbanCardPreview.tsx`：拖拽浮层预览
  - `NewCardForm.tsx`：本地新增卡片表单
- `src/lib/kanban.ts`
  - 领域模型类型（`Card`、`Column`、`BoardData`）
  - 初始种子数据（`initialData`）
  - 卡片移动逻辑（`moveCard`）
  - ID 生成辅助函数（`createId`）
- `src/app/globals.css`
  - 全局设计变量与基础样式
- `src/test/setup.ts`
  - Vitest 测试初始化配置
- `tests/kanban.spec.ts`
  - Playwright 场景：看板加载、新增卡片、拖拽卡片

## 当前行为

- 看板数据从内存中的 `initialData` 初始化
- 当前支持：
  - 重命名列标题
  - 按列新增卡片
  - 删除卡片
  - 列内与跨列拖拽
- 暂无登录鉴权拦截
- 暂未接入后端 API
- 刷新后数据不会持久化

## 测试命令

在 `frontend/` 目录下执行：

```bash
npm install
npm run test:unit
npm run test:e2e
```

覆盖率命令：

```bash
npm run test:unit -- --coverage
```

## 集成期望（后续阶段）

- 保持 `KanbanBoard` 聚焦于 UI 状态编排
- 在接入后端接口前，先引入独立 API 客户端层
- 保留 Playwright 现有测试 ID：
  - `data-testid^="column-"`
  - `data-testid="card-<id>"`
- 保持 `globals.css` 中的视觉配色变量（与项目根 `AGENTS.md` 一致）
