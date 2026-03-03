"""应用分类实体"""
from enum import Enum


class AppCategory(Enum):
    """应用分类枚举"""
    GENERAL = "general"  # 通用
    WRITING = "writing"  # 写作助手
    PROGRAMMING = "programming"  # 编程助手
    BUSINESS = "business"  # 商业分析
    EDUCATION = "education"  # 教育学习
    ENTERTAINMENT = "entertainment"  # 娱乐休闲
    PRODUCTIVITY = "productivity"  # 效率工具
    CUSTOMER_SERVICE = "customer_service"  # 客户服务
    DATA_ANALYSIS = "data_analysis"  # 数据分析
    TRANSLATION = "translation"  # 翻译
    MARKETING = "marketing"  # 营销
    RESEARCH = "research"  # 研究
    OTHER = "other"  # 其他


# 分类中文名称映射
APP_CATEGORY_NAMES = {
    AppCategory.GENERAL.value: "通用",
    AppCategory.WRITING.value: "写作助手",
    AppCategory.PROGRAMMING.value: "编程助手",
    AppCategory.BUSINESS.value: "商业分析",
    AppCategory.EDUCATION.value: "教育学习",
    AppCategory.ENTERTAINMENT.value: "娱乐休闲",
    AppCategory.PRODUCTIVITY.value: "效率工具",
    AppCategory.CUSTOMER_SERVICE.value: "客户服务",
    AppCategory.DATA_ANALYSIS.value: "数据分析",
    AppCategory.TRANSLATION.value: "翻译",
    AppCategory.MARKETING.value: "营销",
    AppCategory.RESEARCH.value: "研究",
    AppCategory.OTHER.value: "其他",
}


# 分类列表(用于前端展示)
APP_CATEGORIES = [
    {"value": category.value, "label": APP_CATEGORY_NAMES[category.value]}
    for category in AppCategory
]
