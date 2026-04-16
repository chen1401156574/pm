# 代码审查报告

**项目**: PM MVP Kanban  
**审查基准版本**: commit `9e90dcd`（step 10 complete）  
**审查日期**: 2026-04-17  
**审查范围**: 全栈代码库——后端（FastAPI/SQLite）、前端（Next.js/React）、测试、基础设施

---

## 总体评价

代码库整体质量**良好，达到 MVP 生产可用标准**。架构分层清晰，类型系统完善，测试覆盖有效（后端 92%），错误处理路径完整。以下审查按严重程度分级标注每个问题，并给出可操作的修复建议。

---

## 一、安全

### 🔴 SEC-1：`password_hash` 列存储明文字符串

**文件**: `backend/app/main.py:36`

```python
DEFAULT_PASSWORD_HASH = "password"  # In a real app, use a real hash
```

`password_hash` 这个列名暗示存储哈希值，但实际写入的是原始字符串 `"password"`。若未来添加真实认证逻辑并从数据库读取此字段进行比对，现有数据会静默失效或被误认为已哈希处理。即使是 MVP，正确的做法是存储确定性哈希（如 SHA-256），而不是明文。

**修复建议**：
```python
import hashlib
DEFAULT_PASSWORD_HASH = hashlib.sha256(b"password").hexdigest()
```

---

### 🔴 SEC-2：内部异常信息直接返回给客户端

**文件**: `backend/app/main.py:195-196`

```python
except Exception as e:
    raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
```

`str(e)` 可能包含数据库文件路径、SQL 语句片段、内部变量名等敏感信息，不应暴露给客户端。

**修复建议**：
```python
except Exception as e:
    logger.error(f"Unhandled error in update_kanban: {str(e)}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")
```

---

### 🟡 SEC-3：后端 API 无任何认证保护

**文件**: `backend/app/main.py:161-196`

所有 API 路由（`GET /api/kanban`、`POST /api/kanban`）均无认证中间件。认证完全依赖前端 `sessionStorage` 中的 `pm-authenticated=true` 标记，任何知道 API 地址的用户都可以直接读写看板数据。

这是 MVP 的已知权衡，但应在代码注释中明确标注，避免未来扩展时遗漏。

---

### 🟡 SEC-4：CORS 使用通配符方法与头

**文件**: `backend/app/main.py:131-137`

```python
allow_methods=["*"],
allow_headers=["*"],
```

`allow_methods=["*"]` 允许 `DELETE`、`PATCH`、`PUT` 等当前路由中并不存在的方法，扩大了攻击面。应改为只允许实际使用的方法：

```python
allow_methods=["GET", "POST"],
allow_headers=["Content-Type", "Accept"],
```

---

## 二、正确性与潜在 Bug

### 🔴 BUG-1：并发写入时版本号会产生唯一键冲突

**文件**: `backend/app/db.py:87-101`

```python
cursor = connection.execute("SELECT COALESCE(MAX(version), 0) FROM board_states WHERE board_id = ?", ...)
current_version = int(cursor.fetchone()[0])
next_version = current_version + 1
connection.execute("INSERT INTO board_states(board_id, version, state_json) VALUES (?, ?, ?)", ...)
```

`SELECT MAX(version)` 与 `INSERT` 之间没有加排他锁。若两个请求并发执行，都读到相同的 `current_version`，再各自尝试写入 `version + 1`，后一个会触发 `UNIQUE (board_id, version)` 约束，抛出 `sqlite3.IntegrityError`，最终导致 500 响应。

SQLite 默认是串行化 WAL 模式，单机低并发时实际碰撞概率极低，但这是一个结构性缺陷。

**修复建议**：将操作包在显式事务中，或改用 `INSERT INTO board_states SELECT ?, COALESCE(MAX(version),0)+1, ? FROM board_states WHERE board_id=?` 的原子单语句写法。

---

### 🔴 BUG-2：`get_current_user_id` 与外层 `get_db` 使用两个独立数据库连接

