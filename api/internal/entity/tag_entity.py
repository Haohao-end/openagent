"""
标签实体模块

定义标签相关的数据模型和枚举。
"""

from enum import Enum
from typing import Dict, List


class TagStatus(str, Enum):
    """标签状态"""
    ACTIVE = "active"  # 活跃
    INACTIVE = "inactive"  # 非活跃
    ARCHIVED = "archived"  # 已归档


class TagType(str, Enum):
    """标签类型"""
    CUSTOM = "custom"  # 自定义标签
    SYSTEM = "system"  # 系统标签
    CATEGORY = "category"  # 分类标签


class AppTag(Enum):
    """应用/工作流标签枚举"""
    GENERAL = "general"  # 通用
    WRITING = "writing"  # 写作助手
    CODING = "coding"  # 编程助手
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


# 标签中文名称映射
APP_TAG_NAMES = {
    AppTag.GENERAL.value: "通用",
    AppTag.WRITING.value: "写作助手",
    AppTag.CODING.value: "编程助手",
    AppTag.BUSINESS.value: "商业分析",
    AppTag.EDUCATION.value: "教育学习",
    AppTag.ENTERTAINMENT.value: "娱乐休闲",
    AppTag.PRODUCTIVITY.value: "效率工具",
    AppTag.CUSTOMER_SERVICE.value: "客户服务",
    AppTag.DATA_ANALYSIS.value: "数据分析",
    AppTag.TRANSLATION.value: "翻译",
    AppTag.MARKETING.value: "营销",
    AppTag.RESEARCH.value: "研究",
    AppTag.OTHER.value: "其他",
}

# 标签优先级映射（数字越小优先级越高）
APP_TAG_PRIORITY = {
    AppTag.GENERAL.value: 1,
    AppTag.WRITING.value: 2,
    AppTag.CODING.value: 3,
    AppTag.BUSINESS.value: 4,
    AppTag.EDUCATION.value: 5,
    AppTag.ENTERTAINMENT.value: 6,
    AppTag.PRODUCTIVITY.value: 7,
    AppTag.CUSTOMER_SERVICE.value: 8,
    AppTag.DATA_ANALYSIS.value: 9,
    AppTag.TRANSLATION.value: 10,
    AppTag.MARKETING.value: 11,
    AppTag.RESEARCH.value: 12,
    AppTag.OTHER.value: 13,
}

# 标签列表(用于前端展示)
APP_TAGS = [
    {
        "id": tag.value,
        "name": APP_TAG_NAMES[tag.value],
        "priority": APP_TAG_PRIORITY[tag.value]
    }
    for tag in AppTag
]

