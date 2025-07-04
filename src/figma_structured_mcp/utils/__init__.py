"""
Figma Structured MCP 工具模块

包含异常处理、图像导出、文件上传等工具功能。
"""

from .exceptions import (
    handle_api_error,
    handle_exception,
    FigmaAPIError,
    FigmaAuthenticationError,
    FigmaNotFoundError,
    FigmaRateLimitError,
)

from .image_export import (
    get_child_node_ids,
    get_figma_images_data,
    download_image_from_url,
    export_figma_images_to_folder,
)

from .image_compression import (
    compress_image,
    get_image_info,
    is_compression_supported,
)

from .file_upload import (
    upload_file,
    upload_multiple_files,
    upload_folder_images,
    StorageProvider,
    CustomUploader,
    get_storage_provider,
)

__all__ = [
    # 异常处理
    "handle_api_error",
    "handle_exception", 
    "FigmaAPIError",
    "FigmaAuthenticationError",
    "FigmaNotFoundError",
    "FigmaRateLimitError",
    # 图像导出
    "get_child_node_ids",
    "get_figma_images_data",
    "download_image_from_url",
    "export_figma_images_to_folder",
    # 图像压缩
    "compress_image",
    "get_image_info",
    "is_compression_supported",
    # 文件上传
    "upload_file",
    "upload_multiple_files",
    "upload_folder_images",
    "StorageProvider",
    "CustomUploader",
    "get_storage_provider",
] 