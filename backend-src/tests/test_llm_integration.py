import os
import sys
import pytest

# 将 backend 目录添加到 sys.path 中，便于按项目方式导入
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from app.core.config import settings
from app.services.llm_gateway import LLMGateway

@pytest.mark.integration
async def test_llm_gateway_real_api_call():
    """
    使用真实API进行简单调用验证
    这是一个轻量级的集成测试，只会产生很少的token消耗
    """
    # 检查关键配置是否存在
    required_attributes = ["TUTOR_OPENAI_API_KEY", "TUTOR_OPENAI_API_BASE", "TUTOR_OPENAI_MODEL"]
    if any(not getattr(settings, attr, None) for attr in required_attributes):
        pytest.skip(
            "Skipping integration test: One or more required settings "
            "(TUTOR_OPENAI_API_KEY, TUTOR_OPENAI_API_BASE, TUTOR_OPENAI_MODEL) are missing."
        )

    try:
        # LLMGateway now reads from settings, so it's ready to go
        gateway = LLMGateway()

        # 发送一个简单的测试请求
        # 使用很低的max_tokens和temperature来减少消耗
        result = await gateway.get_completion(
            system_prompt="You are a helpful assistant.",
            messages=[{"role": "user", "content": "Say 'Hello, World!' and nothing else."}],
            max_tokens=10,
            temperature=0.0
        )

        # 验证返回结果
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Hello" in result or "hello" in result

        print(f"\nAPI call successful. Response: {result}")

    except Exception as e:
        pytest.fail(f"Real API call failed: {e}")

if __name__ == "__main__":
    import asyncio
    # To run this file directly for debugging
    asyncio.run(test_llm_gateway_real_api_call())
