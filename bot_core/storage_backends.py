from django.conf import settings
from django.core.files.storage import FileSystemStorage

# 1) 本地存储
class LocalMediaStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs["location"] = settings.MEDIA_ROOT
        kwargs["base_url"] = settings.MEDIA_URL
        super().__init__(*args, **kwargs)


# 2) 阿里云 OSS
try:
    from storages.backends.oss import OSSStorage
except Exception:
    OSSStorage = None


# 3) 腾讯云 COS（兼容 S3）
try:
    from storages.backends.s3boto3 import S3Boto3Storage
except Exception:
    S3Boto3Storage = None


def get_default_storage():
    mode = getattr(settings, "STORAGE_MODE", "local")

    if mode == "local":
        return LocalMediaStorage()

    if mode == "oss" and OSSStorage:
        return OSSStorage()

    if mode == "cos" and S3Boto3Storage:
        return S3Boto3Storage()

    if mode == "s3" and S3Boto3Storage:
        return S3Boto3Storage()

    # fallback
    return LocalMediaStorage()
