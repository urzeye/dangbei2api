# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-06-17

### 新增特性 🚀

#### 生产级特性
- **连接池管理**：使用全局 `httpx.AsyncClient` 复用 HTTP 连接，显著提升性能
- **资源自动管理**：通过 `async with` 上下文管理器自动清理资源，修复潜在的资源泄漏
- **结构化日志**：集成 `structlog`，支持彩色输出和 JSON 格式（生产环境）
- **统一错误处理**：OpenAI 兼容的错误响应格式，全局异常捕获
- **健康检查**：新增 `/health` 端点，支持 Docker/Kubernetes 健康探测
- **限流保护**：集成 `slowapi`，可配置请求频率限制，防止滥用
- **会话持久化**：可选 SQLite 存储（默认内存），支持服务重启后恢复会话

#### 性能优化
- **模型列表缓存**：避免频繁请求当贝 API，默认缓存 1 小时
- **后台任务**：定期清理过期会话，避免每次请求时执行 O(n) 遍历
- **生命周期管理**：正确的应用启动/关闭流程，优雅清理资源

#### 配置管理
- **pydantic-settings**：统一配置管理，支持类型验证和默认值
- **环境变量分组**：清晰的配置分类（服务器、会话、性能、日志、限流）
- **完整文档**：详细的配置说明和示例

#### 部署改进
- **优化 Dockerfile**：添加健康检查、curl 工具、数据目录
- **Docker Compose**：一键启动，支持持久化存储和资源限制
- **改进 .dockerignore**：减小镜像体积

### 代码质量 📝

- **消除重复代码**：提取 `utils.py` 公共函数
- **完善类型注解**：使用 Python 3.10+ 类型语法
- **模块化设计**：
  - `settings.py` - 统一配置管理
  - `logger.py` - 结构化日志
  - `errors.py` - 统一错误处理
  - `session_store.py` - 会话存储抽象
  - `utils.py` - 工具函数
- **API 文档增强**：完善 Pydantic 模型描述，自动生成 OpenAPI 文档

### 破坏性变更 ⚠️

- **配置文件重命名**：`app/config.py` → `app/settings.py`
- **导入路径变更**：需要从 `app.settings` 导入 `settings` 对象
- **环境变量新增**：建议查看 `.env.example` 更新配置

### 依赖更新

新增依赖：
- `pydantic-settings>=2.0.0` - 配置管理
- `structlog>=24.0.0` - 结构化日志
- `slowapi>=0.1.9` - 限流保护
- `aiosqlite>=0.19.0` - SQLite 异步支持

### 文档改进 📚

- 更新 README.md，新增 v0.2.0 特性说明
- 完善配置说明表格
- 添加 Docker Compose 快速开始指南
- 补充环境变量完整文档

---

## [0.1.0] - 2024-12-XX

### 初始版本

- OpenAI 兼容 API（`/v1/chat/completions`、`/v1/responses`）
- 模型列表端点（`/v1/models`）
- 会话管理（基于内存）
- 支持联网搜索和深度思考
- 匿名模式支持
- Docker 部署支持
