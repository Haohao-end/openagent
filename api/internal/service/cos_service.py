import hashlib
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

from injector import inject
from qcloud_cos import CosS3Client, CosConfig
from werkzeug.datastructures import FileStorage

from internal.entity.upload_file_entity import ALLOWED_IMAGE_EXTENSION, ALLOWED_DOCUMENT_EXTENSION
from internal.exception import FailException
from internal.model import UploadFile, Account
from .upload_file_service import UploadFileService


@inject
@dataclass
class CosService:
    """腾讯云cos对象存储服务"""
    upload_file_service: UploadFileService

    def upload_file(self, file: FileStorage, only_image: bool, account: Account) -> UploadFile:
        """上传文件到腾讯云cos对象存储，上传后返回文件的信息"""
        # 1.提取文件扩展名并检测是否可以上传
        filename = file.filename
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        extension_lower = extension.lower()
        if extension_lower not in (ALLOWED_IMAGE_EXTENSION + ALLOWED_DOCUMENT_EXTENSION):
            raise FailException(f"该.{extension}扩展的文件不允许上传")
        elif only_image and extension_lower not in ALLOWED_IMAGE_EXTENSION:
            raise FailException(f"该.{extension}扩展的文件不支持上传，请上传正确的图片")

        # 2.获取客户端+存储桶名字
        client = self._get_client()
        bucket = self._get_bucket()

        # 3.生成一个随机的名字
        random_filename = str(uuid.uuid4()) + "." + extension
        now = datetime.now()
        upload_filename = f"{now.year}/{now.month:02d}/{now.day:02d}/{random_filename}"

        # 4.流式读取上传的数据并将其上传到cos中
        file_content = file.stream.read()

        try:
            # 5.将数据上传到cos存储桶中
            self._upload_with_retry(client, bucket, file_content, upload_filename)
        except Exception as e:
            raise FailException("上传文件失败，请稍后重试")

        # 6.创建upload_file记录
        return self.upload_file_service.create_upload_file(
            account_id=account.id,
            name=filename,
            key=upload_filename,
            size=len(file_content),
            extension=extension_lower,
            mime_type=file.mimetype,
            hash=hashlib.sha3_256(file_content).hexdigest(),
        )

    @staticmethod
    def _is_object_already_exists_error(error: Exception) -> bool:
        """检测异常是否属于对象已存在，作为幂等上传成功处理。"""
        error_message = str(error).lower()
        idempotent_keywords = (
            "already exists",
            "alreadyexists",
            "objectalreadyexists",
            "filealreadyexists",
            "file exist",
            "key already exists",
        )
        return any(keyword in error_message for keyword in idempotent_keywords)

    def _upload_with_retry(
            self,
            client: CosS3Client,
            bucket: str,
            file_content: bytes,
            upload_filename: str,
            max_attempts: int = 3,
    ) -> None:
        """上传文件并在失败时重试，遇到对象已存在视为幂等成功。"""
        for attempt in range(1, max_attempts + 1):
            try:
                client.put_object(bucket, file_content, upload_filename)
                return
            except Exception as e:
                if self._is_object_already_exists_error(e):
                    return

                if attempt == max_attempts:
                    raise

                # 轻量线性退避，降低瞬时网络抖动导致的失败概率。
                time.sleep(0.1 * attempt)

    def download_file(self, key: str, target_file_path: str):
        """下载cos云端的文件到本地的指定路径"""
        client = self._get_client()
        bucket = self._get_bucket()

        client.download_file(bucket, key, target_file_path)

    @classmethod
    def get_file_url(cls, key: str) -> str:
        """根据传递的cos云端key获取图片的实际URL地址"""
        cos_domain = os.getenv("COS_DOMAIN")

        if not cos_domain:
            bucket = os.getenv("COS_BUCKET")
            scheme = os.getenv("COS_SCHEME")
            region = os.getenv("COS_REGION")
            cos_domain = f"{scheme}://{bucket}.cos.{region}.myqcloud.com"

        return f"{cos_domain}/{key}"

    @classmethod
    def _get_client(cls) -> CosS3Client:
        """获取腾讯云cos对象存储客户端"""
        conf = CosConfig(
            Region=os.getenv("COS_REGION"),
            SecretId=os.getenv("COS_SECRET_ID"),
            SecretKey=os.getenv("COS_SECRET_KEY"),
            Token=None,
            Scheme=os.getenv("COS_SCHEME", "https")
        )
        return CosS3Client(conf)

    @classmethod
    def _get_bucket(cls) -> str:
        """获取存储桶的名字"""
        return os.getenv("COS_BUCKET")
