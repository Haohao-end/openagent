# 文档索引

本目录存放基于 OpenAgent 当前源码的项目文档。

## 文档指南

- [API Key](api-keys.zh-CN.md)：当前支持的权限范围、失效时间、最后使用时间和密钥明文展示规则。
- [实时执行 Trace](trace.zh-CN.md)：事件生命周期、时间线行为，以及 Trace 不会从聊天历史恢复的原因。
- [架构说明](architecture.zh-CN.md)：组件关系、源码目录、典型请求链路和本地开发边界。
- [可编辑架构图](architecture.drawio)：包含系统概览、API、前端、Agent 执行、工作流执行和 Compose 基础设施视图。
- [English architecture guide](architecture.md)：对应的英文版本。
- [English documentation index](README.md)：英文文档索引。

## 文档维护约定

- 当源码结构或开发命令发生变化时，同步维护中英文文档。
- 链接必须指向当前默认分支中实际存在的仓库路径。
- 明确区分当前代码已有行为与规划中的未来能力。
- 本地开发优先运行针对性回归测试，并仅启动必要的 Docker 基础设施；不要暗示每次修改都必须构建完整应用容器。

项目概览和环境配置参见[英文 README](../README.md)、[中文 README](../README_ZH.md)及 [Docker 配置说明](../docker/README.md)。
