# 后端代理说明

## 范围

该目录包含 PM MVP 的 FastAPI 后端服务。当前为 Part 10 完成状态，包含完整的看板 CRUD API、SQLite 数据层、数据迁移和测试套件。

## 核心功能

- **看板 API**: `GET /api/kanban` 和 `POST /api/kanban` 读写看板状态
- **数据持久化**: SQLite 数据库，支持版本化的看板状态存储
- **向后兼容**: 自动将旧版 3 列看板迁移至 5 列布局
- **健康检查**: `GET /api/health` 服务状态检查
- **前端托管**: 静态文件服务（生产环境从 `frontend_dist/` 加载）

## 目录结构

```
backend/
├── app/
│   ├── __init__.py           # 包初始化
│   ├── main.py               # FastAPI 应用工厂、路由、生命周期管理
│   ├── db.py                 # SQLite 数据层（建表、CRUD）
│   └── kanban_schema.py      # TypedDict 类型与严格验证逻辑
├── tests/
│   ├── test_db.py            # 数据库层单元测试
│   └── test_main.py          # API 路由单元测试
├── data/                     # SQLite 数据库文件目录（运行时创建）
├── pyproject.toml            # 依赖与 pytest 配置
└── uv.lock                   # uv 锁定文件
```

## 数据模型

### 表结构

- **users**: 用户表（MVP 单用户，`user`/`password`）
- **boards**: 看板表（用户默认看板）
- **board_states**: 看板状态表（版本化，追加-only）

### BoardState Schema

```python
{
    "columns": [
        {"id": str, "title": str, "card_ids": list[str], "order": int}
    ],
    "cards": [
        {"id": str, "title": str, "details": str, "order": int}
    ]
}
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `PM_DB_PATH` | SQLite 数据库文件路径 | `backend/data/pm.db` |
| `PM_CORS_ORIGINS` | CORS 允许来源 | `http://localhost:3000,http://127.0.0.1:3000` |

## 运行

```bash
# 安装依赖（包含 dev 依赖）
uv pip install --system -e ".[dev]"

# 开发服务器（热重载）
uvicorn app.main:app --reload

# 生产构建（配合 Docker）
docker compose up --build -d
```

## 测试

```bash
# 运行所有测试（需 80% 覆盖率）
pytest

# 单文件测试
pytest tests/test_main.py

# 指定测试名
pytest tests/test_main.py -k "test_health"
```

## 关键实现细节

### 并发安全
- `save_board_state` 使用原子 INSERT + 子查询避免版本号竞争
```python
INSERT INTO board_states(board_id, version, state_json)
VALUES (?, (SELECT COALESCE(MAX(version), 0) + 1 FROM board_states WHERE board_id = ?), ?)
```

### 认证策略
- MVP 仅前端认证（`sessionStorage` 标记）
- 密码使用 SHA-256 哈希存储（确定性哈希，便于迁移）
- 后端 API 当前无认证中间件（已知设计权衡）

### 3→5 列迁移
- 在 `GET /api/kanban` 时自动检测旧版 3 列布局
- 透明迁移：todo→backlog, doing→in-progress, done→done
- 新增 discovery 和 review 两列

### 错误处理
- API 异常内部记录（`logger.error`），返回通用客户端消息
- `KanbanValidationError` 映射为 HTTP 400
- 未预期异常返回 HTTP 500，详情不泄露

## 最近修复（2026-04-18）

- SEC-1: 密码使用 SHA-256 而非明文
- SEC-2: 异常详情内部记录，不返回客户端
- SEC-4: CORS 限制为 GET/POST 方法
- BUG-1: 原子 INSERT 消除并发版本冲突
- BUG-2: 单请求共享数据库连接
