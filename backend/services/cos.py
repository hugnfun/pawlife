"""
腾讯云 COS 对象存储服务。

提供文件上传、预签名 URL 生成等功能。
未配置腾讯云时使用本地存储降级方案。
"""

import logging
import os
import uuid
from datetime import timedelta
from typing import Optional

from core.config import settings

logger = logging.getLogger(__name__)


class COSService:
    """腾讯云 COS 服务。

    配置了腾讯云密钥时使用 COS 存储，
    否则使用本地文件系统存储（开发环境降级）。
    """

    def __init__(self) -> None:
        self._client = None
        self._bucket = settings.tencent_cos_bucket
        self._region = settings.tencent_cos_region
        self._enabled = bool(settings.tencent_secret_id and settings.tencent_secret_key)

        if self._enabled:
            try:
                from qcloud_cos import CosConfig, CosS3Client
                config = CosConfig(
                    Region=self._region,
                    SecretId=settings.tencent_secret_id,
                    SecretKey=settings.tencent_secret_key,
                )
                self._client = CosS3Client(config)
                logger.info(f"COS 服务已初始化: bucket={self._bucket}, region={self._region}")
            except ImportError:
                logger.warning("qcloud_cos 未安装，将使用本地存储降级方案")
                self._enabled = False
            except Exception as e:
                logger.error(f"COS 初始化失败: {e}")
                self._enabled = False
        else:
            logger.info("COS 未配置，使用本地存储降级方案")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """上传二进制数据到 COS 或本地存储。

        Args:
            data: 文件二进制数据
            key: 存储路径（如 images/xxx.jpg）
            content_type: MIME 类型

        Returns:
            文件的访问 URL
        """
        if self._enabled and self._client:
            try:
                self._client.put_object(
                    Bucket=self._bucket,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                )
                url = f"https://{self._bucket}.cos.{self._region}.myqcloud.com/{key}"
                logger.info(f"文件上传到 COS: {key}")
                return url
            except Exception as e:
                logger.error(f"COS 上传失败: {e}")
                # 降级到本地存储

        # 本地存储降级
        return self._save_local(data, key)

    def _save_local(self, data: bytes, key: str) -> str:
        """本地文件存储降级方案。"""
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
        file_path = os.path.join(upload_dir, key)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(data)

        # 返回相对路径 URL
        url = f"/uploads/{key}"
        logger.info(f"文件保存到本地: {file_path}")
        return url

    def get_presigned_url(self, key: str, expires: int = 3600) -> Optional[str]:
        """生成预签名 URL（仅 COS 模式）。

        Args:
            key: 存储路径
            expires: 过期时间（秒）

        Returns:
            预签名 URL，COS 未配置时返回 None
        """
        if not self._enabled or not self._client:
            return None

        try:
            url = self._client.get_presigned_url(
                Method="GET",
                Bucket=self._bucket,
                Key=key,
                Expired=expires,
            )
            return url
        except Exception as e:
            logger.error(f"生成预签名 URL 失败: {e}")
            return None

    @staticmethod
    def generate_key(prefix: str = "images", ext: str = "jpg") -> str:
        """生成唯一存储路径。

        Args:
            prefix: 路径前缀
            ext: 文件扩展名

        Returns:
            格式: {prefix}/{yyyy/mm/dd}/{uuid}.{ext}
        """
        from datetime import datetime
        now = datetime.utcnow()
        date_path = now.strftime("%Y/%m/%d")
        filename = f"{uuid.uuid4().hex[:16]}.{ext}"
        return f"{prefix}/{date_path}/{filename}"

    @staticmethod
    def guess_content_type(filename: str) -> str:
        """根据文件名猜测 MIME 类型。"""
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        content_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "m4a": "audio/mp4",
            "aac": "audio/aac",
            "pdf": "application/pdf",
        }
        return content_types.get(ext, "application/octet-stream")


# 全局实例
cos_service = COSService()
