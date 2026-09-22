import os
import sys
import types
import asyncio
from unittest.mock import MagicMock, patch

import pytest


# 将 backend 目录添加到 sys.path 中，便于按项目方式导入
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)


def _import_llm_gateway_with_fake_openai():
    """在替换掉 openai 与 app.core.config 后再导入目标模块，避免真实依赖与 Pydantic 校验。"""
    # 伪造 openai 模块
    fake_openai_module = types.SimpleNamespace(OpenAI=MagicMock())

    # 伪造 app.core.config.settings，按当前环境变量构造
    fake_settings = types.SimpleNamespace(
        TUTOR_OPENAI_API_KEY=os.getenv("TUTOR_OPENAI_API_KEY", "test-key"),
        TUTOR_OPENAI_API_BASE=os.getenv("TUTOR_OPENAI_API_BASE", "https://fake.base"),
        TUTOR_OPENAI_MODEL=os.getenv("TUTOR_OPENAI_MODEL", "gpt-test"),
        LLM_MAX_TOKENS=int(os.getenv("LLM_MAX_TOKENS", "65536")),
        LLM_TEMPERATURE=float(os.getenv("LLM_TEMPERATURE", "0.7")),
    )
    fake_config_module = types.ModuleType("app.core.config")
    setattr(fake_config_module, "settings", fake_settings)

    with patch.dict(sys.modules, {
        "openai": fake_openai_module,
        "app.core.config": fake_config_module,
    }):
        from app.services.llm_gateway import LLMGateway  # type: ignore
    return LLMGateway, fake_openai_module


def _run(coro):
    """兼容无 pytest-asyncio 的环境，直接运行协程。"""
    return asyncio.run(coro)


def test_get_completion_success_uses_env_and_returns_content(monkeypatch):
    # 1) 准备：设置环境变量
    monkeypatch.setenv("TUTOR_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("TUTOR_OPENAI_API_BASE", "https://fake.base")
    monkeypatch.setenv("TUTOR_OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("LLM_MAX_TOKENS", "123")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.42")
    # 配置其它必须的 settings 环境变量，避免 Pydantic 验证失败
    monkeypatch.setenv("TUTOR_EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setenv("TUTOR_TRANSLATION_API_KEY", "trans-key")

    # 2) 使用假的 openai 导入 LLMGateway
    LLMGateway, fake_openai = _import_llm_gateway_with_fake_openai()

    # 3) 构造返回的响应对象
    response_mock = MagicMock()
    message_mock = MagicMock()
    message_mock.content = "Hello from LLM"
    choice_mock = MagicMock()
    choice_mock.message = message_mock
    response_mock.choices = [choice_mock]

    # 4) 获取 client mock 并配置 create 返回值
    client_instance = fake_openai.OpenAI.return_value
    client_instance.chat.completions.create.return_value = response_mock

    # 5) 将 asyncio.to_thread 改为同步执行，便于断言参数
    def sync_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with patch("asyncio.to_thread", side_effect=sync_to_thread):
        gateway = LLMGateway()

        result = _run(
            gateway.get_completion(
                system_prompt="You are a tutor",
                messages=[{"role": "user", "content": "Hi"}],
            )
        )

    # 6) 断言返回值
    assert result == "Hello from LLM"

    # 7) 断言客户端初始化参数包含期望值（导入时模块级也会实例化一次，因此不限定调用次数）
    assert any(
        call.kwargs == {"api_key": "test-key", "base_url": "https://fake.base"}
        for call in fake_openai.OpenAI.call_args_list
    )

    # 8) 断言调用 create 的参数（包含 system 提示词，默认 max_tokens/temperature）
    call_kwargs = client_instance.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-test"
    assert call_kwargs["max_tokens"] == 123
    assert call_kwargs["temperature"] == 0.42
    assert call_kwargs["messages"][0] == {"role": "system", "content": "You are a tutor"}
    assert call_kwargs["messages"][1] == {"role": "user", "content": "Hi"}


def test_get_completion_empty_choices_returns_default(monkeypatch):
    # 1) 准备：设置基础环境变量（模型名等），避免依赖 settings 默认
    monkeypatch.setenv("TUTOR_OPENAI_API_KEY", "k")
    monkeypatch.setenv("TUTOR_OPENAI_API_BASE", "https://fake.base")
    monkeypatch.setenv("TUTOR_OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("TUTOR_EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setenv("TUTOR_TRANSLATION_API_KEY", "trans-key")

    LLMGateway, fake_openai = _import_llm_gateway_with_fake_openai()

    response_mock = MagicMock()
    response_mock.choices = []  # 空结果分支

    client_instance = fake_openai.OpenAI.return_value
    client_instance.chat.completions.create.return_value = response_mock

    def sync_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with patch("asyncio.to_thread", side_effect=sync_to_thread):
        gateway = LLMGateway()
        result = _run(
            gateway.get_completion(
                system_prompt="S",
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                temperature=0.1,
            )
        )

    # 返回默认提示
    assert "couldn't generate a response" in result

    # 覆盖参数应被传递
    call_kwargs = client_instance.chat.completions.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 5
    assert call_kwargs["temperature"] == 0.1


def test_get_completion_exception_returns_error_message(monkeypatch):
    monkeypatch.setenv("TUTOR_OPENAI_API_KEY", "k")
    monkeypatch.setenv("TUTOR_OPENAI_API_BASE", "https://fake.base")
    monkeypatch.setenv("TUTOR_OPENAI_MODEL", "gpt-test")
    monkeypatch.setenv("TUTOR_EMBEDDING_API_KEY", "embed-key")
    monkeypatch.setenv("TUTOR_TRANSLATION_API_KEY", "trans-key")

    LLMGateway, fake_openai = _import_llm_gateway_with_fake_openai()

    client_instance = fake_openai.OpenAI.return_value
    client_instance.chat.completions.create.side_effect = Exception("boom")

    def sync_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    with patch("asyncio.to_thread", side_effect=sync_to_thread):
        gateway = LLMGateway()
        result = _run(
            gateway.get_completion(
                system_prompt="S",
                messages=[{"role": "user", "content": "Hi"}],
            )
        )

    assert "I apologize" in result
    assert "boom" in result


