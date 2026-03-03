#!/bin/bash

# 安全检查脚本
# 用途: 检查是否有敏感信息被意外提交

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "  LLMOps 安全检查"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ISSUES_FOUND=0

# 1. 检查 .env 文件是否被 Git 跟踪
echo "1. 检查 .env 文件是否被 Git 跟踪..."
if git ls-files --error-unmatch "$PROJECT_ROOT/api/.env" 2>/dev/null; then
    echo -e "${RED}❌ 错误: api/.env 文件被 Git 跟踪！${NC}"
    echo "   请执行: git rm --cached api/.env"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✓ api/.env 未被 Git 跟踪${NC}"
fi

if git ls-files --error-unmatch "$SCRIPT_DIR/.env" 2>/dev/null; then
    echo -e "${RED}❌ 错误: docker/.env 文件被 Git 跟踪！${NC}"
    echo "   请执行: git rm --cached docker/.env"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✓ docker/.env 未被 Git 跟踪${NC}"
fi
echo ""

# 2. 检查 entrypoint.sh 中是否有硬编码的敏感信息
echo "2. 检查 entrypoint.sh 中的敏感信息..."
SENSITIVE_PATTERNS=(
    "sk-[a-zA-Z0-9]{20,}"  # OpenAI/DeepSeek API Keys
    "ghp_[a-zA-Z0-9]{36}"  # GitHub Personal Access Token
    "gho_[a-zA-Z0-9]{36}"  # GitHub OAuth Token
    "AKIA[0-9A-Z]{16}"     # AWS Access Key
    "[0-9]{10,}:[a-zA-Z0-9_-]{35}"  # Telegram Bot Token
)

FOUND_SENSITIVE=0
for pattern in "${SENSITIVE_PATTERNS[@]}"; do
    if grep -qE "$pattern" "$PROJECT_ROOT/api/docker/entrypoint.sh" 2>/dev/null; then
        echo -e "${RED}❌ 发现敏感信息模式: $pattern${NC}"
        FOUND_SENSITIVE=1
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
done

if [ $FOUND_SENSITIVE -eq 0 ]; then
    echo -e "${GREEN}✓ entrypoint.sh 中未发现敏感信息${NC}"
fi
echo ""

# 3. 检查 docker-compose.yaml 中是否有硬编码的 API Keys
echo "3. 检查 docker-compose.yaml 中的 API Keys..."
if grep -qE "(OPENAI_API_KEY|DEEPSEEK_API_KEY|MOONSHOT_API_KEY|CLAUDE_API_KEY):\s*sk-" "$SCRIPT_DIR/docker-compose.yaml" 2>/dev/null; then
    echo -e "${RED}❌ 错误: docker-compose.yaml 中发现硬编码的 API Keys！${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✓ docker-compose.yaml 中未发现硬编码的 API Keys${NC}"
fi
echo ""

# 4. 检查 Git 暂存区中的敏感信息
echo "4. 检查 Git 暂存区中的敏感信息..."
if git diff --cached | grep -qE "(sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{36}|AKIA[0-9A-Z]{16})" 2>/dev/null; then
    echo -e "${RED}❌ 警告: Git 暂存区中发现疑似敏感信息！${NC}"
    echo "   请检查: git diff --cached"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✓ Git 暂存区未发现敏感信息${NC}"
fi
echo ""

# 5. 检查 .gitignore 是否包含 .env
echo "5. 检查 .gitignore 配置..."
if ! grep -q "^\.env$" "$PROJECT_ROOT/.gitignore" 2>/dev/null && \
   ! grep -q "^\.env$" "$PROJECT_ROOT/api/.gitignore" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  警告: .gitignore 中未找到 .env 规则${NC}"
    echo "   建议添加: echo '.env' >> .gitignore"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✓ .gitignore 已配置 .env 规则${NC}"
fi
echo ""

# 6. 检查必需的配置文件是否存在
echo "6. 检查必需的配置文件..."
if [ ! -f "$PROJECT_ROOT/api/.env" ]; then
    echo -e "${YELLOW}⚠️  警告: api/.env 文件不存在${NC}"
    echo "   容器将使用 entrypoint.sh 中的默认配置"
    echo "   建议: cp api/.env.example api/.env"
fi

if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo -e "${YELLOW}⚠️  警告: docker/.env 文件不存在${NC}"
    echo "   将使用 docker-compose.yaml 中的默认值"
    echo "   建议: cp docker/.env.example docker/.env"
fi
echo ""

# 7. 总结
echo "=========================================="
echo "  检查完成"
echo "=========================================="
if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}✅ 未发现安全问题！${NC}"
    exit 0
else
    echo -e "${RED}❌ 发现 $ISSUES_FOUND 个安全问题，请修复后再提交代码！${NC}"
    echo ""
    echo "常见修复方法:"
    echo "  1. 移除 Git 跟踪: git rm --cached <file>"
    echo "  2. 撤销暂存: git reset HEAD <file>"
    echo "  3. 修改文件: 移除硬编码的敏感信息"
    echo "  4. 更新 .gitignore: echo '.env' >> .gitignore"
    echo ""
    echo "详细安全指南: docker/SECURITY.md"
    exit 1
fi
