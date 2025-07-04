#!/usr/bin/env python3
"""
文件上传工具模块

提供一个可扩展、高性能的文件上传服务，支持多种存储提供商。
通过环境变量配置，实现不同上传服务的解耦。
"""

import abc
import asyncio
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import httpx
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

logger = logging.getLogger(__name__)


class StorageProvider(abc.ABC):
    """
    存储提供商的抽象基类
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化提供商。

        Args:
            config: 从环境变量动态加载的配置字典。
        """
        self.config = config

    @abc.abstractmethod
    async def upload(self, file_path: str) -> Dict[str, Any]:
        """
        上传单个文件。
        """
        pass


class CustomUploader(StorageProvider):
    """
    自定义签名上传服务器

    实现将文件上传到通用的、支持时间戳和签名机制的上传接口。
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化 CustomUploader。

        期望配置中包含:
        - 'secret_key': 用于生成签名。
        - 'upload_url': 完整的上传基础URL，可包含静态查询参数。
        """
        super().__init__(config)
        self.secret_key = self.config.get("secret_key")
        self.base_url = self.config.get("upload_url")

        if not self.secret_key:
            raise ValueError(
                "Provider config must include 'secret_key'. "
                "Check your CUSTOM_SECRET_KEY env var."
            )
        if not self.base_url:
            raise ValueError(
                "Provider config must include 'upload_url'. "
                "Check your CUSTOM_UPLOAD_URL env var."
            )

    def _generate_signature(self, timestamp: int) -> str:
        """
        生成上传签名
        """
        sign_string = f"{timestamp}:{self.secret_key}"
        return hashlib.md5(sign_string.encode()).hexdigest()

    def _parse_response(
        self, response_data: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[str]]:
        """从服务器响应中解析URL和错误信息。"""
        if response_data.get("code") == 0 or response_data.get("success"):
            data_field = response_data.get("data")
            if isinstance(data_field, str):
                return data_field, None
            if isinstance(data_field, dict):
                return data_field.get("url"), None
            return response_data.get("url"), None
        return None, response_data.get("message", "Unknown server error")

    async def upload(self, file_path: str) -> Dict[str, Any]:
        """
        上传单个文件到自定义服务器。
        """
        try:
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "error": f"File does not exist: {file_path}",
                    "file_path": file_path,
                }

            timestamp = int(time.time() * 1000)
            signature = self._generate_signature(timestamp)

            url = self.base_url or ""
            separator = "&" if "?" in url else "?"
            upload_url = f"{url}{separator}ts={timestamp}&sign={signature}"

            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)

            logger.warning(f"Starting upload: {file_name} ({file_size} bytes)")

            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(file_path, "rb") as f:
                    files = {"file": (file_name, f, "application/octet-stream")}
                    response = await client.post(upload_url, files=files)

                    if response.status_code != 200:
                        return {
                            "success": False,
                            "error": f"HTTP error: {response.status_code}",
                            "details": response.text,
                            "file_path": file_path,
                        }

                    result_data = response.json()
                    if not isinstance(result_data, dict):
                        return {
                            "success": False,
                            "error": f"Server returned non-JSON response: {result_data}",
                            "file_path": file_path,
                        }

                    file_url, error_msg = self._parse_response(result_data)
                    if error_msg:
                        return {
                            "success": False,
                            "error": f"Server error: {error_msg}",
                            "file_path": file_path,
                        }

                    logger.warning(f"Upload successful: {file_name} -> {file_url}")
                    return {
                        "success": True,
                        "file_name": file_name,
                        "file_size": file_size,
                        "url": file_url,
                        "file_path": file_path,
                    }
        except Exception as e:
            logger.error(f"An exception occurred during upload for {file_path}: {e}")
            return {"success": False, "error": str(e), "file_path": file_path}


# --- Uploader Factory ---

_storage_provider_instance: Optional[StorageProvider] = None


def get_storage_provider() -> StorageProvider:
    """
    获取配置的存储提供商实例（单例模式）。

    根据环境变量 `STORAGE_PROVIDER` 动态加载并配置提供商。
    配置项从环境变量中自动读取，格式为 `PROVIDERNAME_CONFIGKEY`。
    """
    global _storage_provider_instance
    if _storage_provider_instance is None:
        provider_name = os.getenv("STORAGE_PROVIDER", "custom").lower()
        logger.warning(f"Initializing storage provider: {provider_name}")

        # 动态构建配置
        config_prefix = f"{provider_name.upper()}_"
        provider_config = {}
        for key, value in os.environ.items():
            if key.startswith(config_prefix):
                config_key = key[len(config_prefix) :].lower()
                provider_config[config_key] = value

        logger.warning(
            f"Loaded config for {provider_name}: {list(provider_config.keys())}"
        )

        if provider_name == "custom":
            _storage_provider_instance = CustomUploader(provider_config)
        # 在此可以添加其他提供商的逻辑
        # elif provider_name == "s3":
        #     _storage_provider_instance = S3Uploader(provider_config)
        else:
            raise ValueError(f"Unsupported storage provider: {provider_name}")
    return _storage_provider_instance


# --- Public API ---


async def upload_file(file_path: str) -> Dict[str, Any]:
    """
    上传单个文件。
    """
    try:
        provider = get_storage_provider()
        return await provider.upload(file_path)
    except Exception as e:
        logger.error(f"Failed to get storage provider or upload file: {e}")
        return {"success": False, "error": str(e), "file_path": file_path}


async def upload_multiple_files(file_paths: List[str]) -> Dict[str, Any]:
    """
    并发批量上传多个文件。
    """
    logger.warning(f"Starting concurrent batch upload for {len(file_paths)} files.")

    # 并发执行所有上传任务
    tasks = [upload_file(file_path) for file_path in file_paths]
    results = await asyncio.gather(*tasks)

    successful_uploads = [r for r in results if r.get("success")]
    failed_uploads = [r for r in results if not r.get("success")]
    total_size = sum(r.get("file_size", 0) for r in successful_uploads)

    logger.warning(
        f"Batch upload complete: {len(successful_uploads)} successful, {len(failed_uploads)} failed."
    )

    return {
        "success": not failed_uploads,
        "total_files": len(file_paths),
        "successful_count": len(successful_uploads),
        "failed_count": len(failed_uploads),
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads,
        "total_size": total_size,
    }


async def upload_folder_images(
    folder_path: str, file_extensions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    上传文件夹中的所有图像文件。
    """
    if file_extensions is None:
        file_extensions = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"]

    p = Path(folder_path)
    if not p.is_dir():
        return {"success": False, "error": f"Folder not found: {folder_path}"}

    image_files = [
        str(file)
        for ext in file_extensions
        for file in p.rglob(f"*{ext}")
        if file.is_file()
    ]

    if not image_files:
        return {
            "success": True,
            "message": f"No image files found in folder: {folder_path}",
            "total_files": 0,
            "successful_uploads": [],
        }

    logger.warning(f"Found {len(image_files)} image files in {folder_path}.")
    return await upload_multiple_files(file_paths=image_files)
