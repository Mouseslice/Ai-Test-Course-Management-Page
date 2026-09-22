#!/usr/bin/env python3
"""
测试会话管理、用户注册、身份验证相关接口
文件风格参考 test_content_loader.py
"""

import os
import sys
import pytest
from pathlib import Path
from fastapi import FastAPI, Depends, status
from fastapi.testclient import TestClient

# 添加项目根目录到 Python 路径
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)
# 设置测试环境变量，确保 Pydantic Settings 可以初始化
os.environ["TUTOR_OPENAI_API_KEY"] = "test-key"
os.environ["TUTOR_EMBEDDING_API_KEY"] = "test-key"
os.environ["TUTOR_TRANSLATION_API_KEY"] = "test-key"
os.environ["APP_ENV"] = "testing"

# 导入项目模块
from app.api.endpoints import session as session_module
from app.schemas.session import SessionInitiateRequest, SessionInitiateResponse
from app.schemas.response import StandardResponse
from app.services.user_state_service import UserStateService

# 使用一个简单的 mock UserStateService 避免真实 DB 依赖
class MockUserStateService(UserStateService):
    def get_or_create_profile(self, participant_id, db, group):
        # 模拟新用户和老用户
        is_new_user = participant_id.startswith("new_")
        profile = type("Profile", (), {"participant_id": participant_id})
        return profile, is_new_user

# 创建一个独立 FastAPI app 供测试
def create_test_app():
    app = FastAPI()
    
    # 覆盖依赖注入
    app.dependency_overrides[session_module.get_user_state_service] = lambda: MockUserStateService()
    
    # 添加测试路由
    app.include_router(session_module.router, prefix="/session")
    return app

@pytest.fixture(scope="module")
def client():
    """初始化 FastAPI 测试客户端"""
    app = create_test_app()
    return TestClient(app)

class TestSessionEndpoints:
    """会话接口测试类"""
    
    def test_initiate_new_user_session(self, client: TestClient):
        """测试新用户会话初始化"""
        payload = {"participant_id": "new_user_001", "group": "A"}
        response = client.post("/session/initiate", json=payload)
        assert response.status_code == status.HTTP_201_CREATED
        resp_json = response.json()
        assert "data" in resp_json
        data = resp_json["data"]
        assert data["participant_id"] == "new_user_001"
        assert data["is_new_user"] is True
        print("新用户会话初始化测试通过")

    def test_initiate_existing_user_session(self, client: TestClient):
        """测试已存在用户会话初始化"""
        payload = {"participant_id": "existing_user_001", "group": "A"}
        response = client.post("/session/initiate", json=payload)
        assert response.status_code == status.HTTP_200_OK
        resp_json = response.json()
        assert "data" in resp_json
        data = resp_json["data"]
        assert data["participant_id"] == "existing_user_001"
        assert data["is_new_user"] is False
        print("已存在用户会话初始化测试通过")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