**文件**: `backend/app/main.py:89-99, 161-178`

```python
def get_current_user_id(db=Depends(get_db)) -> int:
    ...

@app.get("/api/kanban")
def get_kanban(
    user_id: int = Depends(get_current_user_id),
    db=Depends(get_db)          # ← 这是第二个连接
):
    board_id = get_user_board_id(user_id, db)
```

FastAPI 对同一个请求中两次 `Depends(get_db)` 会创建**两个独立的 SQLite 连接**。在 `get_current_user_id` 中创建用户并 `commit` 之后，如果 SQLite 未处于 WAL 模式，外层 `db` 连接在同一隔离级别下可能看不到该事务结果（虽然实际测试中通常不会出问题，但依赖这个"凑巧"行为是不稳健的）。此外，每个请求打开两个连接也造成资源浪费。

**修复建议**：将 `get_current_user_id` 的签名改为接受 `db` 参数而非再次 `Depends`：
```python
def get_current_user_id(db: sqlite3.Connection) -> int:
    ...

@app.get("/api/kanban")
def get_kanban(db=Depends(get_db)):
    user_id = get_current_user_id(db)
    board_id = get_user_board_id(user_id, db)
    ...
```

---

### 🟡 BUG-3：`test_db.py` 中的 `_connect` 与 `app.db._connect` 行为不同

**文件**: `backend/tests/test_db.py:32-36`

```python
def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
```

测试文件复制了 `app.db._connect` 的实现，而没有直接导入。若后者未来增加行为（如设置 `timeout`、`isolation_level`、`check_same_thread` 等），测试副本不会同步，可能导致测试与生产行为不一致。

**修复建议**：直接导入：
```python
from app.db import _connect
```

---

### 🟡 BUG-4：`KanbanBoard` 的 `useEffect` board 同步逻辑有竞争隐患

**文件**: `frontend/src/components/KanbanBoard.tsx:53-57`

```typescript
useEffect(() => {
  if (board) {
    setLocalBoard(board);
  }
}, [board]);
```

当用户正在拖拽卡片（`activeCardId !== null`）的过程中，若父组件触发了保存响应并更新 `board` prop，这个 `useEffect` 会立刻覆盖 `localBoard`，打断进行中的拖拽并可能导致闪烁或状态错乱。

**修复建议**：拖拽期间跳过同步：
```typescript
useEffect(() => {
  if (board && !activeCardId) {
    setLocalBoard(board);
  }
}, [board, activeCardId]);
```

---

### 🟢 BUG-5：`KanbanCardPreview` 与 `KanbanCard` 存在 JSX 结构重复

**文件**: `frontend/src/components/KanbanCard.tsx`、`KanbanCardPreview.tsx`

两个组件的 JSX 结构几乎相同（均渲染 `article > div > h4 + p`），唯一区别是 `KanbanCardPreview` 没有删除按钮和 DnD hooks。这不是 Bug，但是重复代码，一旦卡片样式需要修改需要改两处。

---

## 三、代码质量

### 🟡 QUAL-1：`validate_board_state` 函数嵌套过深，圈复杂度高

**文件**: `backend/app/kanban_schema.py:36-115`

该函数 80 行、嵌套最深达 4 层循环/条件，圈复杂度约 14，超出建议上限（10）。虽然逻辑清晰，但难以单独测试内部分支。

**建议**：提取 `_validate_column` 和 `_validate_card` 为辅助函数，减少主函数层级。

---

### 🟡 QUAL-2：`isCard` 类型守卫定义在组件函数体内

**文件**: `frontend/src/components/KanbanBoard.tsx:41`

```typescript
const isCard = (card: Card | undefined): card is Card => Boolean(card);
```

每次组件渲染都重新创建这个函数对象。将其提升到组件外可避免无意义的重新分配。

**修复建议**：
```typescript
// 组件外部
const isCard = (card: Card | undefined): card is Card => Boolean(card);
```

