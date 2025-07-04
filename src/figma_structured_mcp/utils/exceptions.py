#!/usr/bin/env python3
"""
figma-structured-mcp 异常处理模块

统一处理 Figma API 相关的错误和异常。
"""

import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


def handle_api_error(response: httpx.Response, operation_name: str) -> Dict[str, Any]:
    """
    统一处理 Figma API 错误响应

    Args:
        response: HTTP 响应对象
        operation_name: 操作名称，用于日志记录

    Returns:
        标准化的错误响应字典
    """
    error_msgs = {
        403: "访问被拒绝：请检查访问令牌权限或文件访问权限",
        404: "文件未找到：请检查文件密钥是否正确",
        429: "请求频率过高：已达到API速率限制，请稍后重试",
    }

    error_msg = error_msgs.get(
        response.status_code, f"API请求失败，状态码: {response.status_code}"
    )

    try:
        error_data = response.json()
        if "err" in error_data:
            error_msg += f", 错误信息: {error_data['err']}"
        elif "message" in error_data:
            error_msg += f", 错误信息: {error_data['message']}"
    except:
        pass

    logger.error(f"Figma {operation_name} API错误 {response.status_code}: {error_msg}")
    return {
        "success": False,
        "error": error_msg,
        "status_code": response.status_code,
    }


def handle_exception(e: Exception, operation_name: str) -> Dict[str, Any]:
    """
    统一处理异常

    Args:
        e: 异常对象
        operation_name: 操作名称，用于日志记录

    Returns:
        标准化的错误响应字典
    """
    if isinstance(e, httpx.TimeoutException):
        error_msg = "请求超时：Figma API响应时间过长"
        logger.error(error_msg)
        return {"success": False, "error": error_msg, "status_code": 408}

    elif isinstance(e, httpx.RequestError):
        error_msg = f"网络请求错误: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg, "status_code": 0}

    else:
        error_msg = f"{operation_name}时发生未知错误: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg, "status_code": 500}


class FigmaAPIError(Exception):
    """Figma API 相关错误的基类"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class FigmaAuthenticationError(FigmaAPIError):
    """Figma API 认证错误"""

    def __init__(self, message: str = "访问被拒绝：请检查访问令牌权限"):
        super().__init__(message, 403)


class FigmaNotFoundError(FigmaAPIError):
    """Figma API 资源未找到错误"""

    def __init__(self, message: str = "文件未找到：请检查文件密钥是否正确"):
        super().__init__(message, 404)


class FigmaRateLimitError(FigmaAPIError):
    """Figma API 速率限制错误"""

    def __init__(self, message: str = "请求频率过高：已达到API速率限制，请稍后重试"):
        super().__init__(message, 429)
