import os
import base64
import requests
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class StabilityTextToImageArgsSchema(BaseModel):
    """Stability AI文生图参数描述"""
    prompt: str = Field(description="生成图像的文本描述(prompt)")


def _generate_image(prompt: str, **kwargs) -> str:
    """使用Stability AI生成图像"""
    api_key = os.getenv("STABILITY_API_KEY")
    if not api_key:
        return "错误：未配置STABILITY_API_KEY环境变量"

    engine_id = kwargs.get("engine_id", "stable-diffusion-xl-1024-v1-0")
    width = kwargs.get("width", 1024)
    height = kwargs.get("height", 1024)
    steps = kwargs.get("steps", 30)

    url = f"https://api.stability.ai/v1/generation/{engine_id}/text-to-image"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    body = {
        "text_prompts": [{"text": prompt}],
        "cfg_scale": 7,
        "height": height,
        "width": width,
        "steps": steps,
        "samples": 1,
    }

    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
        response.raise_for_status()

        data = response.json()
        if "artifacts" in data and len(data["artifacts"]) > 0:
            image_data = data["artifacts"][0]["base64"]
            return f"图像生成成功！Base64数据长度：{len(image_data)}\n您可以将此Base64数据保存为图像文件。"
        else:
            return "图像生成失败：未返回图像数据"

    except Exception as e:
        return f"生成图像时出错：{str(e)}"


@add_attribute("args_schema", StabilityTextToImageArgsSchema)
def stability_text_to_image(**kwargs) -> Tool:
    """Stability AI文生图工具"""
    return Tool(
        name="stability_text_to_image",
        description="使用Stable Diffusion生成高质量图像。输入应该是详细的图像描述(prompt)。",
        func=lambda prompt: _generate_image(prompt, **kwargs),
        args_schema=StabilityTextToImageArgsSchema
    )