# 关键词到标签的映射表
TAG_KEYWORDS_MAPPING: Dict[str, Dict] = {
    "writing": {
        "priority": 2,
        "keywords": [
            # 中文关键词
            "写作", "文案", "内容", "博客", "小说", "文章", "创意写作",
            "文本生成", "故事", "诗歌", "剧本", "新闻", "报告", "总结",
            "文章生成", "内容创作", "文本", "写", "撰写", "编写",
            # 英文关键词
            "writing", "content", "blog", "article", "story", "novel",
            "creative writing", "text generation", "copywriting", "essay"
        ]
    },
    "coding": {
        "priority": 3,
        "keywords": [
            # 中文关键词
            "代码", "编程", "开发", "Python", "JavaScript", "Java", "C++",
            "调试", "优化", "算法", "数据结构", "API", "函数", "类",
            "编码", "程序", "脚本", "代码生成", "代码审查", "重构",
            "前端", "后端", "全栈", "Web", "移动", "应用开发",
            # 英文关键词
            "coding", "programming", "development", "code", "debug",
            "algorithm", "function", "class", "API", "script"
        ]
    },
    "business": {
        "priority": 4,
        "keywords": [
            # 中文关键词
            "商业", "分析", "市场", "销售", "ROI", "竞争", "战略",
            "商务", "商业分析", "市场分析", "销售分析", "财务", "投资",
            "商业智能", "BI", "决策", "规划", "预测", "趋势",
            # 英文关键词
            "business", "analysis", "market", "sales", "strategy",
            "ROI", "competitive", "financial", "investment"
        ]
    },
    "education": {
        "priority": 5,
        "keywords": [
            # 中文关键词
            "教育", "学习", "培训", "考试", "课程", "讲师", "学生",
            "教学", "教材", "知识", "技能", "认证", "在线课程",
            "教育平台", "学习管理", "作业", "测试", "评估",
            # 英文关键词
            "education", "learning", "training", "course", "student",
            "teaching", "tutorial", "certification", "exam"
        ]
    },
    "entertainment": {
        "priority": 6,
        "keywords": [
            # 中文关键词
            "娱乐", "游戏", "创意", "故事", "音乐", "视频", "电影",
            "动画", "漫画", "休闲", "趣味", "幽默", "笑话",
            "娱乐应用", "游戏开发", "创意工具", "内容创作",
            # 英文关键词
            "entertainment", "game", "creative", "story", "music",
            "video", "movie", "animation", "fun", "humor"
        ]
    },
    "productivity": {
        "priority": 7,
        "keywords": [
            # 中文关键词
            "效率", "任务", "日程", "提醒", "自动化", "流程", "管理",
            "时间管理", "项目管理", "待办", "清单", "计划", "协作",
            "工作流", "自动化工具", "效率工具", "生产力",
            # 英文关键词
            "productivity", "task", "schedule", "automation", "workflow",
            "project management", "time management", "collaboration"
        ]
    },
    "customer_service": {
        "priority": 8,
        "keywords": [
            # 中文关键词
            "客服", "支持", "反馈", "投诉", "售后", "帮助", "咨询",
            "客户", "服务", "问题解决", "FAQ", "知识库", "工单",
            "客户关系", "CRM", "客户满意度", "服务质量",
            # 英文关键词
            "customer service", "support", "feedback", "complaint",
            "help", "FAQ", "customer", "service", "CRM"
        ]
    },
    "data_analysis": {
        "priority": 9,
        "keywords": [
            # 中文关键词
            "数据", "分析", "统计", "可视化", "报表", "BI", "仪表板",
            "数据处理", "数据挖掘", "机器学习", "预测", "趋势",
            "数据库", "SQL", "数据科学", "大数据", "数据仓库",
            # 英文关键词
            "data", "analysis", "statistics", "visualization", "dashboard",
            "BI", "analytics", "data mining", "machine learning"
        ]
    },
    "translation": {
        "priority": 10,
        "keywords": [
            # 中文关键词
            "翻译", "语言", "多语言", "本地化", "国际化", "语言转换",
            "机器翻译", "自动翻译", "语言处理", "NLP", "文本翻译",
            # 英文关键词
            "translation", "language", "multilingual", "localization",
            "internationalization", "translate", "language processing"
        ]
    },
    "marketing": {
        "priority": 11,
        "keywords": [
            # 中文关键词
            "营销", "广告", "推广", "SEO", "社媒", "品牌", "宣传",
            "市场营销", "内容营销", "社交媒体", "电子邮件", "转化",
            "用户获取", "增长", "流量", "转化率", "用户留存",
            # 英文关键词
            "marketing", "advertising", "promotion", "SEO", "social media",
            "brand", "campaign", "email", "conversion", "growth"
        ]
    },
    "research": {
        "priority": 12,
        "keywords": [
            # 中文关键词
            "研究", "论文", "学术", "知识库", "文献", "调查", "实验",
            "科研", "学术研究", "论文写作", "文献综述", "数据收集",
            "研究方法", "学术出版", "引文", "参考文献",
            # 英文关键词
            "research", "paper", "academic", "knowledge base", "literature",
            "survey", "experiment", "study", "publication", "citation"
        ]
    },
    "general": {
        "priority": 1,
        "keywords": [
            # 中文关键词
            "通用", "助手", "工具", "平台", "应用", "系统", "服务",
            "综合", "多功能", "全能", "万能", "智能助手",
            # 英文关键词
            "general", "assistant", "tool", "platform", "application",
            "system", "service", "universal", "all-in-one"
        ]
    },
    "other": {
        "priority": 13,
        "keywords": [
            # 中文关键词
            "其他", "杂项", "未分类",
            # 英文关键词
            "other", "misc", "miscellaneous"
        ]
    }
}


def get_tag_name(tag_id: str) -> str:
    """获取标签的中文名称"""
    return APP_TAG_NAMES.get(tag_id, tag_id)


def get_tag_priority(tag_id: str) -> int:
    """获取标签的优先级"""
    return APP_TAG_PRIORITY.get(tag_id, 999)


def sort_tags_by_priority(tags: List[str]) -> List[str]:
    """按优先级排序标签"""
    return sorted(tags, key=lambda t: get_tag_priority(t))
