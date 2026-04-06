from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject

from internal.schema.upload_file_schema import UploadFileReq, UploadFileResp, UploadImageReq
from internal.service import CosService
from pkg.response import validate_error_json, success_json


@inject
@dataclass
class UploadFileHandler:
    """上传文件处理器"""
    cos_service: CosService

    @login_required
    def upload_file(self):
        """上传文件/文档"""
        # 1.构建请求并校验
        req = UploadFileReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务上传文件并获取记录
        upload_file = self.cos_service.upload_file(req.file.data, False, current_user)

        # 3.构建响应并返回
        resp = UploadFileResp()
        return success_json(resp.dump(upload_file))

    @login_required
    def upload_image(self):
        """上传图片"""
        # 1.构建请求并校验
        req = UploadImageReq()
        if not req.validate():
            return validate_error_json(req.errors)

        # 2.调用服务并上传文件
        upload_file = self.cos_service.upload_file(req.file.data, True, current_user)

        # 3.获取图片的实际URL地址
        image_url = self.cos_service.get_file_url(upload_file.key)

        return success_json({"image_url": image_url})
