from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject

from internal.schema.audio_schema import AudioToTextReq, MessageToAudioReq, TextToAudioReq
from internal.service import AudioService
from pkg.response import validate_error_json, success_json, compact_generate_response


@inject
@dataclass
class AudioHandler:
    """语音处理器"""
    audio_service: AudioService

    @login_required
    def audio_to_text(self):
        """将语音转换成文本"""
        # 1.提取请求并校验
        req = AudioToTextReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务将音频文件转换成文本
        text = self.audio_service.audio_to_text(req.file.data)

        return success_json({"text": text})

    @login_required
    def message_to_audio(self):
        """将消息转换成流式输出音频"""
        # 1.提取请求并校验
        req = MessageToAudioReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取流式事件输出
        response = self.audio_service.message_to_audio(req.message_id.data, current_user)

        return compact_generate_response(response)

    @login_required
    def text_to_audio(self):
        """将文本转换成流式输出音频"""
        # 1.提取请求并校验
        req = TextToAudioReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务获取流式事件输出
        response = self.audio_service.text_to_audio(
            req.message_id.data,
            req.text.data,
            current_user,
        )

        return compact_generate_response(response)
