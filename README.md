# Adaptive Tutor System

## 目录说明
- `docker-compose.submission.yml`：评审运行用 Docker Compose 配置
- `.env.template`：环境变量模板，只包含占位项，不包含真实密钥。
- `ENVIRONMENT_VARIABLES.md`：环境变量说明。
- `CONFIDENTIALITY_NOTICE.md`：保密与使用限制说明。
- `artifacts/`：已导出的 Docker 镜像 tar 文件与校验文件。

## 快速启动
1. 准备环境变量文件：
```bash
cp .env.template .env
# 在 .env 中填写评审运行所需的 API Key 和模型配置
```
2. 构建并启动服务（首次会自动构建后端/前端镜像，需几分钟；Dockerfile 已内置国内镜像源）：
```bash
docker compose --env-file .env -f docker-compose.submission.yml up -d --build
```
3. 验证运行状态：
- 前端访问地址：`http://localhost:8325`
- 执行 `docker compose --env-file .env -f docker-compose.submission.yml ps`，应看到 `backend`、`frontend`、`redis` 以及所有 `celery-*` 服务均处于运行状态。

> 说明：后端首次启动会自动创建数据库表结构（无需手动执行建表脚本）。
> 预构建镜像包位于 `artifacts/`（本地评审用，未纳入 git，因体积超过 GitHub 单文件限制）。
