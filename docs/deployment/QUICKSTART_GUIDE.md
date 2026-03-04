# 🚀 快速开始

## 📦 本地开发（WSL2）

### 1. 提交代码到 GitHub

```bash
cd /home/haohao/llmops

# 初始化 Git（如果需要）
git init
git remote add origin https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents.git

# 安全检查
bash docker/security-check.sh

# 提交代码
git add .
git commit -m "feat: 重构 Docker 配置，实现安全的环境变量管理"
git push -u origin main
```

### 2. 本地启动服务

```bash
cd docker
./start.sh
```

---

## 🌐 服务器部署

### 方式 1: 一键部署（推荐）

```bash
# SSH 连接到服务器
ssh root@82.157.66.198

# 下载并运行部署脚本
curl -fsSL https://raw.githubusercontent.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents/main/deploy-server.sh | bash

# 或者手动下载
wget https://raw.githubusercontent.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents/main/deploy-server.sh
bash deploy-server.sh
```

### 方式 2: 手动部署

```bash
# 1. 克隆代码
git clone https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents.git /opt/llmops
cd /opt/llmops

# 2. 配置环境变量
cp api/.env.example api/.env
vim api/.env  # 填入真实的 API Keys

# 3. 启动服务
cd docker
bash start.sh
```

---

## 🔄 更新部署

```bash
# 服务器上执行
cd /opt/llmops
git pull origin main
cd docker
docker compose down
docker compose build
docker compose up -d
```

---

## 📝 访问地址

- **前端**: http://your-server-ip:3000
- **API**: http://your-server-ip:5001
- **Nginx**: http://your-server-ip

---

## 🔍 常用命令

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f llmops-api

# 重启服务
docker compose restart

# 停止服务
docker compose stop
```

---

## 📚 详细文档

- [完整部署指南](./DEPLOYMENT.md)
- [安全配置说明](./docker/SECURITY.md)
- [Docker 配置文档](./docker/README.md)
- [项目架构说明](./CLAUDE.md)

---

## ⚠️ 重要提示

1. ✅ **api/.env** 必须配置真实的 API Keys
2. ✅ **docker/.env** 建议修改数据库密码
3. ✅ 生产环境请配置 HTTPS
4. ✅ 定期备份数据库和 volumes

---

**需要帮助？** 查看 [DEPLOYMENT.md](./DEPLOYMENT.md) 或提交 [Issue](https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents/issues)
