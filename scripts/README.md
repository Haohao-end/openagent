# 🔧 Scripts - 实用脚本集合

本目录包含 LLMOps 项目的各种实用脚本。

## 📜 脚本列表

### 🚀 部署脚本

#### `deploy-server.sh`
**用途**: 服务器一键部署脚本

**功能**:
- 自动检查并安装 Docker 和 Git
- 克隆或更新代码仓库
- 配置环境变量
- 构建并启动 Docker 服务
- 执行健康检查

**使用方法**:
```bash
# 在服务器上运行
sudo bash scripts/deploy-server.sh

# 或者远程执行
bash <(curl -fsSL https://raw.githubusercontent.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents/main/scripts/deploy-server.sh)
```

**注意事项**:
- 需要 root 权限
- 会安装到 `/opt/llmops` 目录
- 首次运行需要配置 `api/.env` 文件

---

### ✅ 验证脚本

#### `verify-api-config.sh`
**用途**: 验证 API 配置和 Nginx 代理设置

**功能**:
- 检查环境变量配置
- 验证 Nginx 配置文件
- 检查 Docker Compose 配置
- 测试前端配置代码
- 运行时服务检查
- 网络连通性测试

**使用方法**:
```bash
bash scripts/verify-api-config.sh
```

**检查项目**:
- ✓ 环境变量配置 (`.env.development`, `.env.production`)
- ✓ Nginx 配置文件 (`nginx.conf`, `default.conf`, `proxy.conf`)
- ✓ Docker Compose 服务定义
- ✓ 前端 API 前缀配置
- ✓ 容器运行状态
- ✓ 网络连通性

---

#### `verify_password_rules.sh`
**用途**: 验证前后端密码规则一致性

**功能**:
- 检查后端密码正则表达式
- 检查前端密码正则表达式
- 对比前后端规则是否一致
- 测试常见密码案例

**使用方法**:
```bash
bash scripts/verify_password_rules.sh
```

**密码规则**:
- 至少一个字母（大小写均可）
- 至少一个数字
- 长度 8-16 位
- 可包含特殊字符

---

#### `verify_plugins.sh`
**用途**: 验证扩展插件文件完整性

**功能**:
- 检查插件配置文件
- 验证各个插件提供商目录和文件
- 统计验证结果

**使用方法**:
```bash
bash scripts/verify_plugins.sh
```

**检查的插件**:
- SerpAPI (搜索)
- Tavily (搜索)
- Arxiv (学术搜索)
- OpenWeatherMap (天气)
- News API (新闻)
- Wolfram Alpha (计算)
- Stability AI (图像生成)
- GitHub (代码仓库)
- Google/YouTube (搜索)

---

### 🔄 Git 相关

#### `push-to-github.sh`
**用途**: GitHub 推送指南脚本

**功能**:
- 显示 GitHub 推送步骤
- 提供三种推送方式：
  1. Personal Access Token
  2. SSH 密钥
  3. GitHub CLI

**使用方法**:
```bash
bash scripts/push-to-github.sh
```

**注意**: 这是一个指南脚本，不会自动推送代码，需要手动执行显示的命令。

---

## 🎯 使用场景

### 场景 1: 首次部署到服务器
```bash
# 1. 运行部署脚本
sudo bash scripts/deploy-server.sh

# 2. 验证配置
bash scripts/verify-api-config.sh
```

### 场景 2: 开发环境配置验证
```bash
# 验证 API 配置
bash scripts/verify-api-config.sh

# 验证密码规则
bash scripts/verify_password_rules.sh

# 验证插件
bash scripts/verify_plugins.sh
```

### 场景 3: 推送代码到 GitHub
```bash
# 查看推送指南
bash scripts/push-to-github.sh

# 然后按照提示操作
```

---

## 📝 脚本开发规范

如果您要添加新脚本，请遵循以下规范：

1. **文件命名**: 使用小写字母和下划线，如 `verify_something.sh`
2. **文件头部**: 添加脚本用途说明
3. **错误处理**: 使用 `set -e` 在错误时退出
4. **颜色输出**: 使用统一的颜色定义
   ```bash
   RED='\033[0;31m'
   GREEN='\033[0;32m'
   YELLOW='\033[1;33m'
   NC='\033[0m'
   ```
5. **帮助信息**: 提供清晰的使用说明
6. **可执行权限**: `chmod +x script_name.sh`
7. **文档更新**: 在本 README 中添加说明

---

## 🔒 安全注意事项

- 不要在脚本中硬编码敏感信息（API Keys、密码等）
- 使用环境变量或配置文件传递敏感数据
- 验证用户输入，防止注入攻击
- 对于需要 root 权限的脚本，明确提示用户

---

## 🐛 问题反馈

如果脚本运行出现问题，请：
1. 检查脚本执行权限
2. 查看错误输出信息
3. 确认依赖工具已安装（Docker、Git、curl 等）
4. 提交 Issue 到 GitHub

---

**最后更新**: 2026-03-04
