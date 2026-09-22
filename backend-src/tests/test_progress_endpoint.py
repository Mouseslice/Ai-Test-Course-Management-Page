"""
进度API端点测试

该测试文件验证用户进度相关API端点的功能是否正常工作。
"""

import sys
import os
import pytest
from typing import Generator
from fastapi.testclient import TestClient
from datetime import datetime, UTC
from sqlalchemy.orm import Session
import uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.core.config import settings

current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(current_dir, "app", "db", "database.db")
os.environ["DATABASE_URL"] = settings.DATABASE_URL

# 导入项目模块
from app.db.base_class import Base
from app.db.database import engine, SessionLocal
from app.main import app
from app.models.participant import Participant
from app.models.user_progress import UserProgress
from app.schemas.participant import ParticipantCreate
from app.schemas.user_progress import UserProgressCreate
from app.crud import participant as participant_crud
from app.crud import progress as progress_crud


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    # 创建内存数据库表结构
    Base.metadata.create_all(bind=engine)
    
    # 初始化数据库会话
    db = SessionLocal()
    db.begin()
    try:
        yield db
    finally:
        db.rollback()
        db.close()
        # 清理数据库表
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client() -> Generator[TestClient, None, None]:
    """创建测试客户端"""
    with TestClient(app) as c:
        yield c


def test_get_user_progress(db: Session, client: TestClient):
    """测试获取用户进度API端点"""
    # 生成唯一的参与者ID
    participant_id = f"test_participant_{uuid.uuid4().hex[:8]}"
    
    # 创建参与者
    participant_data = ParticipantCreate(
        id=participant_id,
        group="experimental"
    )
    participant_crud.create(db, obj_in=participant_data)
    
    # 创建一些用户进度记录
    topic_ids = ["topic_1", "topic_2", "topic_3"]
    for topic_id in topic_ids:
        progress_data = UserProgressCreate(
            participant_id=participant_id,
            topic_id=topic_id
        )
        progress_crud.create(db, obj_in=progress_data)
    
    # 调用API端点
    # 使用正确的API路径前缀
    response = client.get(f"/api/v1/progress/participants/{participant_id}/progress")
    
    # 验证响应
    assert response.status_code == 200
    assert response.json() == {
        "code": 200,
        "message": "success",
        "data": {
            "completed_topics": topic_ids
        }
    }
    response_json = response.json()
    assert response_json["data"] is not None
    assert response_json["data"]["completed_topics"] is not None
    assert len(response_json["data"]["completed_topics"]) == len(topic_ids)
    for topic_id in topic_ids:
        assert topic_id in response_json["data"]["completed_topics"]
    
    print(f"获取用户进度API端点测试通过，完成主题数量: {len(topic_ids)}")


def test_get_user_progress_with_no_data(db: Session, client: TestClient):
    """测试获取不存在的用户进度API端点"""
    # 生成唯一的参与者ID（不存在于数据库中）
    participant_id = f"test_participant_{uuid.uuid4().hex[:8]}"
    
    # 调用API端点
    # 使用正确的API路径前缀
    response = client.get(f"/api/v1/progress/participants/{participant_id}/progress")
    
    # 验证响应
    assert response.status_code == 200
    response_json = response.json()
    assert response_json["data"] is not None
    assert response_json["data"]["completed_topics"] == []
    
    print("获取不存在的用户进度API端点测试通过")