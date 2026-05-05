import logging
import uuid
from dataclasses import dataclass
from typing import Optional

import requests
from flask import current_app
from injector import inject
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from internal.core.language_model import LanguageModelManager
from internal.entity.app_entity import GENERATE_ICON_PROMPT_TEMPLATE
from internal.exception import FailException
from internal.lib.helper import utc_now_naive
from .base_service import BaseService
from .cos_service import CosService


@inject
@dataclass
class IconGeneratorService(BaseService):
    """图标生成服务 - 支持 Kolors → Qwen → DALLE 降级策略"""

    cos_service: CosService
    language_model_manager: LanguageModelManager

    def generate_icon(self, name: str, description: str = "") -> str:
        """
        根据应用名称和描述生成图标并上传到COS

        Args:
            name: 应用名称
            description: 应用描述

        Returns:
            str: 图标的COS URL

        Raises:
            FailException: 所有图标生成方式都失败时抛出
        """
        errors = []

        # 1. 尝试使用 Kolors (硅基流动)
        try:
            logging.info(f"尝试使用 Kolors 生成图标: name={name}")
            icon_url = self._generate_with_kolors(name, description)
            if icon_url:
                logging.info(f"Kolors 生成图标成功: {icon_url}")
                return icon_url
        except Exception as e:
            error_msg = str(e)
            logging.warning(f"Kolors 生成图标失败: {error_msg}")
            errors.append(f"Kolors: {error_msg}")

        # 2. 尝试使用 Qwen (通义万相)
        try:
            logging.info(f"尝试使用 Qwen 生成图标: name={name}")
            icon_url = self._generate_with_qwen(name, description)
            if icon_url:
                logging.info(f"Qwen 生成图标成功: {icon_url}")
                return icon_url
        except Exception as e:
            error_msg = str(e)
            logging.warning(f"Qwen 生成图标失败: {error_msg}")
            errors.append(f"Qwen: {error_msg}")

        # 3. 最后使用 DALLE 兜底
        try:
            logging.info(f"尝试使用 DALLE 生成图标: name={name}")
            icon_url = self._generate_with_dalle(name, description)
            if icon_url:
                logging.info(f"DALLE 生成图标成功: {icon_url}")
                return icon_url
        except Exception as e:
            error_msg = str(e)
            logging.error(f"DALLE 生成图标失败: {error_msg}")
            errors.append(f"DALLE: {error_msg}")

        # 所有服务都失败，返回友好的错误信息
        error_summary = "; ".join(errors)
        logging.error(f"所有图标生成服务均失败: {error_summary}")
        raise FailException("图标生成服务暂时不可用，请稍后重试或手动上传图标")

    def _generate_icon_prompt(self, name: str, description: str) -> str:
        """生成图标描述提示词"""
        try:
            # 使用 DeepSeek 生成英文的图标描述
            from internal.core.language_model.providers.deepseek.chat import Chat as DeepSeekChat

            llm = DeepSeekChat(
                model="deepseek-chat",
                temperature=0.7,
            )

            prompt_chain = ChatPromptTemplate.from_template(
                GENERATE_ICON_PROMPT_TEMPLATE
            ) | llm | StrOutputParser()

            icon_prompt = prompt_chain.invoke({
                "name": name,
                "description": description or f"一个名为{name}的应用"
            })

            return str(icon_prompt).strip()
        except Exception as e:
            logging.warning(f"生成图标提示词失败，使用默认提示词: {str(e)}")
            return (
                f"A premium mobile app launcher icon for {name}, single centered subject, "
                f"rounded square app icon composition, modern polished visual style, distinctive color palette, "
                f"premium material finish, soft studio lighting, clean plain background, crisp silhouette, "
                f"high recognizability at small sizes, no text, no watermark, no extra elements"
            )

    def _raise_request_error(self, provider_name: str, error: Exception) -> None:
        """将上游 HTTP 异常转换为统一的业务异常"""
        if isinstance(error, requests.exceptions.Timeout):
            raise FailException(f"{provider_name} 服务请求超时，请稍后重试")

        if isinstance(error, requests.exceptions.HTTPError):
            status_code = getattr(error.response, "status_code", None)
            error_detail = ""
            try:
                error_data = error.response.json() if error.response else {}
                error_detail = (
                    error_data.get("error", {}).get("message")
                    or error_data.get("message")
                    or str(error)
                )
            except Exception:
                error_detail = str(error)

            if status_code == 429:
                raise FailException(f"{provider_name} 服务请求过于频繁，请稍后重试")

            if status_code:
                raise FailException(f"{provider_name} 服务请求失败: HTTP {status_code}: {error_detail}")

            raise FailException(f"{provider_name} 服务请求失败: {error_detail}")

        if isinstance(error, requests.exceptions.RequestException):
            raise FailException(f"{provider_name} 服务请求失败，请稍后重试")

        raise error

    def _request_siliconflow_image(
            self,
            provider_name: str,
            model: str,
            prompt: str,
            source: str,
            **payload: object,
    ) -> str:
        """请求 SiliconFlow 文生图并返回上传后的 COS 地址"""
        api_key = current_app.config.get("SILICONFLOW_API_KEY")
        if not api_key:
            raise FailException("SILICONFLOW_API_KEY 未配置")

        api_base = current_app.config.get("SILICONFLOW_API_BASE", "https://api.siliconflow.cn")
        url = f"{str(api_base).rstrip('/')}/v1/images/generations"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "prompt": prompt,
            **payload,
        }

        try:
            response = requests.post(url, json=body, headers=headers, timeout=60)
            response.raise_for_status()
        except Exception as e:
            self._raise_request_error(provider_name, e)

        result = response.json()
        images = result.get("images") or []
        if not images:
            raise FailException(f"{provider_name} 返回的图片列表为空")

        image_url = images[0].get("url")
        if not image_url:
            raise FailException(f"{provider_name} 返回的图片URL为空")

        return self._download_and_upload_image(image_url, source)

    def _generate_with_kolors(self, name: str, description: str) -> Optional[str]:
        """使用 Kolors (硅基流动) 生成图标"""
        prompt = self._generate_icon_prompt(name, description)
        return self._request_siliconflow_image(
            "Kolors",
            "Kwai-Kolors/Kolors",
            prompt,
            "kolors",
            image_size="1024x1024",
            batch_size=1,
            num_inference_steps=20,
            guidance_scale=7.5,
        )

    def _generate_with_qwen(self, name: str, description: str) -> Optional[str]:
        """使用 Qwen (SiliconFlow) 生成图标"""
        prompt = self._generate_icon_prompt(name, description)
        return self._request_siliconflow_image(
            "Qwen",
            "Qwen/Qwen-Image",
            prompt,
            "qwen",
            image_size="1328x1328",
            num_inference_steps=50,
            cfg=4.0,
        )

    def _generate_with_dalle(self, name: str, description: str) -> Optional[str]:
        """使用 DALLE 生成图标"""
        api_key = current_app.config.get("OPENAI_API_KEY")
        if not api_key:
            raise FailException("OPENAI_API_KEY 未配置")

        # 生成图标描述
        prompt = self._generate_icon_prompt(name, description)

        # 使用 LangChain 的 DALLE wrapper
        dalle_api_wrapper = DallEAPIWrapper(
            model="dall-e-3",
            api_key=api_key,
            size="1024x1024",
            quality="standard",
            n=1,
        )

        # 生成图片
        image_url = dalle_api_wrapper.run(prompt)

        if not image_url:
            raise FailException("DALLE 返回的图片URL为空")

        # 下载图片并上传到COS
        return self._download_and_upload_image(image_url, "dalle")

    def _download_and_upload_image(self, image_url: str, source: str) -> str:
        """
        下载图片并上传到COS

        Args:
            image_url: 图片URL
            source: 图片来源 (kolors/qwen/dalle)

        Returns:
            str: COS中的图片URL
        """
        # 1. 下载图片
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()

        image_data = response.content

        # 2. 获取COS客户端和存储桶
        client = self.cos_service._get_client()
        bucket = self.cos_service._get_bucket()

        # 3. 生成文件名
        random_filename = f"{uuid.uuid4()}.png"
        now = utc_now_naive()
        upload_filename = f"{now.year}/{now.month:02d}/{now.day:02d}/icons/{source}_{random_filename}"

        # 4. 上传到COS
        client.put_object(
            Bucket=bucket,
            Body=image_data,
            Key=upload_filename,
            ContentType="image/png"
        )

        # 5. 返回COS URL
        cos_domain = current_app.config.get("COS_DOMAIN")
        if not cos_domain:
            raise FailException("COS_DOMAIN 未配置")

        return f"{cos_domain}/{upload_filename}"
