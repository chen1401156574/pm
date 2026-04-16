# 后端代理说明

## 范围

该目录包含 PM MVP 的 FastAPI 后端服务。  
第 2 部分刻意保持后端最小化：

- 在 `/` 返回静态 HTML，用于 Hello World 验证。
- 在 `/api/health` 提供 JSON 健康检查接口。

## 目录结构

- `app/main.py`
  - FastAPI 应用实例与路由定义。
- `tests/test_main.py`
  - 使用 `fastapi.testclient` 的基础接口测试。
- `pyproject.toml`
  - 运行时依赖与测试依赖配置。

## 运行

在 `backend/` 目录下执行：

```bash
uv pip install --system -e ".[dev]"
uvicorn app.main:app --reload
```

## 测试

在 `backend/` 目录下执行：

```bash
pytest
```
