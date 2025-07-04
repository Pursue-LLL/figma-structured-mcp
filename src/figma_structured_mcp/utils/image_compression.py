#!/usr/bin/env python3
"""
图像压缩工具模块

提供图像压缩和尺寸调整的功能。
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None


def get_pngquant_path() -> Optional[str]:
    """获取pngquant可执行文件路径"""
    # 首先检查虚拟环境中的pngquant
    if hasattr(sys, "prefix"):
        venv_pngquant = Path(sys.prefix) / "bin" / "pngquant"
        if venv_pngquant.exists():
            return str(venv_pngquant)
    return None


def check_pngquant_available() -> bool:
    """检查pngquant是否可用"""
    return get_pngquant_path() is not None


async def compress_png_with_pngquant(
    image_path: Path,
    quality: float = 0.85,
) -> Dict[str, Any]:
    """
    使用pngquant压缩PNG图像

    Args:
        image_path: PNG图像文件路径
        quality: 压缩质量 (0.0-1.0)
                0.0 = 最大压缩（最低质量）
                1.0 = 最高质量压缩

    Returns:
        压缩结果字典
    """
    try:
        pngquant_path = get_pngquant_path()
        if not pngquant_path:
            return {
                "success": False,
                "error": "pngquant未找到。请安装: pip install pngquant-cli 或 brew install pngquant",
            }

        original_size = image_path.stat().st_size

        # 统一的百分比映射：quality直接映射到pngquant质量范围
        # quality=0.0 -> 质量范围 5-20 (最大压缩)
        # quality=1.0 -> 质量范围 85-95 (最高质量)
        min_quality = int(5 + quality * 80)  # 5 到 85
        max_quality = int(20 + quality * 75)  # 20 到 95

        # 确保范围合理
        min_quality = max(5, min(85, min_quality))
        max_quality = max(20, min(95, max_quality))

        # 确保max >= min
        if max_quality <= min_quality:
            max_quality = min_quality + 10

        # 构建pngquant命令
        cmd = [
            pngquant_path,
            "--quality",
            f"{min_quality}-{max_quality}",
            "--force",  # 覆盖输出文件
            "--output",
            str(image_path),  # 输出到原文件
            str(image_path),  # 输入文件
        ]

        # 执行pngquant命令
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30  # 30秒超时
        )

        if result.returncode == 0:
            compressed_size = image_path.stat().st_size
            compression_ratio = (
                (original_size - compressed_size) / original_size * 100
                if original_size > 0
                else 0
            )

            return {
                "success": True,
                "original_size": original_size,
                "compressed_size": compressed_size,
                "compression_ratio": compression_ratio,
                "size_reduction": original_size - compressed_size,
                "compression_method": "pngquant",
                "quality_range": f"{min_quality}-{max_quality}",
            }
        elif result.returncode == 99:
            # pngquant退出码99表示图像质量已经很好，无法在指定质量范围内压缩
            return {
                "success": False,
                "error": f"图像质量已经很好，无法在质量范围{min_quality}-{max_quality}内进一步压缩",
            }
        else:
            # pngquant失败
            error_msg = (
                result.stderr.strip()
                if result.stderr
                else f"退出码: {result.returncode}"
            )
            return {
                "success": False,
                "error": f"pngquant压缩失败: {error_msg}",
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "pngquant压缩超时",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"pngquant压缩出错: {str(e)}",
        }


async def compress_image(
    image_path: Path,
    quality: float = 0.85,
    optimize: bool = True,
) -> Dict[str, Any]:
    """
    压缩图像文件

    Args:
        image_path: 图像文件路径
        quality: 压缩质量 (0.0-1.0)
                0.0 = 最大压缩（最低质量）
                1.0 = 最高质量（最小压缩）
        optimize: 是否优化图像

    Returns:
        压缩结果字典

    注意:
        PNG格式压缩策略：
        - 只使用pngquant进行专业PNG压缩
        - 如果pngquant不可用，返回错误
        其他格式继续使用Pillow处理
    """
    try:
        original_size = image_path.stat().st_size

        if not PIL_AVAILABLE or Image is None:
            return {
                "success": False,
                "error": "图像压缩功能需要安装 Pillow 库: pip install Pillow",
            }

        # 确保quality在有效范围内
        quality = max(0.0, min(1.0, quality))

        # 获取文件格式
        file_format = image_path.suffix.upper().lstrip(".")

        # PNG格式：只使用pngquant
        if file_format == "PNG":
            pngquant_result = await compress_png_with_pngquant(image_path, quality)
            return pngquant_result

        # 使用Pillow处理其他格式
        with Image.open(image_path) as img:
            # 根据文件格式保存
            img_format = img.format or file_format

            if img_format.upper() in ["JPEG", "JPG"]:
                # 确保RGB模式用于JPEG
                if img.mode != "RGB":
                    img = img.convert("RGB")
                # 统一的百分比映射：quality直接映射到PIL质量
                # quality=0.0 -> PIL质量 1 (最大压缩)
                # quality=1.0 -> PIL质量 100 (最高质量)
                pil_quality = int(1 + quality * 99)
                pil_quality = max(1, min(100, pil_quality))
                img.save(
                    image_path, format="JPEG", quality=pil_quality, optimize=optimize
                )
            elif img_format.upper() == "WEBP":
                # 统一的百分比映射：quality直接映射到PIL质量
                # quality=0.0 -> PIL质量 1 (最大压缩)
                # quality=1.0 -> PIL质量 100 (最高质量)
                pil_quality = int(1 + quality * 99)
                pil_quality = max(1, min(100, pil_quality))
                img.save(
                    image_path, format="WEBP", quality=pil_quality, optimize=optimize
                )
            else:
                # 其他格式保持原样
                img.save(image_path, optimize=optimize)

        compressed_size = image_path.stat().st_size
        compression_ratio = (
            (original_size - compressed_size) / original_size * 100
            if original_size > 0
            else 0
        )

        return {
            "success": True,
            "original_size": original_size,
            "compressed_size": compressed_size,
            "compression_ratio": compression_ratio,
            "size_reduction": original_size - compressed_size,
            "compression_method": "pillow",
        }

    except Exception as e:
        return {"success": False, "error": f"压缩图像失败: {str(e)}"}


def get_image_info(image_path: Path) -> Dict[str, Any]:
    """
    获取图像基本信息

    Args:
        image_path: 图像文件路径

    Returns:
        图像信息字典
    """
    try:
        if not PIL_AVAILABLE or Image is None:
            return {
                "success": False,
                "error": "图像处理功能需要安装 Pillow 库: pip install Pillow",
            }

        with Image.open(image_path) as img:
            return {
                "success": True,
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.width,
                "height": img.height,
                "file_size": image_path.stat().st_size,
            }

    except Exception as e:
        return {"success": False, "error": f"获取图像信息失败: {str(e)}"}


def is_compression_supported(image_path: Path) -> bool:
    """
    检查图像格式是否支持压缩

    Args:
        image_path: 图像文件路径

    Returns:
        是否支持压缩
    """
    supported_formats = [".jpg", ".jpeg", ".png", ".webp"]
    return image_path.suffix.lower() in supported_formats
