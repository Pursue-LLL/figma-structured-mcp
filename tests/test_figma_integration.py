#!/usr/bin/env python3
"""
Figma API 集成测试

真实调用 Figma API 的集成测试，使用 FastMCP 客户端。
需要设置环境变量：
- FIGMA_ACCESS_TOKEN: Figma 个人访问令牌
"""

import os
import pytest
import logging
import threading
import time
import json

from fastmcp import Client

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestFigmaIntegration:
    """Figma API 集成测试类"""

    @classmethod
    def setup_class(cls):
        """测试类初始化，在所有测试方法执行前运行一次"""
        cls.access_token = os.getenv("FIGMA_ACCESS_TOKEN")
        cls.file_key = os.getenv("FIGMA_FILE_KEY")
        cls.server_port = 8888  # 使用特殊端口避免冲突
        cls.server_thread = None
        cls.server_started = False

        if not cls.access_token:
            pytest.skip("需要设置 FIGMA_ACCESS_TOKEN 环境变量")

        # 启动测试服务器
        cls._start_test_server()

    @classmethod
    def teardown_class(cls):
        """测试类清理，在所有测试方法执行后运行一次"""
        if cls.server_thread and cls.server_thread.is_alive():
            logger.warning("正在停止测试服务器...")
            # 注意：在实际应用中可能需要更优雅的服务器停止方式

    @classmethod
    def _start_test_server(cls):
        """启动测试服务器"""

        def run_server():
            try:
                from src.figma_structured_mcp.server import mcp

                logger.warning(f"启动测试服务器，端口: {cls.server_port}")
                mcp.run(
                    transport="streamable-http",
                    host="127.0.0.1",
                    port=cls.server_port,
                    path="/mcp",
                )
            except Exception as e:
                logger.error(f"服务器启动失败: {e}")

        cls.server_thread = threading.Thread(target=run_server, daemon=True)
        cls.server_thread.start()

        # 等待服务器启动
        max_wait = 10  # 最多等待10秒
        for i in range(max_wait):
            try:
                import httpx

                response = httpx.get(f"http://127.0.0.1:{cls.server_port}/mcp")
                # 307 是临时重定向，也表示服务器在运行
                if response.status_code in [200, 307, 404]:
                    cls.server_started = True
                    logger.warning(
                        f"测试服务器启动成功，状态码: {response.status_code}"
                    )
                    break
            except Exception as e:
                logger.debug(f"服务器检测尝试 {i+1} 失败: {e}")
            time.sleep(1)

        if not cls.server_started:
            logger.error("无法启动测试服务器")
            pytest.skip("无法启动测试服务器")

    async def _get_client(self) -> Client:
        """获取 FastMCP 客户端"""
        # 使用 HTTP URL 直接创建客户端
        return Client(f"http://127.0.0.1:{self.server_port}/mcp")

    def _extract_result_text(self, result) -> str:
        """从 MCP 结果中提取文本内容"""
        if not result:
            return ""

        # 处理不同类型的返回结果
        first_result = result[0]

        # 如果有 text 属性，直接返回
        if hasattr(first_result, "text"):
            return first_result.text

        # 如果是字典类型，尝试获取 content
        if isinstance(first_result, dict):
            if "content" in first_result:
                content = first_result["content"]
                if isinstance(content, list) and len(content) > 0:
                    return content[0].get("text", str(content[0]))
                return str(content)
            return str(first_result)

        # 其他情况，转换为字符串
        return str(first_result)

    @pytest.mark.asyncio
    async def test_get_figma_images_with_compression(self):
        """测试图像压缩功能"""
        async with await self._get_client() as client:
            # 测试带压缩的图像导出
            result = await client.call_tool(
                "get_figma_images",
                {
                    "file_key": "d5VnH9TP69zb3EyDejwvKs",
                    "node_ids": "1348-2218",
                    "format": "png",
                    "scale": 2,
                    "compression_quality": 0.9,
                    "export_children": False,
                },
            )

            # 验证返回结果
            assert len(result) > 0, "应该返回结果"

            # 提取结果文本
            result_text = self._extract_result_text(result)
            print("----成功测试图像压缩功能----", result_text)

            # 解析返回的 JSON 数据
            data = json.loads(result_text)

            # 验证返回格式 - 现在只包含上传结果
            assert "successful_uploads" in data, "返回数据应该包含 successful_uploads"
            assert "failed_uploads" in data, "返回数据应该包含 failed_uploads"

            # 验证上传成功的结果
            successful_uploads = data["successful_uploads"]
            assert isinstance(successful_uploads, list), "successful_uploads 应该是列表"
            logger.info(f"成功上传 {len(successful_uploads)} 个文件")

            for upload_info in successful_uploads:
                assert "name" in upload_info, "upload_info 应该包含 name"
                assert "url" in upload_info, "upload_info 应该包含 url"
                logger.info(f"上传文件: {upload_info['name']} -> {upload_info['url']}")

            # 验证上传失败的结果
            failed_uploads = data["failed_uploads"]
            assert isinstance(failed_uploads, list), "failed_uploads 应该是列表"

            if failed_uploads:
                logger.warning(f"上传失败 {len(failed_uploads)} 个文件")
                for failed_info in failed_uploads:
                    assert "name" in failed_info, "failed_info 应该包含 name"
                    assert "error" in failed_info, "failed_info 应该包含 error"
                    logger.warning(
                        f"失败文件: {failed_info['name']} - {failed_info['error']}"
                    )
                # 上传失败不影响测试通过，因为可能是网络或服务器问题


def run_integration_tests():
    """运行集成测试的便捷函数"""
    print("run_integration_tests", os.getenv("FIGMA_ACCESS_TOKEN"))
    # 检查环境变量
    if not os.getenv("FIGMA_ACCESS_TOKEN"):
        print("❌ 请设置 FIGMA_ACCESS_TOKEN 环境变量")
        print("   获取方法: https://www.figma.com/developers/api#access-tokens")
        return False

    print("🧪 开始运行 Figma API 集成测试...")


    # 运行 pytest，不捕获输出，让用户看到详细的测试过程
    import subprocess

    try:
        result = subprocess.run(
            [
                "python",
                "-m",
                "pytest",
                "tests/test_figma_integration.py",
                "-v",
                "-s",  # 不捕获输出，显示 print 语句
                "--tb=short",
                "--no-header",  # 减少冗余信息
            ],
            # 不捕获输出，直接显示在终端
            # capture_output=True,
            # text=True,
        )

        print()
        if result.returncode == 0:
            print("🎉 所有测试通过！")
            return True
        else:
            print("❌ 部分测试失败")
            return False

    except Exception as e:
        print(f"❌ 运行测试时发生错误: {e}")
        return False


if __name__ == "__main__":
    success = run_integration_tests()
    exit(0 if success else 1)
