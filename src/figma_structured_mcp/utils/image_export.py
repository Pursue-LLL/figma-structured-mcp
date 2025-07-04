#!/usr/bin/env python3
"""
Figma 图像导出工具模块

提供 Figma 图像获取和下载的核心功能。
"""

import os
import asyncio
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from .exceptions import handle_api_error, handle_exception
from .image_compression import compress_image, is_compression_supported


async def get_child_node_ids(file_key: str, access_token: str, node_ids: str) -> Dict[str, Any]:
    """
    获取指定节点的所有顶级子节点ID
    
    Args:
        file_key: Figma文件的唯一标识符
        access_token: Figma个人访问令牌
        node_ids: 父节点ID列表，用逗号分隔
        
    Returns:
        包含子节点ID列表的字典
    """
    try:
        # 构建请求头
        headers = {"X-Figma-Token": access_token, "Content-Type": "application/json"}
        
        # 构建API URL - 获取节点信息，depth=1 只获取直接子节点
        url = f"https://api.figma.com/v1/files/{file_key}/nodes"
        params = {
            "ids": node_ids,
            "depth": 1,
        }
        
        # 发送HTTP请求
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                nodes = data.get("nodes", {})
                
                child_node_ids = []
                
                # 遍历每个父节点，收集其子节点ID
                for node_id, node_info in nodes.items():
                    if node_info and "document" in node_info:
                        document = node_info["document"]
                        children = document.get("children", [])
                        
                        # 收集所有顶级子节点的ID
                        for child in children:
                            child_id = child.get("id")
                            if child_id:
                                child_node_ids.append(child_id)
                
                return {
                    "success": True,
                    "child_node_ids": child_node_ids,
                    "parent_nodes": list(nodes.keys()),
                    "total_children": len(child_node_ids)
                }
            
            return handle_api_error(response, "获取子节点信息")
            
    except Exception as e:
        return handle_exception(e, "获取子节点信息")