---

### 🟢 QUAL-3：`__testables` 导出模式固化了内部实现接口

**文件**: `frontend/src/lib/kanbanApi.ts:143-147`

```typescript
export const __testables = {
  toBoardData,
  toApiBoardState,
  resolveApiBaseUrl,
};
```

通过 `__testables` 暴露私有函数是为了让单元测试可以直接断言内部转换逻辑，这是合理的权衡，但意味着 `toBoardData`、`toApiBoardState`、`resolveApiBaseUrl` 的签名已经成为隐式公共接口，重构时需同步更新测试。

---

### 🟢 QUAL-4：`docker-compose.yml` 无数据持久化卷

**文件**: `docker-compose.yml`

```yaml
services:
  pm-app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
```

无 `volumes` 声明，容器重启后 `backend/data/pm.db` 会丢失。对于演示可以接受，但用户若不知情可能认为数据已持久化。

**建议**：
```yaml
volumes:
  - ./backend/data:/app/backend/data
```

---

## 四、测试

### 🟡 TEST-1：Windows 上 `tmp_path` 清理触发 `PermissionError`

**文件**: `backend/tests/test_main.py:12-13`

```python
if db_path.exists():
    db_path.unlink()
```

`TestClient` 的 lifespan 上下文管理器在 teardown 结束后仍持有 SQLite 连接（Windows 文件锁），导致 `unlink` 抛出 `PermissionError: [WinError 32]`。测试本身全部通过，但 teardown 错误会在 CI 报告中产生噪音，且可能掩盖真正的清理失败。

**修复建议**：pytest 的 `tmp_path` 会在会话结束后自动清理临时目录，fixture 中不需要手动删除文件；若确实需要手动清理，用 `shutil.rmtree(tmp_path, ignore_errors=True)` 代替 `unlink`。

---

### 🟡 TEST-2：E2E 缺少"刷新后数据持久化"用例

**文件**: `frontend/tests/kanban.spec.ts`

PLAN.md Part 7 验收标准明确要求：

> 单条 e2e 主链路：修改看板 -> 刷新页面 -> 数据仍在

但 `kanban.spec.ts` 中的 4 条测试均未覆盖此场景。这是最核心的持久化验证，目前只有后端集成测试（`test_update_and_get_kanban`）间接验证了数据库层的持久化，前端到后端的端到端持久化路径未被 E2E 覆盖。

---

### 🟡 TEST-3：`vitest.config.ts` 未设置覆盖率门槛

**文件**: `frontend/vitest.config.ts:11-13`

```typescript
coverage: {
  reporter: ["text", "html"],
}
```

后端 `pyproject.toml` 中配置了 `--cov-fail-under=80`，但前端 vitest 配置没有设置 `coverage.thresholds`，前端覆盖率没有强制门槛，CI 不会因覆盖率不足而失败。

**建议**：
```typescript
coverage: {
  reporter: ["text", "html"],
  thresholds: { lines: 80 },
}
```

---

### 🟢 TEST-4：`moveCard` 缺少边界用例

**文件**: `frontend/src/lib/kanban.test.ts`

当前 3 条测试覆盖了正常路径（同列重排、跨列移动、拖入空列末尾），但以下边界情况未测试：

- `activeId` 不存在于任何列时应返回原始 columns（函数有此保护，但未测试）
- `active.id === over.id` 时的幂等性（DnD 框架层面有处理，但 `moveCard` 本身未测试）
- `oldIndex === newIndex` 时返回原始 columns（函数有此保护，但未测试）

---

### 🟢 TEST-5：`playwright.config.ts` 的 E2E 测试只启动前端，不启动后端

**文件**: `frontend/playwright.config.ts:13-18`

```typescript
webServer: {
  command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
  url: "http://127.0.0.1:3000",
}
```

