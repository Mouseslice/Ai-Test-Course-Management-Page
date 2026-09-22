"""教师端认证域的 Pydantic 模型。

与 teacher-frontend/src/api/auth-api.ts 的字段约定保持一致
（userAccount / userPassword / checkPassword / userRole / SyncPBLUserVO），
因此字段名直接用 camelCase（纯线上 DTO，不映射 ORM 列名）。
"""
from typing import Optional
from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    """注册请求：教师端固定带 userRole=teacher。"""
    userAccount: str = Field(..., min_length=2, max_length=32, description="登录账号")
    userPassword: str = Field(..., min_length=6, max_length=64, description="口令")
    checkPassword: str = Field(..., description="确认口令")
    userRole: str = Field("teacher", description="角色，教师端固定为 teacher")


class UserLoginRequest(BaseModel):
    """登录请求。"""
    userAccount: str = Field(..., description="登录账号")
    userPassword: str = Field(..., description="口令")


class SyncPBLUserVO(BaseModel):
    """当前登录用户视图（对齐教师端 SyncPBLUserVO，绝不包含口令哈希）。"""
    id: int
    userAccount: str
    userName: str = ""
    userAvatar: Optional[str] = None
    userProfile: Optional[str] = None
    userRole: str = "teacher"
    createTime: Optional[str] = None
    updateTime: Optional[str] = None
