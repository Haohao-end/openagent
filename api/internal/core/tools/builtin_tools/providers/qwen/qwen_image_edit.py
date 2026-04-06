import os
import requests
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class QwenImageEditArgsSchema(BaseModel):
    """千问图像编辑参数描述"""
    prompt: str = Field(description="图像编辑的文本描述，描述想要的编辑效果")
    image: str = Field(description="输入图片，可以是URL或base64格式(data:image/png;base64,XXX)")


def _edit_image(prompt: str, image: str, **kwargs) -> str:
    """使用千问Qwen-Image-Edit编辑图像"""
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        return "错误：未配置SILICONFLOW_API_KEY环境变量。请在.env文件中添加：SILICONFLOW_API_KEY=your_api_key"

    url = "https://api.siliconflow.cn/v1/images/generations"

    # 获取参数
    num_inference_steps = kwargs.get("num_inference_steps", 50)
    cfg = kwargs.get("cfg", 4.0)
    seed = kwargs.get("seed")
    negative_prompt = kwargs.get("negative_prompt", "")

    # 验证参数范围
    if num_inference_steps < 1 or num_inference_steps > 100:
        num_inference_steps = 50
    if cfg < 0.1 or cfg > 20:
        cfg = 4.0

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    body = {
        "model": "Qwen/Qwen-Image-Edit",
        "prompt": prompt,
        "image": image,
        "num_inference_steps": num_inference_steps,
        "cfg": cfg
    }

    # 添加可选参数
    if negative_prompt:
        body["negative_prompt"] = negative_prompt
    if seed is not None:
        body["seed"] = seed

    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
        response.raise_for_status()

        data = response.json()

        if "images" in data and len(data["images"]) > 0:
            result_lines = [
                f"✓ 成功编辑图像",
                f"模型: Qwen/Qwen-Image-Edit",
                f"推理步数: {num_inference_steps}",
                f"CFG系数: {cfg}",
                ""
            ]

            # 添加图片信息
            for idx, img in enumerate(data["images"], 1):
                img_url = img.get("url", "")
                result_lines.append(f"输出图片 {idx}:")
                result_lines.append(f"  URL: {img_url}")
                result_lines.append(f"  提示: 图片URL有效期为1小时，请及时下载保存")
                result_lines.append("")

            # 添加时间信息
            if "timings" in data:
                timings = data["timings"]
                result_lines.append(f"生成耗时: {timings.get('inference', 'N/A')}秒")

            # 添加种子信息
            if "seed" in data:
                result_lines.append(f"随机种子: {data['seed']}")

            return "\n".join(result_lines)
        else:
            return "图像编辑失败：未返回图像数据"

    except requests.exceptions.Timeout:
        return "图像编辑超时：请求时间过长，请稍后重试"
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP错误 {e.response.status_code}"
        try:
            error_data = e.response.json()
            error_detail = error_data.get("error", {}).get("message", str(e))
            error_msg += f": {error_detail}"
        except:
            error_msg += f": {str(e)}"
        return f"图像编辑失败：{error_msg}"
    except Exception as e:
        return f"编辑图像时出错：{str(e)}"


@add_attribute("args_schema", QwenImageEditArgsSchema)
def qwen_image_edit(**kwargs) -> Tool:
    """千问Qwen-Image-Edit图像编辑工具"""
    return Tool(
        name="qwen_image_edit",
        description=(
            "使用阿里千问Qwen-Image-Edit模型编辑图像。"
            "支持单张图片输入，可进行图像编辑、风格转换、内容修改等操作。"
            "输入需要包含编辑描述和一张图片URL或base64数据。"
        ),
        func=lambda prompt, image: _edit_image(prompt, image, **kwargs),
        args_schema=QwenImageEditArgsSchema
    )