只自动启动前端 dev server（`:3000`），没有启动后端（`:8000`）。当前 Playwright 测试之所以能通过，是因为 `reuseExistingServer: true` 要求手动预先启动后端，或者测试依赖 `initialData`（加载失败时的回退数据）。若后端未运行，测试会静默使用前端种子数据，无法验证真实的持久化链路。

---

## 五、架构与设计

### 🟡 ARCH-1：`migrate_legacy_three_column_state` 的副作用触发在 GET 请求中

**文件**: `backend/app/main.py:170-177`

```python
@app.get("/api/kanban")
def get_kanban(...):
    migrated_state = migrate_legacy_three_column_state(state_data["state"])
    if migrated_state is not None:
        migrated_version = save_board_state(db, board_id, migrated_state)  # ← 写入
```

`GET` 请求触发了数据库写操作（`save_board_state`），违反了 HTTP 幂等性语义。若客户端因网络问题重试 GET，会多次触发迁移写入，版本号每次递增（虽然内容相同）。

迁移逻辑更适合放在 `POST` 请求的读取阶段或应用启动时执行一次。

---

### 🟢 ARCH-2：`board_states` 表只增不减，长期运行会无限增长

**文件**: `backend/app/db.py`

每次看板更新都 INSERT 一条新记录，没有任何清理机制。单用户 MVP 场景下增长缓慢，但若未来支持多用户或高频自动保存，表会持续膨胀。

**建议**：实现一个定期保留最近 N 个版本的清理任务，或在写入时删除旧版本（仅保留最新 K 条）。

---

### 🟢 ARCH-3：前端保存策略是"每次改动立即发起请求"，无批量/防抖机制

**文件**: `frontend/src/app/page.tsx:89-92`

```typescript
const handleBoardChange = (nextBoard: BoardData) => {
  setBoard(nextBoard);
  void persistBoard(nextBoard);  // 每次改动都发请求
};
```

每次列重命名按键、每次卡片拖放都立即触发一个 POST 请求。对于列标题 `<input>` 的 `onChange`，用户输入中的每个字符都会发起一次保存请求，产生大量无效的中间状态写入。

**建议**：对 `persistBoard` 添加 debounce（300-500ms），或区分"即时保存"（拖放）和"延迟保存"（文本输入）。

---

## 六、文档

### 🟡 DOC-1：`backend/backend_AGENTS.md` 内容严重滞后

**文件**: `backend/backend_AGENTS.md`

该文件描述的是 Part 2 阶段的后端结构（仅 Hello World 和健康检查），而当前代码已包含完整的数据库层、看板 CRUD API、迁移逻辑。文档与代码之间存在严重脱节，可能误导后续开发者。

---

### 🟢 DOC-2：`PLAN.md` 中 Part 8/9/10 标记为完成但代码不存在

**文件**: `docs/PLAN.md:209-270`

计划中 Part 8（OpenRouter 客户端）、Part 9（结构化 AI 输出）、Part 10（AI 侧边栏）的多个子项标记为 `[x]`，但在当前代码库中均不存在对应实现（git 状态显示 `openrouter_client.py`、`ai_structured_output.py`、相关测试文件均被删除）。

如果这些功能已被移除或推迟，PLAN.md 中对应项应更新状态说明。

---

## 七、问题汇总

