#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
figma-structured-mcp 统一启动脚本

支持三种运行模式：
1. stdio - 标准MCP模式（默认）
2. http - Streamable-HTTP模式
3. sse - SSE模式
"""

import sys
import argparse
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_stdio():
    """运行STDIO模式（标准MCP模式）"""

    from src.figma_structured_mcp.server import mcp

    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("\n服务器已停止")


def run_http(port=8000):
    """运行Streamable-HTTP模式"""
    logger.info("启动Streamable-HTTP模式...")
    logger.info("服务器地址: http://127.0.0.1:" + str(port) + "/mcp")

    # 优先使用FastMCP内置HTTP服务器（稳定性更好）
    logger.info("使用FastMCP内置HTTP服务器")

    from src.figma_structured_mcp.server import mcp

    try:
        mcp.run(transport="streamable-http", host="127.0.0.1", port=port, path="/mcp")
    except KeyboardInterrupt:
        logger.info("\n服务器已停止")


def run_sse(port=8001):
    """使用FastMCP内置方式运行SSE模式"""
    logger.info("启动SSE模式（使用FastMCP内置）...")
    logger.info("服务器地址: http://127.0.0.1:" + str(port))
    logger.info("SSE端点: http://127.0.0.1:" + str(port) + "/sse")
    logger.info("SSE传输，兼容性模式，请优先使用HTTP模式，提供更好的性能和稳定性")

    # 使用FastMCP内置的SSE运行方式
    from src.figma_structured_mcp.server import mcp

    try:
        mcp.run(transport="sse", host="127.0.0.1", port=port)
    except KeyboardInterrupt:
        logger.info("\n服务器已停止")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="figma-structured-mcp 统一启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--mode",
        "-m",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="运行模式 (默认: stdio)",
    )

    parser.add_argument(
        "--port", "-p", type=int, default=8000, help="HTTP/SSE模式的端口号 (默认: 8000)"
    )

    args = parser.parse_args()

    try:
        if args.mode == "stdio":
            run_stdio()
        elif args.mode == "http":
            run_http(args.port)
        elif args.mode == "sse":
            run_sse(args.port)
        else:
            logger.error("不支持的模式: " + args.mode)
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n再见！")
    except Exception as e:
        logger.error("启动失败: " + str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
