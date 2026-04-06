import json
from typing import Any, Type
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from internal.lib.helper import add_attribute


class QRCodeArgsSchema(BaseModel):
    text: str = Field(description="需要生成二维码的文本内容，可以是URL、文本等")
    size: int = Field(default=200, description="二维码尺寸（像素），默认200")


class QRCodeTool(BaseTool):
    """二维码生成工具"""
    name: str = "qrcode_generate"
    description: str = "根据文本内容生成二维码图片URL"
    args_schema: Type[BaseModel] = QRCodeArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """生成二维码"""
        try:
            text = kwargs.get("text", "")
            size = kwargs.get("size", 200)

            if not text:
                return "请提供需要生成二维码的文本内容"

            # 使用免费的二维码API
            import urllib.parse
            encoded_text = urllib.parse.quote(text)
            qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size={size}x{size}&data={encoded_text}"

            result = {
                "text": text,
                "size": size,
                "qr_code_url": qr_url,
                "message": "二维码生成成功，可以通过URL访问"
            }
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            return f"二维码生成失败：{str(e)}"


@add_attribute("args_schema", QRCodeArgsSchema)
def qrcode_generate(**kwargs) -> BaseTool:
    """获取二维码生成工具"""
    return QRCodeTool()
