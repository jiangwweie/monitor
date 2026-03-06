# ==========================================
# CryptoRadar Docker 部署指南
# ==========================================

## 快速开始

### 1. 创建必要的目录

```bash
mkdir -p /Users/jiangwei/Documents/docker/monitor/{data,logs,config}
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp config/.env.example /Users/jiangwei/Documents/docker/monitor/.env

# 编辑配置文件，填入币安 API 密钥
vi /Users/jiangwei/Documents/docker/monitor/.env
# 或
nano /Users/jiangwei/Documents/docker/monitor/.env
```

### 3. 自定义端口（可选）

编辑 `.env` 文件：
```bash
BACKEND_PORT=9000      # 后端端口
FRONTEND_PORT=5176     # 前端端口
```

### 4. 启动服务

```bash
cd config
docker-compose up --build -d
```

### 5. 查看状态

```bash
# 查看运行状态
docker-compose ps

# 查看后端日志
docker-compose logs -f backend

# 查看前端日志
docker-compose logs -f frontend
```

### 6. 访问应用

- 前端地址：http://localhost:5174（或配置的 FRONTEND_PORT）
- 后端 API: http://localhost:8000（或配置的 BACKEND_PORT）
- API 文档：http://localhost:8000/docs

### 7. 停止服务

```bash
docker-compose down
```

---

## 目录结构

```
/Users/jiangwei/Documents/docker/monitor/
├── .env                    # 配置文件（从 .env.example 复制）
├── data/
│   └── radar.db           # SQLite 数据库
├── logs/
│   └── backend.log        # 后端日志
└── config/                # 配置文件备份
```

---

## 常见问题

### Q1: 端口冲突怎么办？

修改 `.env` 文件中的端口配置：
```bash
BACKEND_PORT=9000      # 改为其他可用端口
FRONTEND_PORT=5176     # 改为其他可用端口
```

然后重启：
```bash
docker-compose down
docker-compose up -d
```

### Q2: 如何升级版本？

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker-compose down
docker-compose up --build -d
```

### Q3: 如何备份数据？

```bash
# 备份数据库
cp /Users/jiangwei/Documents/docker/monitor/data/radar.db ./backup.db

# 备份配置
cp /Users/jiangwei/Documents/docker/monitor/.env ./backup.env
```

### Q4: 如何迁移到新机器？

1. 复制整个 `/Users/jiangwei/Documents/docker/monitor/` 目录
2. 确保新机器已安装 Docker 和 Docker Compose
3. 运行 `docker-compose up -d`

---

## 健康检查

```bash
# 检查后端健康
curl http://localhost:8000/api/system/status

# 检查前端
curl http://localhost:5174
```

---

## 网络说明

- 前端容器通过内部网络访问后端：`http://backend:8000`
- 外部访问通过端口映射：`localhost:5174` → `nginx:80` → `backend:8000`
