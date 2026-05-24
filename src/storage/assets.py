"""附件存储后端。"""
from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from src.services.cos import upload_file


class AssetStorage(ABC):
    @abstractmethod
    def save(self, local_path: str, key: str | None = None) -> Optional[str]:
        """保存本地文件并返回 URL 或目标路径。"""


class LocalAssetStorage(AssetStorage):
    def __init__(self, root_path: str):
        self.root_path = Path(root_path)

    def save(self, local_path: str, key: str | None = None) -> Optional[str]:
        self.root_path.mkdir(parents=True, exist_ok=True)
        src = Path(local_path)
        dest = self.root_path / (key or src.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return str(dest)


class CosAssetStorage(AssetStorage):
    def save(self, local_path: str, key: str | None = None) -> Optional[str]:
        return upload_file(local_path)


class S3CompatibleAssetStorage(AssetStorage):
    """S3-compatible 占位实现。

    当前复用 COS SDK 的部署路径；自托管 S3 可在后续替换为 boto3 或兼容 SDK。
    """

    def save(self, local_path: str, key: str | None = None) -> Optional[str]:
        return upload_file(local_path)


def get_asset_storage() -> AssetStorage:
    backend = os.getenv("ASSET_STORAGE_BACKEND", "local").lower()
    if backend == "cos":
        return CosAssetStorage()
    if backend in {"s3", "s3-compatible"}:
        return S3CompatibleAssetStorage()
    return LocalAssetStorage(os.getenv("ASSET_LOCAL_PATH", "data/assets"))
