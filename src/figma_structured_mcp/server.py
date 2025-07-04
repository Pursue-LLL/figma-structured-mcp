#!/usr/bin/env python3
"""
figma-structured-mcp 服务器

"""

import logging
import os
import shutil
from typing import Dict, Any
from fastmcp import FastMCP
from dotenv import load_dotenv

from .utils import (
    handle_exception,
    get_child_node_ids,
    export_figma_images_to_folder,
    upload_folder_images,
)

# 加载 .env 文件中的环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建MCP服务实例
mcp = FastMCP("figma-structured-mcp")

# Figma API 配置
FIGMA_API_BASE_URL = "https://api.figma.com/v1"


@mcp.tool
async def get_figma_images(
    file_key: str,
    node_ids: str,
    format: str = "png",
    scale: float = 1.0,
    compression_quality: float = 0.85,
    export_children: bool = True,
) -> Dict[str, Any]:
    """
    从Figma导出、压缩并上传指定节点的图像，返回可公开访问的图像URL。

    此工具自动化处理从Figma提取设计素材的整个流程：
    1. 根据提供的 `file_key` 和 `node_ids` 从Figma API获取图像。
    2. 可选择导出节点本身或其所有子节点（默认）。
    3. 对导出的图像（JPG/PNG）进行压缩以优化文件大小。
    4. 将处理后的图像上传到云存储。
    5. 返回一个包含成功上传图像的URL列表和失败详情的字典。

    **如何从Figma链接中提取参数:**
    当用户提供一个Figma链接时，需要从中提取 `file_key` 和 `node_ids`。
    例如，对于链接: `https://www.figma.com/design/d5VnH9TP69zb3EyDejwvKs/My-Design?node-id=1348-2218`
    - `file_key` 是 `d5VnH9TP69zb3EyDejwvKs` (位于 `design/` 或 `file/` 之后的部分)
    - `node_ids` 是 `1348-2218` (位于 `?node-id=` 之后的部分)

    Args:
        file_key (str): Figma文件的唯一标识符。从文件URL中 'file/' 或 'design/' 之后的部分提取。
        node_ids (str): 一个或多个逗号分隔的Figma节点ID。从URL的 `?node-id=` 参数中提取。
        format (str): 导出图像的格式。支持 "jpg", "png", "svg", "pdf"。默认为 "png"。
        scale (float): 图像的缩放比例，取值范围在 0.01 到 4 之间。默认为 1.0 (原始尺寸)。
        compression_quality (float): 图像压缩质量，仅对'jpg'和'png'格式有效。取值范围 0.0 (低质量，高压缩) 到 1.0 (高质量，低压缩)。默认为 0.85。
        export_children (bool): 控制导出行为。
            - `True` (默认): 导出指定`node_ids`下所有直接子节点作为独立的图像。这是最常见的用法，适用于需要节点内多个图层（如图标、图片素材）的场景。
            - `False`: 仅导出`node_ids`指定的节点本身，将其作为一个整体图像。当用户明确指定将节点本身导出时使用。

    Returns:
        Dict[str, Any]: 一个字典，包含两个键:
            - "successful_uploads": 一个列表，其中每个元素都是一个字典，包含 `node_id`, `file_name`, 和 `url`。
              例如: `[{"node_id": "1:2", "file_name": "icon.png", "url": "https://cdn.example.com/icon.png"}]`
            - "failed_uploads": 一个包含上传失败详情的列表。
    """
    if not os.environ.get("FIGMA_ACCESS_TOKEN"):
        raise ValueError("FIGMA_ACCESS_TOKEN environment variable not set.")
    try:
        # 从环境变量获取Figma访问令牌
        access_token = os.getenv("FIGMA_ACCESS_TOKEN")
        if not access_token:
            return {"success": False, "error": "未找到FIGMA_ACCESS_TOKEN环境变量"}
        # 清理temp-images文件夹，确保每次执行只处理本次下载的文件
        temp_folder = "temp-images"
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)
            logger.warning(f"已清理临时文件夹: {temp_folder}")

        # 如果需要导出子节点，先获取子节点ID
        target_node_ids = node_ids
        if export_children:
            logger.warning("正在获取子节点信息...")
            child_nodes_result = await get_child_node_ids(
                file_key, access_token, node_ids
            )

            if not child_nodes_result.get("success"):
                return child_nodes_result

            child_node_ids = child_nodes_result.get("child_node_ids", [])
            if not child_node_ids:
                return {"success": False, "error": "指定节点没有子节点可导出"}

            target_node_ids = ",".join(child_node_ids)
            logger.warning(
                f"找到 {len(child_node_ids)} 个子节点，将导出这些子节点的图像"
            )

        # 使用现有的导出到文件夹功能
        result = await export_figma_images_to_folder(
            file_key=file_key,
            access_token=access_token,
            node_ids=target_node_ids,
            format=format,
            scale=scale,
            compression_quality=compression_quality,
        )

        if not result.get("success"):
            return result

        logger.warning(
            f"成功导出 {len(result.get('downloaded_files', []))} 个图像到本地文件夹"
        )

        logger.warning("开始自动上传图像到服务器...")

        # 获取所有下载的文件路径
        downloaded_files = result.get("downloaded_files", [])
        if downloaded_files:
            # 批量上传文件，使用配置好的上传服务
            upload_result = await upload_folder_images(folder_path="temp-images")

            # 简化返回结果，只保留成功和失败的上传信息
            successful_uploads = [
                {"name": upload["file_name"], "url": upload["url"]}
                for upload in upload_result.get("successful_uploads", [])
            ]

            failed_uploads = [
                {
                    "name": os.path.basename(upload["file_path"]),
                    "error": upload["error"],
                }
                for upload in upload_result.get("failed_uploads", [])
            ]

            logger.warning(f"成功上传 {len(successful_uploads)} 个文件到服务器")
            if failed_uploads:
                logger.warning(f"上传失败 {len(failed_uploads)} 个文件")
        else:
            successful_uploads = []
            failed_uploads = []

        # 只返回上传成功和失败的信息
        return {
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads,
        }

    except Exception as e:
        return handle_exception(e, "获取Figma图像")
