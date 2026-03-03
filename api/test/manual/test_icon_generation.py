"""
测试图标生成功能

运行方式：
cd api
pytest test/manual/test_icon_generation.py -v -s
"""
import os
import sys
import pytest

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_MANUAL_TESTS") != "1",
    reason="manual test: set RUN_MANUAL_TESTS=1 to run",
)


def test_icon_generation_manual():
    """
    手动测试图标生成功能

    注意：此测试需要配置以下环境变量之一：
    - SILICONFLOW_API_KEY
    - DASHSCOPE_API_KEY
    - OPENAI_API_KEY

    以及 COS 配置：
    - COS_SECRET_ID
    - COS_SECRET_KEY
    - COS_BUCKET
    - COS_DOMAIN
    """
    from flask import Flask
    from internal.service.icon_generator_service import IconGeneratorService
    from internal.service.cos_service import CosService
    from internal.core.language_model import LanguageModelManager
    from injector import Injector
    from app.http.module import ExtensionModule

    # 创建 Flask 应用
    app = Flask(__name__)
    app.config.from_pyfile('../../config/config.py')

    # 创建依赖注入容器
    injector = Injector([ExtensionModule])

    # 获取服务实例
    icon_generator_service = injector.get(IconGeneratorService)

    # 测试生成图标
    with app.app_context():
        print("\n开始测试图标生成...")
        print("=" * 60)

        # 测试用例
        test_cases = [
            {
                "name": "智能客服助手",
                "description": "一个能够回答用户问题的智能客服机器人"
            },
            {
                "name": "代码审查助手",
                "description": "帮助开发者审查代码质量和安全性"
            },
            {
                "name": "文档生成器",
                "description": "自动生成技术文档和API文档"
            }
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n测试用例 {i}:")
            print(f"  名称: {test_case['name']}")
            print(f"  描述: {test_case['description']}")

            try:
                icon_url = icon_generator_service.generate_icon(
                    name=test_case['name'],
                    description=test_case['description']
                )
                print(f"  ✓ 生成成功!")
                print(f"  图标URL: {icon_url}")
            except Exception as e:
                print(f"  ✗ 生成失败: {str(e)}")

        print("\n" + "=" * 60)
        print("测试完成!")


if __name__ == "__main__":
    test_icon_generation_manual()
