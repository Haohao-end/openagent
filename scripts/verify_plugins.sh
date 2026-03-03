#!/bin/bash

# 扩展插件验证脚本
# 用于验证所有新增插件文件是否正确创建

echo "=========================================="
echo "  LLMOps 扩展插件验证脚本"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 计数器
total=0
success=0
failed=0

# 检查函数
check_file() {
    local file=$1
    local desc=$2
    total=$((total + 1))

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $desc"
        success=$((success + 1))
    else
        echo -e "${RED}✗${NC} $desc (文件不存在: $file)"
        failed=$((failed + 1))
    fi
}

check_dir() {
    local dir=$1
    local desc=$2
    total=$((total + 1))

    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} $desc"
        success=$((success + 1))
    else
        echo -e "${RED}✗${NC} $desc (目录不存在: $dir)"
        failed=$((failed + 1))
    fi
}

BASE_DIR="api/internal/core/tools/builtin_tools"

echo "1. 检查配置文件..."
echo "---"
check_file "$BASE_DIR/categories/categories.yaml" "分类配置文件"
check_file "$BASE_DIR/providers/providers.yaml" "提供商配置文件"
echo ""

echo "2. 检查 SerpAPI 提供商..."
echo "---"
check_dir "$BASE_DIR/providers/serpapi" "SerpAPI 目录"
check_file "$BASE_DIR/providers/serpapi/__init__.py" "SerpAPI __init__.py"
check_file "$BASE_DIR/providers/serpapi/positions.yaml" "SerpAPI positions.yaml"
check_file "$BASE_DIR/providers/serpapi/serpapi_search.py" "SerpAPI 搜索插件"
check_file "$BASE_DIR/providers/serpapi/serpapi_search.yaml" "SerpAPI 搜索配置"
echo ""

echo "3. 检查 Tavily 提供商..."
echo "---"
check_dir "$BASE_DIR/providers/tavily" "Tavily 目录"
check_file "$BASE_DIR/providers/tavily/__init__.py" "Tavily __init__.py"
check_file "$BASE_DIR/providers/tavily/positions.yaml" "Tavily positions.yaml"
check_file "$BASE_DIR/providers/tavily/tavily_search.py" "Tavily 搜索插件"
check_file "$BASE_DIR/providers/tavily/tavily_search.yaml" "Tavily 搜索配置"
check_file "$BASE_DIR/providers/tavily/tavily_answer.py" "Tavily 答案插件"
check_file "$BASE_DIR/providers/tavily/tavily_answer.yaml" "Tavily 答案配置"
echo ""

echo "4. 检查 Arxiv 提供商..."
echo "---"
check_dir "$BASE_DIR/providers/arxiv" "Arxiv 目录"
check_file "$BASE_DIR/providers/arxiv/__init__.py" "Arxiv __init__.py"
check_file "$BASE_DIR/providers/arxiv/positions.yaml" "Arxiv positions.yaml"
check_file "$BASE_DIR/providers/arxiv/arxiv_search.py" "Arxiv 搜索插件"
check_file "$BASE_DIR/providers/arxiv/arxiv_search.yaml" "Arxiv 搜索配置"
echo ""

echo "5. 检查 OpenWeatherMap 提供商..."
echo "---"
check_dir "$BASE_DIR/providers/openweathermap" "OpenWeatherMap 目录"
check_file "$BASE_DIR/providers/openweathermap/__init__.py" "OpenWeatherMap __init__.py"
check_file "$BASE_DIR/providers/openweathermap/positions.yaml" "OpenWeatherMap positions.yaml"
check_file "$BASE_DIR/providers/openweathermap/openweathermap_weather.py" "OpenWeatherMap 天气插件"
check_file "$BASE_DIR/providers/openweathermap/openweathermap_weather.yaml" "OpenWeatherMap 天气配置"
echo ""

