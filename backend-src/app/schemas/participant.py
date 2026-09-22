# backend/app/schemas/participant.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class ParticipantBase(BaseModel):
    """参与者基础模型"""
    id: str = Field(..., description="系统中用户的唯一ID (UUID)")
    group: str = Field(..., description="实验分组，'experimental' 或 'control'")

class ParticipantCreate(ParticipantBase):
    """创建参与者请求模型"""
    pass

class ParticipantUpdate(BaseModel):
    """更新参与者请求模型"""
    group: Optional[str] = Field(None, description="实验分组，'experimental' 或 'control'")

class ParticipantInDBBase(ParticipantBase):
    """数据库中的参与者基础模型"""
    model_config = ConfigDict(from_attributes=True)

class Participant(ParticipantInDBBase):
    """参与者响应模型"""
    pass