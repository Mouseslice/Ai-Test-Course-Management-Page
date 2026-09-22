# backend/tests/test_session_endpoints.py
import sys
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from dotenv import load_dotenv

# 手动加载项目根目录下的 .env 文件
load_dotenv(Path(__file__).parent.parent.parent / ".env")
# 将 backend 目录添加到 sys.path 中
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_path)

from app.main import app
from app.core.config import settings
from app.services.user_state_service import UserStateService

client = TestClient(app)


class TestSessionEndpoints:
    """
    集成测试 Session 相关接口，使用真实数据库和环境变量
    """

    def test_initiate_new_user_session(self):
        """
        测试为一个新的用户创建会话
        """
        import uuid
        participant_id = str(uuid.uuid4())

        response = client.post(
            f"{settings.API_V1_STR}/session/initiate",
            json={"participant_id": participant_id, "group": "integration-test"}
        )

        assert response.status_code in (200, 201)
        data = response.json()
        assert "data" in data
        assert "participant_id" in data["data"]
        assert data["data"]["participant_id"] == participant_id
        assert data["data"]["is_new_user"] is True

    def test_initiate_existing_user_session(self):
        """
        测试为一个已有用户创建会话
        """
        participant_id = "integration_test_participant"

        # 先保证用户存在
        response1 = client.post(
            f"{settings.API_V1_STR}/session/initiate",
            json={"participant_id": participant_id, "group": "integration-test"}
        )
        assert response1.status_code in (200, 201)

        # 再次发起会话，应该标记为已有用户
        response2 = client.post(
            f"{settings.API_V1_STR}/session/initiate",
            json={"participant_id": participant_id, "group": "integration-test"}
        )
        assert response2.status_code in (200, 201)
        data = response2.json()
        assert "data" in data
        assert data["data"]["participant_id"] == participant_id
        assert data["data"]["is_new_user"] is False
    
    @pytest.mark.parametrize("invalid_username", ["", "a", "x"*51])
    def test_invalid_username_length(self, invalid_username):
        """测试 username 不合法（长度过短或过长）返回 422"""
        response = client.post(
            f"{settings.API_V1_STR}/session/initiate",
            json={"username": invalid_username, "group": "test-group"}
        )
        assert response.status_code == 422

    def test_idempotent_username_registration(self):
        """多次注册同一 participant_id 返回相同 participant_id"""
        participant_id = "integration_test_idempotent"

        # 第一次请求
        response1 = client.post(
            f"{settings.API_V1_STR}/session/initiate",
            json={"participant_id": participant_id, "group": "test-group"}
        )
        assert response1.status_code in (200, 201)
        pid1 = response1.json()["data"]["participant_id"]

        # 第二次请求
        response2 = client.post(
            f"{settings.API_V1_STR}/session/initiate",
            json={"participant_id": participant_id, "group": "test-group"}
        )
        assert response2.status_code in (200, 201)
        pid2 = response2.json()["data"]["participant_id"]

        assert pid1 == pid2
