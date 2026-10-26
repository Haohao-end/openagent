# Documentation

This directory contains source-grounded documentation for OpenAgent.

## Guides

- [Architecture guide](architecture.md) — component map, repository source locations, representative request paths, and local development boundaries.
- [中文架构说明](architecture.zh-CN.md) — Chinese version of the same guide.
- [中文文档索引](README.zh-CN.md) — documentation index in Chinese.

## Documentation maintenance

- Keep English and Chinese guides aligned when source structure or development commands change.
- Link to repository paths that exist on the current default branch.
- Distinguish current code behavior from proposed or future capabilities.
- Prefer focused regression tests and the infrastructure-only Docker workflow for local development; do not imply that the full application containers must be built for every change.

See the [repository README](../README.md), [Chinese README](../README_ZH.md), and [Docker setup](../docker/README.md) for project overview and environment setup.
