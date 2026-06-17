# 快速配置 GitHub Actions

## 第一步：配置 Docker Hub Secrets

### 1. 创建 Docker Hub Access Token

1. 登录 [Docker Hub](https://hub.docker.com/)
2. 进入 **Account Settings** → **Security**
3. 点击 **New Access Token**
4. 填写信息：
   - **Description**: `GitHub Actions`
   - **Access permissions**: 选择 **Read, Write, Delete**
5. 点击 **Generate**
6. **复制 Token**（只显示一次，请妥善保存）

### 2. 在 GitHub 仓库中添加 Secrets

1. 进入 GitHub 仓库页面：`https://github.com/urzeye/dangbei2api`
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**

#### 添加 DOCKERHUB_USERNAME

- **Name**: `DOCKERHUB_USERNAME`
- **Value**: `urzeye`（你的 Docker Hub 用户名）
- 点击 **Add secret**

#### 添加 DOCKERHUB_TOKEN

- **Name**: `DOCKERHUB_TOKEN`
- **Value**: 粘贴刚才复制的 Token
- 点击 **Add secret**

---

## 第二步：创建 Docker Hub 仓库

1. 登录 [Docker Hub](https://hub.docker.com/)
2. 点击 **Create Repository**
3. 填写信息：
   - **Name**: `dangbei2api`
   - **Visibility**: Public 或 Private
   - **Description**: 将当贝 AI 封装为 OpenAI 兼容 API
4. 点击 **Create**

---

## 第三步：发布第一个版本

### 方式 1：创建 Tag 触发自动发布

```bash
# 1. 确保本地代码已提交
git status

# 2. 创建 tag（版本号与 pyproject.toml 一致）
git tag v0.2.1

# 3. 推送 tag 到 GitHub
git push origin v0.2.1
```

### 方式 2：手动触发构建

1. 进入 GitHub 仓库页面
2. 点击 **Actions** 标签
3. 选择 **Build and Push Docker Image**
4. 点击 **Run workflow**
5. 选择 `main` 分支
6. 点击 **Run workflow**

---

## 第四步：验证发布结果

### 检查 GitHub Actions

1. 进入 **Actions** 标签
2. 查看工作流运行状态：
   - ✅ **Build and Push Docker Image**（约 3-5 分钟）
   - ✅ **Create Release**（约 30 秒）

### 检查 Docker Hub

1. 访问 `https://hub.docker.com/r/urzeye/dangbei2api`
2. 确认镜像已推送成功
3. 查看可用标签：`0.2.1`, `0.2`, `0`, `latest`

### 检查 GitHub Release

1. 进入 GitHub 仓库页面
2. 点击 **Releases**
3. 确认 `v0.2.1` Release 已创建

---

## 第五步：测试 Docker 镜像

```bash
# 拉取镜像
docker pull urzeye/dangbei2api:0.2.1

# 运行测试
docker run -d -p 8000:8000 --name test-dangbei2api urzeye/dangbei2api:0.2.1

# 健康检查
curl http://localhost:8000/health

# 查看日志
docker logs test-dangbei2api

# 清理测试容器
docker stop test-dangbei2api
docker rm test-dangbei2api
```

---

## 常见问题

### Q1: 推送 Docker 镜像失败

**错误**: `unauthorized: authentication required`

**解决方案**:
1. 检查 `DOCKERHUB_USERNAME` 是否正确
2. 检查 `DOCKERHUB_TOKEN` 是否有效
3. 重新生成 Token 并更新 Secret

### Q2: Docker Hub 仓库描述未更新

**原因**: `peter-evans/dockerhub-description` 需要额外的权限

**解决方案**:
1. 确认 Token 权限包含 **Read & Write**
2. 手动在 Docker Hub 编辑仓库描述

### Q3: GitHub Release 创建失败

**错误**: `Error: Resource not accessible by integration`

**解决方案**:
1. 检查工作流权限：Settings → Actions → General → Workflow permissions
2. 确保选择 **Read and write permissions**

### Q4: 多架构构建失败

**错误**: `ERROR: failed to solve: process "/bin/sh -c apk add..." did not complete successfully`

**解决方案**:
1. 检查 Dockerfile 中的包名是否正确
2. 使用 `apk search <package>` 查找可用包
3. 本地测试：`docker buildx build --platform linux/amd64,linux/arm64 .`

---

## 后续操作

### 每次发版流程

```bash
# 1. 更新版本号
# 修改：pyproject.toml, app/main.py, CHANGELOG.md

# 2. 提交代码
git add -A
git commit -m "chore: bump version to v0.2.2"
git push origin main

# 3. 创建 tag
git tag v0.2.2
git push origin v0.2.2

# 4. 等待 GitHub Actions 完成（自动）
# - 构建 Docker 镜像
# - 推送到 Docker Hub
# - 创建 GitHub Release
```

### 删除错误的 Tag

```bash
# 删除本地 tag
git tag -d v0.2.1

# 删除远程 tag
git push origin :refs/tags/v0.2.1
```

---

## 完成！

现在你已经成功配置了 GitHub Actions CI/CD 工作流，每次推送 tag 都会自动构建和发布 Docker 镜像。

**相关链接**:
- Docker Hub: `https://hub.docker.com/r/urzeye/dangbei2api`
- GitHub Actions: `https://github.com/urzeye/dangbei2api/actions`
- Releases: `https://github.com/urzeye/dangbei2api/releases`