echo "6. 检查 News API 提供商..."
echo "---"
check_dir "$BASE_DIR/providers/newsapi" "News API 目录"
check_file "$BASE_DIR/providers/newsapi/__init__.py" "News API __init__.py"
check_file "$BASE_DIR/providers/newsapi/positions.yaml" "News API positions.yaml"
check_file "$BASE_DIR/providers/newsapi/newsapi_search.py" "News API 搜索插件"
check_file "$BASE_DIR/providers/newsapi/newsapi_search.yaml" "News API 搜索配置"
check_file "$BASE_DIR/providers/newsapi/newsapi_top_headlines.py" "News API 头条插件"
check_file "$BASE_DIR/providers/newsapi/newsapi_top_headlines.yaml" "News API 头条配置"
echo ""

echo "7. 检查 Wolfram Alpha 提供商..."
echo "---"
check_dir "$BASE_DIR/providers/wolframalpha" "Wolfram Alpha 目录"
check_file "$BASE_DIR/providers/wolframalpha/__init__.py" "Wolfram Alpha __init__.py"
check_file "$BASE_DIR/providers/wolframalpha/positions.yaml" "Wolfram Alpha positions.yaml"
check_file "$BASE_DIR/providers/wolframalpha/wolframalpha_query.py" "Wolfram Alpha 查询插件"
check_file "$BASE_DIR/providers/wolframalpha/wolframalpha_query.yaml" "Wolfram Alpha 查询配置"
echo ""

echo "8. 检查 Stability AI 提供商..."
echo "---"
check_dir "$BASE_DIR/providers/stability" "Stability AI 目录"
check_file "$BASE_DIR/providers/stability/__init__.py" "Stability AI __init__.py"
check_file "$BASE_DIR/providers/stability/positions.yaml" "Stability AI positions.yaml"
check_file "$BASE_DIR/providers/stability/stability_text_to_image.py" "Stability AI 图像生成插件"
check_file "$BASE_DIR/providers/stability/stability_text_to_image.yaml" "Stability AI 图像生成配置"
echo ""

echo "9. 检查 GitHub 提供商..."
echo "---"
check_dir "$BASE_DIR/providers/github" "GitHub 目录"
check_file "$BASE_DIR/providers/github/__init__.py" "GitHub __init__.py"
check_file "$BASE_DIR/providers/github/positions.yaml" "GitHub positions.yaml"
check_file "$BASE_DIR/providers/github/github_repo_search.py" "GitHub 仓库搜索插件"
check_file "$BASE_DIR/providers/github/github_repo_search.yaml" "GitHub 仓库搜索配置"
check_file "$BASE_DIR/providers/github/github_issue_search.py" "GitHub Issue 搜索插件"
check_file "$BASE_DIR/providers/github/github_issue_search.yaml" "GitHub Issue 搜索配置"
echo ""

echo "10. 检查 Google 提供商扩展..."
echo "---"
check_file "$BASE_DIR/providers/google/youtube_search.py" "YouTube 搜索插件"
check_file "$BASE_DIR/providers/google/youtube_search.yaml" "YouTube 搜索配置"
echo ""

echo "11. 检查文档文件..."
echo "---"
check_file "docs/PLUGIN_API_KEYS.md" "API Keys 配置文档"
check_file "docs/PLUGIN_UPDATE_SUMMARY.md" "插件更新总结文档"
check_file "api/.env.example" ".env.example 配置文件"
echo ""

echo "=========================================="
echo "  验证结果统计"
echo "=========================================="
echo -e "总计: ${YELLOW}$total${NC} 项"
echo -e "成功: ${GREEN}$success${NC} 项"
echo -e "失败: ${RED}$failed${NC} 项"
echo ""

if [ $failed -eq 0 ]; then
    echo -e "${GREEN}✓ 所有文件验证通过！${NC}"
    echo ""
    echo "下一步操作："
    echo "1. 配置 API Keys: 编辑 api/.env 文件"
    echo "2. 查看配置文档: cat docs/PLUGIN_API_KEYS.md"
    echo "3. 重启服务: cd api && python app/http/app.py"
    exit 0
else
    echo -e "${RED}✗ 验证失败，请检查缺失的文件${NC}"
    exit 1
fi
