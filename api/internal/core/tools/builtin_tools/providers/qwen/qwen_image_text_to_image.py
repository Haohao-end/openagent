import os
import requests
from langchain_core.tools import Tool
from pydantic import BaseModel, Field
from internal.lib.helper import add_attribute


class QwenImageTextToImageArgsSchema(BaseModel):
    """千问文生图参数描述"""
    prompt: str = Field(description="图像生成的文本描述，详细描述想要生成的图像内容")


def _generate_image(prompt: str, **kwargs) -> str:
    """使用千问Qwen-Image生成图像"""
    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key:
        return "错误：未配置SILICONFLOW_API_KEY环境变量。请在.env文件中添加：SILICONFLOW_API_KEY=your_api_key"

    url = "https://api.siliconflow.cn/v1/images/generations"

    # 获取参数
    image_size = kwargs.get("image_size", "1328x1328")
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
        "model": "Qwen/Qwen-Image",
        "prompt": prompt,
        "image_size": image_size,
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
                f"✓ 成功生成图像",
                f"模型: Qwen/Qwen-Image",
                f"尺寸: {image_size}",
                f"推理步数: {num_inference_steps}",
                f"CFG系数: {cfg}",
                ""
            ]

            # 添加图片信息
            for idx, img in enumerate(data["images"], 1):
                img_url = img.get("url", "")
                result_lines.append(f"图片 {idx}:")
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
            return "图像生成失败：未返回图像数据"

    except requests.exceptions.Timeout:
        return "图像生成超时：请求时间过长，请稍后重试"
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP错误 {e.response.status_code}"
        try:
            error_data = e.response.json()
            error_detail = error_data.get("error", {}).get("message", str(e))
            error_msg += f": {error_detail}"
        except:
            error_msg += f": {str(e)}"
        return f"图像生成失败：{error_msg}"
    except Exception as e:
        return f"生成图像时出错：{str(e)}"


@add_attribute("args_schema", QwenImageTextToImageArgsSchema)
def qwen_image_text_to_image(**kwargs) -> Tool:
    """千问Qwen-Image文生图工具"""
    return Tool(
        name="qwen_image_text_to_image",
        description=(
            "使用阿里千问Qwen-Image模型生成高质量图像。"
            "支持多种图片尺寸（1:1、16:9、9:16、4:3、3:4、3:2、2:3）。"
            "使用CFG参数控制生成精度和创造性。"
            "输入应该是详细的图像描述。"
        ),
        func=lambda prompt: _generate_image(prompt, **kwargs),
        args_schema=QwenImageTextToImageArgsSchema
    )
