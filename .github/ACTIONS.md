# GitHub Actions 配置说明

本项目使用 GitHub Actions 实现 CI/CD 自动化。

## 工作流列表

### 1. CI（持续集成）
**文件**: `.github/workflows/ci.yml`

**触发条件**:
- Push 到 `main` 分支
- Pull Request 到 `main` 分支

**功能**:
- 多版本 Python 测试（3.10、3.11、3.12）
- 检查代码导入
- Docker 镜像构建测试
- 健康检查验证

---

### 2. Docker 镜像构建与推送
**文件**: `.github/workflows/docker-publish.yml`

**触发条件**:
- 推送 `v*.*.*` 格式的 tag（如 `v0.2.1`）
- 手动触发（workflow_dispatch）

**功能**:
- 构建多架构镜像（amd64、arm64）
- 同时推送到两个镜像仓库：
  - **Docker Hub**: `urzeye/dangbei2api`
  - **GitHub Packages**: `ghcr.io/urzeye/dangbei2api`
- 自动生成镜像标签：
  - `v0.2.1`（完整版本号）
  - `v0.2`（次版本号）
  - `v0`（主版本号）
  - `latest`（最新版）
- 自动更新 Docker Hub 仓库描述

---

### 3. GitHub Release 自动创建
**文件**: `.github/workflows/release.yml`

**触发条件**:
- 推送 `v*.*.*` 格式的 tag

**功能**:
- 自动创建 GitHub Release
- 从 CHANGELOG.md 提取对应版本的更新日志
- 生成 Release Notes

---

## 配置 GitHub Secrets

在 GitHub 仓库中配置以下 Secrets（Settings → Secrets and variables → Actions）：

### 必需配置

1. **DOCKERHUB_USERNAME**
   - Docker Hub 用户名
   - 示例: `urzeye`

2. **DOCKERHUB_TOKEN**
   - Docker Hub Access Token（不是密码）
   - 获取方式: Docker Hub → Account Settings → Security → New Access Token

### 自动配置（无需手动添加）

- **GITHUB_TOKEN**: GitHub Actions 自动提供，用于推送到 GitHub Packages (ghcr.io)

### 获取 Docker Hub Token

```bash
# 1. 登录 Docker Hub
https://hub.docker.com/settings/security

# 2. 点击 "New Access Token"
# 3. 输入描述: "GitHub Actions"
# 4. 权限选择: Read, Write, Delete
# 5. 生成并复制 Token（只显示一次）

# 6. 在 GitHub 仓库中添加 Secrets
# Settings → Secrets and variables → Actions → New repository secret
# Name: DOCKERHUB_TOKEN
# Value: 粘贴刚才复制的 Token
```

---

## 发布新版本

### 完整发布流程

```bash
# 1. 更新版本号
# 修改以下文件中的版本号：
# - pyproject.toml
# - app/main.py
# - CHANGELOG.md

# 2. 提交代码
git add -A
git commit -m "chore: bump version to v0.2.1"
git push origin main

# 3. 创建并推送 tag
git tag v0.2.1
git push origin v0.2.1

# 4. GitHub Actions 自动执行：
# ✅ 构建 Docker 镜像
# ✅ 推送到 Docker Hub
# ✅ 创建 GitHub Release
# ✅ 更新 Docker Hub 描述
```

### 自动触发的流程

推送 tag 后，GitHub Actions 会自动：

1. **构建镜像**（约 3-5 分钟）
   - 构建 `linux/amd64` 和 `linux/arm64` 镜像
   - 推送到 Docker Hub

2. **创建 Release**（约 30 秒）
   - 从 CHANGELOG.md 提取更新内容
   - 创建 GitHub Release 页面

3. **更新 Docker Hub**（约 10 秒）
   - 同步 README.md 到 Docker Hub 仓库描述

---

## 使用已发布的镜像

### Docker Hub

```bash
# 拉取最新版本
docker pull urzeye/dangbei2api:latest

# 拉取指定版本
docker pull urzeye/dangbei2api:0.2.1

# 拉取次版本号（自动获取最新补丁版本）
docker pull urzeye/dangbei2api:0.2
```

### GitHub Packages (ghcr.io)

```bash
# 拉取最新版本
docker pull ghcr.io/urzeye/dangbei2api:latest

# 拉取指定版本
docker pull ghcr.io/urzeye/dangbei2api:0.2.1

# 拉取次版本号
docker pull ghcr.io/urzeye/dangbei2api:0.2
```

**选择建议**:
- 海外用户 → Docker Hub（网络更快）
- 国内用户 → 两者都可以尝试（部分地区 GHCR 更快）
- CI/CD 环境 → GitHub Packages（同一平台，更稳定）

### Docker Compose

```yaml
services:
  dangbei2api:
    image: urzeye/dangbei2api:0.2.1
    ports:
      - "8000:8000"
    environment:
      - API_KEY=your-secret-key
```

---

## 手动触发构建

如果需要手动触发 Docker 镜像构建（不创建 tag）：

1. 进入 GitHub 仓库页面
2. 点击 "Actions" 标签
3. 选择 "Build and Push Docker Image"
4. 点击 "Run workflow"
5. 选择分支并运行

---

## 故障排查

### 构建失败

**问题**: Docker 镜像构建失败

**解决方案**:
1. 检查 Dockerfile 语法
2. 本地测试构建: `docker build -t test .`
3. 查看 Actions 日志中的错误信息

### 推送失败

**问题**: 推送到 Docker Hub 失败

**解决方案**:
1. 检查 `DOCKERHUB_USERNAME` 和 `DOCKERHUB_TOKEN` 是否正确
2. 确认 Token 权限包含 "Write"
3. 检查 Docker Hub 仓库是否存在

### Release 创建失败

**问题**: GitHub Release 创建失败

**解决方案**:
1. 检查 CHANGELOG.md 格式是否正确
2. 确认版本号与 tag 匹配
3. 检查仓库权限设置

---

## 镜像标签说明

每次发版会自动生成多个标签：

| Tag | 说明 | 示例 |
|-----|------|------|
| `latest` | 最新稳定版 | `dangbei2api:latest` |
| `v{major}.{minor}.{patch}` | 完整版本号 | `dangbei2api:0.2.1` |
| `v{major}.{minor}` | 次版本号（自动更新到最新补丁） | `dangbei2api:0.2` |
| `v{major}` | 主版本号（自动更新到最新次版本） | `dangbei2api:0` |

**推荐使用**:
- 生产环境: 使用完整版本号（`0.2.1`）
- 测试环境: 使用次版本号（`0.2`）
- 开发环境: 使用 `latest`

---

## 多架构支持

镜像支持以下架构：
- `linux/amd64`（x86_64）
- `linux/arm64`（ARM64/aarch64）

Docker 会自动选择匹配当前系统的镜像。

---

## 维护建议

1. **版本号管理**: 遵循语义化版本（Semantic Versioning）
2. **CHANGELOG 更新**: 每次发版前更新 CHANGELOG.md
3. **测试验证**: 本地测试通过后再推送 tag
4. **回滚方案**: 保留多个历史版本镜像，便于快速回滚

---

## 相关链接

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker Hub](https://hub.docker.com/)
- [语义化版本规范](https://semver.org/lang/zh-CN/)