async def get_figma_images_data(
    file_key: str,
    access_token: str,
    node_ids: str,
    format: str = "png",
    scale: float = 1.0,
    api_base_url: str = "https://api.figma.com/v1",
) -> Dict[str, Any]:
    """
    从 Figma API 获取图像数据

    Args:
        file_key: Figma文件的唯一标识符
        access_token: Figma个人访问令牌
        node_ids: 要导出图像的节点ID列表，用逗号分隔
        format: 图像格式 ("jpg", "png", "svg", "pdf")
        scale: 图像缩放比例 (0.01 到 4)
        api_base_url: Figma API 基础URL

    Returns:
        包含图像URL的字典
    """
    try:
        # 验证格式参数
        valid_formats = ["jpg", "png", "svg", "pdf"]
        if format not in valid_formats:
            return {
                "success": False,
                "error": f"无效的图像格式: {format}。支持的格式: {', '.join(valid_formats)}",
            }

        # 验证缩放比例
        if not (0.01 <= scale <= 4.0):
            return {
                "success": False,
                "error": f"无效的缩放比例: {scale}。缩放比例必须在0.01到4之间",
            }

        # 构建请求头
        headers = {"X-Figma-Token": access_token, "Content-Type": "application/json"}

        # 构建API URL
        url = f"{api_base_url}/images/{file_key}"
        params = {
            "ids": node_ids,
            "format": format,
            "scale": scale,
        }

        # 发送HTTP请求
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(url, headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()

                # 处理和格式化返回数据
                result = {
                    "success": True,
                    "file_key": file_key,
                    "images": data.get("images", {}),
                    "format": format,
                    "scale": scale,
                    "err": data.get("err", None),
                }

                # 检查是否有失败的节点
                failed_nodes = [
                    node_id
                    for node_id, url in data.get("images", {}).items()
                    if not url
                ]
                if failed_nodes:
                    result["failed_nodes"] = failed_nodes

                return result

            return handle_api_error(response, "图像获取")

    except Exception as e:
        return handle_exception(e, "获取Figma图像")


async def download_image_from_url(
    image_url: str,
    save_path: Path,
    filename: str,
    compression_quality: float = 0.85,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    从URL下载图像到本地文件，支持压缩和重试机制

    Args:
        image_url: 图像URL
        save_path: 保存目录路径
        filename: 文件名
        compression_quality: 压缩质量 (0.0-1.0)
        max_retries: 最大重试次数

    Returns:
        下载结果字典
    """
    import asyncio

    # 确保保存目录存在
    save_path.mkdir(parents=True, exist_ok=True)
    full_path = save_path / filename

    for attempt in range(max_retries + 1):
        try:
            # 下载图像
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(image_url)

                if response.status_code == 200:
                    with open(full_path, "wb") as f:
                        f.write(response.content)

                    original_size = len(response.content)
                    result = {
                        "success": True,
                        "file_path": str(full_path),
                        "filename": filename,
                        "file_size": original_size,
                    }

                    # 如果需要压缩
                    if is_compression_supported(full_path):
                        compression_result = await compress_image(
                            full_path,
                            quality=compression_quality,
                        )

                        if compression_result.get("success"):
                            result.update(
                                {
                                    "compressed": True,
                                    "original_size": compression_result[
                                        "original_size"
                                    ],
                                    "file_size": compression_result["compressed_size"],
                                    "compression_ratio": compression_result[
                                        "compression_ratio"
                                    ],
                                    "size_reduction": compression_result[
                                        "size_reduction"
                                    ],
                                    "compression_method": compression_result.get(
                                        "compression_method", "unknown"
                                    ),
                                }
                            )
                        else:
                            result.update(
                                {
                                    "compressed": False,
                                    "compression_error": compression_result.get(
                                        "error"
                                    ),
                                }
                            )

                    return result
                else:
                    if attempt < max_retries:
                        await asyncio.sleep(2**attempt)  # 指数退避
                        continue
                    return {
                        "success": False,
                        "error": f"下载失败，状态码: {response.status_code}",
                    }

        except Exception as e:
            if attempt < max_retries:
                print(
                    f"下载尝试 {attempt + 1} 失败: {str(e)}，{2 ** attempt} 秒后重试..."
                )
                await asyncio.sleep(2**attempt)  # 指数退避
                continue
            else:
                return {
                    "success": False,
                    "error": f"下载图像时发生错误: {str(e)}",
                }

    # 如果所有重试都失败了，返回错误
    return {
        "success": False,
        "error": "所有下载尝试都失败了",
    }


async def export_figma_images_to_folder(
    file_key: str,
    access_token: str,
    node_ids: str,
    format: str = "png",
    scale: float = 1.0,
    compression_quality: float = 0.85,
) -> Dict[str, Any]:
    """
    导出 Figma 图像并保存到指定文件夹

    Args:
        file_key: Figma文件的唯一标识符
        access_token: Figma个人访问令牌
        node_ids: 要导出图像的节点ID列表，用逗号分隔
        output_folder: 输出文件夹路径
        format: 图像格式 ("jpg", "png", "svg")
        scale: 图像缩放比例 (0.01 到 4)
        compression_quality: 压缩质量 (0.0-1.0)

    Returns:
        包含导出结果的字典
    """
    try:
        # 首先获取节点信息以获得节点名称
        node_names = {}
        try:
            # 构建请求头
            headers = {
                "X-Figma-Token": access_token,
                "Content-Type": "application/json",
            }

            # 构建节点信息API URL
            url = f"https://api.figma.com/v1/files/{file_key}/nodes"
            params = {
                "ids": node_ids,
                "depth": 1,
            }

            # 获取节点名称
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(url, headers=headers, params=params)

                if response.status_code == 200:
                    nodes_data = response.json()
                    nodes = nodes_data.get("nodes", {})

                    # 提取节点名称
                    for node_id, node_info in nodes.items():
                        if node_info and "document" in node_info:
                            node_name = node_info["document"].get("name", "").strip()
                            # 清理文件名，移除不合法字符
                            if node_name:
                                # 替换非法字符
                                import re

                                safe_name = re.sub(r'[<>:"/\\|?*]', "_", node_name)
                                safe_name = safe_name.strip()
                                if safe_name:
                                    node_names[node_id] = safe_name
        except Exception as e:
            # 如果获取节点信息失败，记录警告但继续执行
            print(f"⚠️ 获取节点名称失败，将使用默认文件名: {e}")

        # 获取图像URL
        images_data = await get_figma_images_data(
            file_key=file_key,
            access_token=access_token,
            node_ids=node_ids,
            format=format,
            scale=scale,
        )

        if not images_data.get("success"):
            return images_data

        images = images_data.get("images", {})
        if not images:
            return {
                "success": False,
                "error": "未获取到任何图像URL",
            }

        # 创建输出文件夹
        output_path = Path("temp-images")
        output_path.mkdir(parents=True, exist_ok=True)

        # 下载所有图像
        downloaded_files = []
        failed_downloads = []

        # 创建并发下载任务
        download_tasks = []

        for i, (node_id, image_url) in enumerate(images.items()):
            if not image_url:
                failed_downloads.append({"node_id": node_id, "error": "图像URL为空"})
                continue

            # 生成文件名：优先使用节点名称，否则使用默认格式
            if node_id in node_names:
                filename = f"{node_names[node_id]}.{format}"
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"figma_export_{node_id}_{timestamp}_{i+1}.{format}"

            # 创建下载任务
            task = download_image_from_url(
                image_url,
                output_path,
                filename,
                compression_quality=compression_quality,
            )
            download_tasks.append((node_id, task))

        # 并发执行所有下载任务
        if download_tasks:
            download_results = await asyncio.gather(
                *[task for _, task in download_tasks], return_exceptions=True
            )

            # 处理下载结果
            for (node_id, _), result in zip(download_tasks, download_results):
                if isinstance(result, Exception):
                    failed_downloads.append({"node_id": node_id, "error": str(result)})
                elif isinstance(result, dict) and result.get("success"):
                    downloaded_files.append(
                        {
                            "node_id": node_id,
                            "file_path": result["file_path"],
                            "filename": result["filename"],
                            "file_size": result["file_size"],
                            "uses_original_name": node_id in node_names,
                        }
                    )
                else:
                    error_msg = (
                        result.get("error", "下载失败")
                        if isinstance(result, dict)
                        else "下载失败"
                    )
                    failed_downloads.append({"node_id": node_id, "error": error_msg})

        result = {
            "success": True,
            "file_key": file_key,
            "format": format,
            "scale": scale,
            "downloaded_files": downloaded_files,
        }

        if failed_downloads:
            result["failed_downloads"] = failed_downloads
            result["failed_count"] = len(failed_downloads)

        return result

    except Exception as e:
        return handle_exception(e, "导出Figma图像到文件夹")
