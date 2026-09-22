# Adaptive Tutor System

自适应教学系统（OpenMAIC 式场景课件生成 + 行为追踪 + AI 自适应辅导）。

## 目录说明
- `docker-compose.submission.yml`：评审运行用 Docker Compose 配置（含构建与端口映射）
- `.env.template`：环境变量模板，只包含占位项，不包含真实密钥
- `ENVIRONMENT_VARIABLES.md`：环境变量说明
- `CONFIDENTIALITY_NOTICE.md`：保密与使用限制说明
- `artifacts/`：已导出的 Docker 镜像 tar 文件（本地评审用，未纳入 git，因体积超过 GitHub 单文件限制）

## 环境要求
- 已安装 Docker（含 Docker Compose v2）
- 能够访问 Docker Hub（首次构建需拉取基础镜像；Dockerfile 已内置清华/阿里等国内镜像源）

## 部署教程（推荐方式：从源码构建）

### 1. 获取代码
```bash
git clone https://github.com/YCBRMSN-maker/Ai-Test.git
cd Ai-Test
```

### 2. 配置环境变量
```bash
cp .env.template .env
```
在 `.env` 中填写评审运行所需的 API Key 和模型配置（字段含义见 `ENVIRONMENT_VARIABLES.md`）。

### 3. 构建并启动（首次需几分钟）
```bash
docker compose --env-file .env -f docker-compose.submission.yml up -d --build
```

### 4. 验证运行状态
- 学生端：http://localhost:8325
- 教师端：http://localhost:8326
- 检查服务：
```bash
docker compose --env-file .env -f docker-compose.submission.yml ps
```
应看到 `backend`、`frontend`、`redis` 以及所有 `celery-*` 服务均处于运行状态。

> 后端首次启动会自动创建数据库表结构，无需手动执行建表脚本。

## 备用方式：离线导入预构建镜像
若本机无法联网构建（如评审环境隔离），可使用预构建镜像包（由项目方随压缩包分发，不在 git 仓库中）：
```bash
docker load -i artifacts/adaptive-tutor-system_backend_competition-v1.tar
docker load -i artifacts/adaptive-tutor-system_frontend_competition-v1.tar
docker compose --env-file .env -f docker-compose.submission.yml up -d
```

## 停止 / 清理
```bash
# 停止服务（保留数据卷）
docker compose --env-file .env -f docker-compose.submission.yml down
# 停止并删除数据卷（会清空数据库，谨慎）
docker compose --env-file .env -f docker-compose.submission.yml down -v
```
