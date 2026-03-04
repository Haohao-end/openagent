# 📁 LLMOps 项目结构

整理后的项目目录结构清晰明了，便于维护和查找。

## 🌲 目录树

```
llmops/
├── 📄 README.md                    # 项目主文档（英文）
├── 📄 README_ZH.md                 # 项目主文档（中文）
├── 📄 CLAUDE.md                    # Claude AI 项目指令
├── 📄 .gitignore                   # Git 忽略配置
├── 📄 .dockerignore                # Docker 忽略配置
│
├── 📂 api/                         # 后端代码（Python Flask）
│   ├── app/                        # 应用入口
│   ├── internal/                   # 核心业务逻辑
│   │   ├── handler/               # HTTP 请求处理器
│   │   ├── service/               # 业务逻辑层
│   │   ├── model/                 # 数据库模型
│   │   ├── schema/                # 数据验证模式
│   │   ├── core/                  # 核心功能
│   │   │   ├── agent/            # Agent 实现
│   │   │   ├── workflow/         # 工作流引擎
│   │   │   ├── language_model/   # LLM 集成
│   │   │   └── tools/            # 内置工具
│   │   └── ...
│   ├── pkg/                       # 可复用包
│   ├── config/                    # 配置管理
│   ├── test/                      # 测试套件
│   ├── requirements.txt           # Python 依赖
│   └── .env.example              # 环境变量模板
│
├── 📂 ui/                          # 前端代码（Vue 3）
│   ├── src/
│   │   ├── views/                # 页面组件
│   │   ├── components/           # 可复用组件
│   │   ├── services/             # API 客户端
│   │   ├── stores/               # 状态管理
│   │   ├── router/               # 路由配置
│   │   └── ...
│   ├── package.json              # Node 依赖
│   └── vite.config.ts            # Vite 配置
│
├── 📂 docker/                      # Docker 配置
│   ├── docker-compose.yml        # 服务编排
│   ├── nginx/                    # Nginx 配置
│   │   ├── nginx.conf
│   │   └── conf.d/
│   ├── .env.example              # Docker 环境变量
│   ├── README.md                 # Docker 文档
│   └── SECURITY.md               # 安全指南
│
├── 📂 docs/                        # 📚 文档中心
│   ├── 📄 README.md               # 文档索引（重要！）
│   │
│   ├── 📂 deployment/             # 🚀 部署文档
│   │   ├── DEPLOYMENT.md         # 完整部署指南
│   │   ├── QUICKSTART_GUIDE.md   # 快速开始
│   │   └── ...
│   │
│   ├── 📂 development/            # 💻 开发文档
│   │   ├── AGENTS.md             # Agent 开发
│   │   ├── API_CONFIG_SUMMARY.md # API 配置
│   │   ├── FRONTEND_IMPLEMENTATION_GUIDE.md
│   │   └── ...
│   │
│   ├── 📂 features/               # ✨ 功能文档
│   │   ├── ICON_GENERATION_COMPLETE_GUIDE.md
│   │   ├── IF_ELSE_ARCHITECTURE.md
│   │   └── ...
│   │
│   ├── 📂 bugfix/                 # 🐛 Bug 修复记录
│   │   ├── BUGFIX.md
│   │   ├── BUG_FIX_REPORT.md
│   │   └── ...
│   │
│   ├── 📂 testing/                # 🧪 测试文档
│   │   ├── TEST_GUIDE.md
│   │   └── ...
│   │
│   ├── 📂 summary/                # 📝 开发总结
│   │   ├── FINAL_SUMMARY.md
│   │   ├── COMPLETE_SUMMARY.md
│   │   └── ...
│   │
│   └── 📄 其他文档...             # 插件、图像生成等
│
├── 📂 scripts/                     # 🔧 实用脚本
│   ├── 📄 README.md               # 脚本说明（重要！）
│   ├── deploy-server.sh          # 服务器部署
│   ├── verify-api-config.sh      # API 配置验证
│   ├── verify_password_rules.sh  # 密码规则验证
│   ├── verify_plugins.sh         # 插件验证
│   └── push-to-github.sh         # GitHub 推送指南
│
├── 📂 deploy/                      # 部署配置
│   └── docker-compose.app.yaml   # 应用部署配置
│
├── 📂 storage/                     # 存储目录
├── 📂 logs/                        # 日志目录
└── 📂 tmp/                         # 临时文件

```

## 📊 统计信息

- **总文档数**: 56 个 Markdown 文档
- **脚本数量**: 5 个实用脚本
- **文档分类**:
  - 部署文档: 6 个
  - 开发文档: 10 个
  - 功能文档: 6 个
  - Bug 修复: 8 个
  - 测试文档: 3 个
  - 开发总结: 11 个
  - 其他文档: 12 个

## 🎯 快速导航

### 我想...

| 需求 | 查看文档 |
|------|---------|
| 🚀 部署项目 | [docs/deployment/QUICKSTART_GUIDE.md](docs/deployment/QUICKSTART_GUIDE.md) |
| 💻 开发 Agent | [docs/development/AGENTS.md](docs/development/AGENTS.md) |
| ⚙️ 配置 API | [docs/development/API_CONFIG_SUMMARY.md](docs/development/API_CONFIG_SUMMARY.md) |
| 🔧 运行脚本 | [scripts/README.md](scripts/README.md) |
| 📚 浏览所有文档 | [docs/README.md](docs/README.md) |
| 🐛 查看 Bug 历史 | [docs/bugfix/](docs/bugfix/) |
| 🧪 运行测试 | [docs/testing/TEST_GUIDE.md](docs/testing/TEST_GUIDE.md) |

## ✨ 整理成果

### ✅ 完成的工作

1. **根目录清理**
   - 只保留 3 个核心文档（README.md, README_ZH.md, CLAUDE.md）
   - 移除了 47 个散乱的文档文件
   - 保留了核心目录（api/, ui/, docker/）

2. **文档分类整理**
   - 创建了 6 个文档分类目录
   - 所有文档按用途归类
   - 创建了文档索引（docs/README.md）

3. **脚本集中管理**
   - 所有脚本移至 scripts/ 目录
   - 创建了脚本说明文档
   - 便于查找和使用

4. **文档链接更新**
   - 更新了 README.md 中的文档链接
   - 确保所有引用正确

5. **创建索引文档**
   - docs/README.md - 文档中心索引
   - scripts/README.md - 脚本使用说明
   - PROJECT_STRUCTURE.md - 项目结构说明

### 🎨 整理原则

1. **清晰性**: 目录结构一目了然
2. **可维护性**: 文档分类便于更新
3. **可发现性**: 通过索引快速找到所需文档
4. **一致性**: 统一的命名和组织方式

## 📝 维护建议

### 添加新文档时

1. 确定文档类型（部署/开发/功能/Bug/测试/总结）
2. 放入对应的 docs/ 子目录
3. 更新 docs/README.md 索引
4. 如果是重要文档，在主 README.md 中添加链接

### 添加新脚本时

1. 放入 scripts/ 目录
2. 添加可执行权限：`chmod +x script_name.sh`
3. 在 scripts/README.md 中添加说明
4. 遵循脚本开发规范

## 🔗 相关链接

- **在线 Demo**: http://82.157.66.198/
- **API 文档**: https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417
- **详细文档**: https://deepwiki.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents
- **GitHub**: https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents

---

**整理日期**: 2026-03-04  
**整理人**: Claude AI Assistant
