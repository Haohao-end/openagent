import logging
import hashlib
import mimetypes
import os
import time
import unicodedata
import uuid
from dataclasses import dataclass
from urllib.parse import quote

from injector import inject
from qcloud_cos import CosS3Client, CosConfig
from werkzeug.datastructures import FileStorage

from internal.entity.upload_file_entity import ALLOWED_IMAGE_EXTENSION, ALLOWED_DOCUMENT_EXTENSION
from internal.exception import FailException
from internal.lib.helper import utc_now_naive
from internal.model import UploadFile, Account
from .upload_file_service import UploadFileService


@inject
@dataclass
class CosService:
    """腾讯云cos对象存储服务"""
    upload_file_service: UploadFileService

    @staticmethod
    def _build_object_key(filename: str, folder: str = "") -> str:
        """生成对象存储 key。"""
        extension = filename.rsplit(".", 1)[-1] if "." in filename else ""
        random_filename = str(uuid.uuid4()) + (f".{extension}" if extension else "")
        now = utc_now_naive()
        prefix = f"{now.year}/{now.month:02d}/{now.day:02d}"
        normalized_folder = folder.strip("/")
        if normalized_folder:
            return f"{prefix}/{normalized_folder}/{random_filename}"
        return f"{prefix}/{random_filename}"

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

        # 3.生成一个随机的名字
        upload_filename = self._build_object_key(filename)

        # 4.流式读取上传的数据并将其上传到cos中
        file_content = file.stream.read()
        bucket = None
        try:
            # 2.获取客户端+存储桶名字
            client = self._get_client()
            bucket = self._get_bucket()

            # 5.将数据上传到cos存储桶中
            self._upload_with_retry(client, bucket, file_content, upload_filename)
            stored_key = upload_filename
        except Exception:
            logging.exception(
                "COS upload failed: bucket=%s key=%s account_id=%s",
                bucket,
                upload_filename,
                account.id,
            )
            raise FailException("上传文件失败，请稍后重试")

        # 6.创建upload_file记录
        return self.upload_file_service.create_upload_file(
            account_id=account.id,
            name=filename,
            key=stored_key,
            size=len(file_content),
            extension=extension_lower,
            mime_type=file.mimetype,
            hash=hashlib.sha3_256(file_content).hexdigest(),
        )

    def upload_bytes(
        self,
        *,
        filename: str,
        content: bytes,
        account_id,
        mime_type: str | None = None,
        folder: str = "artifacts",
    ) -> UploadFile:
        """上传内存中的字节内容，用于持久化沙箱产物。"""
        upload_filename = self._build_object_key(filename, folder=folder)
        resolved_mime_type = mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        bucket = None
        try:
            client = self._get_client()
            bucket = self._get_bucket()
            self._upload_with_retry(client, bucket, content, upload_filename)
            stored_key = upload_filename
        except Exception:
            logging.exception(
                "COS bytes upload failed: bucket=%s key=%s account_id=%s",
                bucket,
                upload_filename,
                account_id,
            )
            raise FailException("上传产物文件失败，请稍后重试")

        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return self.upload_file_service.create_upload_file(
            account_id=account_id,
            name=filename,
            key=stored_key,
            size=len(content),
            extension=extension,
            mime_type=resolved_mime_type,
            hash=hashlib.sha3_256(content).hexdigest(),
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

    @classmethod
    def _upload_with_retry(
            cls,
            client: CosS3Client,
            bucket: str,
            file_content: bytes,
            upload_filename: str,
            max_attempts: int | None = None,
    ) -> None:
        """上传文件并在失败时重试，遇到对象已存在视为幂等成功。"""
        if max_attempts is None:
            max_attempts = cls._get_upload_max_attempts()

        for attempt in range(1, max_attempts + 1):
            try:
                client.put_object(bucket, file_content, upload_filename)
                return
            except Exception as e:
                if cls._is_object_already_exists_error(e):
                    return

                if attempt == max_attempts:
                    raise

                logging.warning(
                    "COS upload attempt failed: attempt=%s/%s bucket=%s key=%s error=%s",
                    attempt,
                    max_attempts,
                    bucket,
                    upload_filename,
                    e,
                )

                # 轻量线性退避，降低瞬时网络抖动导致的失败概率。
                time.sleep(0.1 * attempt)

    @classmethod
    def upload_bytes_without_record(
        cls,
        *,
        filename: str,
        content: bytes,
        folder: str = "generated-images",
    ) -> str:
        """上传内存字节到 COS，但不创建 UploadFile 记录。"""
        upload_filename = cls._build_object_key(filename, folder=folder)
        bucket = None
        try:
            client = cls._get_client()
            bucket = cls._get_bucket()
            cls._upload_with_retry(client, bucket, content, upload_filename)
            stored_key = upload_filename
        except Exception:
            logging.exception(
                "COS bytes upload without record failed: bucket=%s key=%s",
                bucket,
                upload_filename,
            )
            raise FailException("上传产物文件失败，请稍后重试")
        return cls.get_file_url(stored_key)

    def download_file(self, key: str, target_file_path: str):
        """下载cos云端的文件到本地的指定路径"""
        if str(key or "").startswith("local/"):
            raise FailException("本地文件存储已禁用，请重新上传")

        client = self._get_client()
        bucket = self._get_bucket()

        client.download_file(bucket, key, target_file_path)

    @staticmethod
    def _build_download_filename(filename: str) -> str:
        """构建用于 Content-Disposition 的安全文件名。"""
        normalized = (filename or "").strip()
        if not normalized:
            return "download"

        ascii_fallback = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
        ascii_fallback = ascii_fallback.replace("\\", "_").replace("\"", "_").strip(" .")
        fallback_base, fallback_extension = os.path.splitext(ascii_fallback)
        if ascii_fallback and any(char.isalpha() for char in fallback_base):
            return ascii_fallback

        normalized_base, normalized_extension = os.path.splitext(normalized)
        extension = fallback_extension or normalized_extension
        return f"download{extension}" if extension else "download"

    @classmethod
    def get_file_url(cls, key: str, download_name: str | None = None) -> str:
        """根据 COS key 获取文件 URL。

        默认返回匿名可访问的裸 URL，避免给公网对象附加
        response-content-disposition 后触发 COS 匿名 GET 限制。
        如需私有桶签名下载，可通过 COS_PRESIGNED_DOWNLOAD_URL_EXPIRE_SECONDS
        显式开启预签名。
        """
        if str(key or "").startswith("local/"):
            raise FailException("本地文件存储已禁用，请重新上传")

        cos_domain = os.getenv("COS_DOMAIN")

        if not cos_domain:
            bucket = os.getenv("COS_BUCKET")
            scheme = os.getenv("COS_SCHEME")
            region = os.getenv("COS_REGION")
            cos_domain = f"{scheme}://{bucket}.cos.{region}.myqcloud.com"

        url = f"{cos_domain}/{key}"
        if not download_name:
            return url

        presigned_expires = cls._get_int_env(
            "COS_PRESIGNED_DOWNLOAD_URL_EXPIRE_SECONDS",
            0,
            minimum=0,
        )
        if presigned_expires <= 0:
            return url

        fallback_name = cls._build_download_filename(download_name)
        utf8_name = quote(download_name, safe="")
        is_html = os.path.splitext(download_name)[1].lower() in {".html", ".htm"}
        disposition_type = "inline" if is_html else "attachment"
        disposition = (
            f"{disposition_type}; filename=\"{fallback_name}\"; "
            f"filename*=UTF-8''{utf8_name}"
        )
        client = cls._get_client()
        bucket = cls._get_bucket()
        return client.get_presigned_download_url(
            Bucket=bucket,
            Key=key,
            Expired=presigned_expires,
            Params={
                "response-content-disposition": disposition,
            },
        )

    @classmethod
    def _get_client(cls) -> CosS3Client:
        """获取腾讯云cos对象存储客户端"""
        timeout_seconds = cls._get_timeout_seconds()
        sdk_retry = cls._get_sdk_retry()
        conf = CosConfig(
            Region=os.getenv("COS_REGION"),
            SecretId=os.getenv("COS_SECRET_ID"),
            SecretKey=os.getenv("COS_SECRET_KEY"),
            Token=None,
            Scheme=os.getenv("COS_SCHEME", "https"),
            Timeout=timeout_seconds,
            AutoSwitchDomainOnRetry=cls._get_bool_env("COS_AUTO_SWITCH_DOMAIN_ON_RETRY", True),
            EnableOldDomain=cls._get_bool_env("COS_ENABLE_OLD_DOMAIN", True),
            EnableInternalDomain=cls._get_bool_env("COS_ENABLE_INTERNAL_DOMAIN", False),
        )
        return CosS3Client(conf, retry=sdk_retry)

    @classmethod
    def _get_bucket(cls) -> str:
        """获取存储桶的名字"""
        return os.getenv("COS_BUCKET")

    @classmethod
    def _get_upload_max_attempts(cls) -> int:
        """获取业务层上传最大重试次数。"""
        return cls._get_int_env("COS_UPLOAD_MAX_ATTEMPTS", 3, minimum=1)

    @classmethod
    def _get_timeout_seconds(cls) -> int:
        """获取 COS 请求超时时间。"""
        return cls._get_int_env("COS_TIMEOUT_SECONDS", 10)

    @classmethod
    def _get_sdk_retry(cls) -> int:
        """获取 COS SDK 自身重试次数。"""
        return cls._get_int_env("COS_SDK_RETRY", 1, minimum=0)

    @staticmethod
    def _get_bool_env(key: str, default: bool) -> bool:
        """读取布尔环境变量，非法值时回退默认值。"""
        value = os.getenv(key)
        if value is None:
            return default

        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return default

    @staticmethod
    def _get_int_env(key: str, default: int, minimum: int = 1) -> int:
        """读取整型环境变量，非法值时回退默认值。"""
        value = os.getenv(key)
        if value is None:
            return default

        try:
            return max(minimum, int(value))
        except (TypeError, ValueError):
            return default
