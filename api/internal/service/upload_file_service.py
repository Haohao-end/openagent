from injector import inject
from dataclasses import  dataclass
from .base_service import BaseService
from pkg.sqlalchemy import SQLAlchemy
from internal.model import UploadFile

@inject
@dataclass
class UploadFileService(BaseService):
    """上传文件记录服务"""
    db: SQLAlchemy

    def create_upload_file(self, **kwargs) -> UploadFile:
        """创建文件记录服务"""
        return self.create(UploadFile, **kwargs)