# 数据库设计说明（Part 5）

## 目标

本阶段为 Kanban MVP 引入 SQLite 持久化能力，满足：

- 支持多用户隔离存储看板数据。
- 看板状态按 JSON 保存，并保留版本历史。
- 新环境首次启动时自动建库建表。

## 实体与关系

### 1) User

- 表名：`users`
- 作用：保存登录用户基础信息（为后续真实认证扩展预留）。
- 关键字段：
  - `id`：主键，自增。
  - `username`：唯一用户名。
  - `password_hash`：密码摘要（当前阶段允许简化值，后续替换真实哈希方案）。
  - `created_at`：创建时间。

### 2) Board

- 表名：`boards`
- 作用：用户维度的看板容器（一个用户可有多个看板）。
- 关键字段：
  - `id`：主键，自增。
  - `user_id`：外键，关联 `users.id`。
  - `name`：看板名称，默认 `default`。
  - `created_at` / `updated_at`：创建和更新时间。
- 约束：
  - `UNIQUE(user_id, name)`，防止同一用户重名看板。
  - 外键删除策略：`ON DELETE CASCADE`，删除用户时级联删除其看板。

### 3) BoardState

- 表名：`board_states`
- 作用：保存看板快照（JSON）与版本号。
- 关键字段：
  - `id`：主键，自增。
  - `board_id`：外键，关联 `boards.id`。
  - `version`：版本号，从 1 递增。
  - `state_json`：看板 JSON 文本。
  - `created_at`：创建时间。
- 约束：
  - `UNIQUE(board_id, version)`，保证同一看板版本唯一。
  - 外键删除策略：`ON DELETE CASCADE`，删除看板时级联删除快照。

## 索引设计

- `idx_boards_user_id`：加速用户维度查询看板。
- `idx_board_states_board_id`：加速按看板查询版本历史与最新快照。

## JSON Schema 约定（应用层校验）

看板 JSON 采用如下结构（应用层 `kanban_schema.py` 严格校验）：

```json
{
  "columns": [
    {
      "id": "col-backlog",
      "title": "Backlog",
      "card_ids": ["card-1", "card-2"],
      "order": 0
    }
  ],
  "cards": [
    {
      "id": "card-1",
      "title": "Task title",
      "details": "Task detail",
      "order": 0
    }
  ]
}
```

校验规则：

- 顶层必须包含 `columns` 与 `cards`。
- `columns` 不能为空。
- 列与卡片的 `id` 必须唯一。
- `column.card_ids` 中的每个卡片 ID 必须存在于 `cards` 集合。
- 反序列化非法 JSON 时直接抛出校验异常，禁止落库。

## 初始化与迁移策略

### 初始化策略

- 后端启动时执行 `initialize_database()`。
- 若数据库文件不存在，自动创建目录、数据库文件与三张表。
- 默认路径：`backend/data/pm.db`。
- 可通过环境变量 `PM_DB_PATH` 覆盖数据库路径。

### 迁移策略（当前阶段）

- 采用“幂等 DDL”策略：`CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`。
- 当前阶段不引入独立迁移框架，后续版本如需复杂演进可接入 Alembic。

## 测试策略映射

对应 Part 5 测试项已覆盖：

- Schema 序列化/反序列化：验证 round-trip 与非法 JSON。
- 数据层初始化与读写：验证建表、保存版本、读取最新快照。
- 失败场景：缺失用户创建看板触发外键错误；空看板触发 schema 校验错误。