| ID | 严重性 | 类别 | 文件 | 摘要 |
|---|---|---|---|---|
| SEC-1 | 🔴 高 | 安全 | `app/main.py:36` | `password_hash` 列存储明文密码 |
| SEC-2 | 🔴 高 | 安全 | `app/main.py:196` | 异常信息直接暴露给客户端 |
| SEC-3 | 🟡 中 | 安全 | `app/main.py` | API 路由无认证保护（MVP 已知权衡） |
| SEC-4 | 🟡 中 | 安全 | `app/main.py:133-135` | CORS 使用通配符方法和头 |
| BUG-1 | 🔴 高 | 正确性 | `app/db.py:87-101` | 并发写入版本号竞争导致唯一键冲突 |
| BUG-2 | 🔴 高 | 正确性 | `app/main.py:89,161` | 同请求创建两个 DB 连接 |
| BUG-3 | 🟡 中 | 正确性 | `tests/test_db.py:32` | 测试中复制了 `_connect` 实现而非导入 |
| BUG-4 | 🟡 中 | 正确性 | `KanbanBoard.tsx:53` | 拖拽中 board prop 变化会打断交互 |
| BUG-5 | 🟢 低 | 重复代码 | `KanbanCard/Preview.tsx` | JSX 结构重复 |
| QUAL-1 | 🟡 中 | 可维护性 | `kanban_schema.py:36` | `validate_board_state` 圈复杂度过高 |
| QUAL-2 | 🟡 中 | 性能 | `KanbanBoard.tsx:41` | `isCard` 函数在渲染函数体内定义 |
| QUAL-3 | 🟢 低 | 设计 | `kanbanApi.ts:143` | `__testables` 固化了内部实现接口 |
| QUAL-4 | 🟢 低 | 运维 | `docker-compose.yml` | 无持久化卷，容器重启丢数据 |
| TEST-1 | 🟡 中 | 测试 | `test_main.py:12` | Windows teardown `PermissionError` |
| TEST-2 | 🟡 中 | 测试 | `kanban.spec.ts` | 缺少"刷新后数据持久化"E2E 用例 |
| TEST-3 | 🟡 中 | 测试 | `vitest.config.ts` | 前端无覆盖率门槛 |
| TEST-4 | 🟢 低 | 测试 | `kanban.test.ts` | `moveCard` 缺少边界用例 |
| TEST-5 | 🟢 低 | 测试 | `playwright.config.ts` | E2E 不自动启动后端 |
| ARCH-1 | 🟡 中 | 架构 | `app/main.py:170` | GET 请求中有写副作用（迁移） |
| ARCH-2 | 🟢 低 | 架构 | `app/db.py` | `board_states` 只增不减 |
| ARCH-3 | 🟢 低 | 架构 | `page.tsx:89` | 每次输入变化都触发保存请求 |
| DOC-1 | 🟡 中 | 文档 | `backend_AGENTS.md` | 内容严重滞后于当前代码 |
| DOC-2 | 🟢 低 | 文档 | `docs/PLAN.md` | 已删除的 AI 功能仍标记为完成 |

---

## 八、优先修复建议

### 本次迭代应修复（🔴 高优先级）

1. **SEC-1**：将 `DEFAULT_PASSWORD_HASH` 改为存储 SHA-256 哈希值（5 分钟）
2. **SEC-2**：捕获异常时只返回通用错误信息，详情写日志（5 分钟）
3. **BUG-1**：用事务或原子 INSERT 解决并发版本号竞争（30 分钟）
4. **BUG-2**：将 `get_current_user_id` 改为参数传递 `db`，消除双连接（15 分钟）

### 本次迭代建议修复（🟡 中优先级）

5. **TEST-1**：移除 fixture 中手动 `unlink`，依赖 pytest `tmp_path` 自动清理（10 分钟）
6. **TEST-2**：补充"修改卡片 → 刷新 → 数据仍在"的 E2E 用例（30 分钟）
7. **TEST-3**：`vitest.config.ts` 添加 `thresholds: { lines: 80 }`（5 分钟）
8. **SEC-4**：CORS 改为白名单方法（5 分钟）
9. **ARCH-1**：将迁移逻辑移出 GET handler（30 分钟）
10. **DOC-1**：更新 `backend_AGENTS.md` 至当前代码状态（20 分钟）
11. **BUG-4**：拖拽期间跳过 board prop 同步（10 分钟）

### 后续迭代可选优化（🟢 低优先级）

- **QUAL-4**：`docker-compose.yml` 添加持久化卷
- **QUAL-2**：将 `isCard` 提升到组件外
- **ARCH-3**：对文本输入添加 debounce 保存
- **ARCH-2**：实现 `board_states` 版本清理策略
- **BUG-5**：提取共享的卡片内容组件
