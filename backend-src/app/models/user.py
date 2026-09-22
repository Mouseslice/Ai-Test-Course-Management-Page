"""教师端用户与会话的持久化模型。

教师端（teacher-frontend）走 Session + Cookie 认证：
  - users 表存账号与口令哈希（PBKDF2-HMAC-SHA256，见 app/core/security.py）；
  - user_sessions 表存登录会话（随机 token + 过期时间）。
会话落库而非进程内存，保证后端容器重启（StatReload / 部署）后登录态不丢，
且多个 worker 天然共享同一份会话数据。
"""
from datetime import datetime
import pytz
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.db.base_class import Base


def _now() -> datetime:
    """当前时间（上海时区），用于各表的时间列默认值。"""
    return datetime.now(pytz.timezone('Asia/Shanghai'))


class User(Base):
    """教师端用户。

    Attributes:
        id: 自增主键
        user_account: 登录账号（唯一）
        user_password: 口令哈希（格式见 app/core/security.py，绝不明文存储）
        user_name: 显示昵称
        user_avatar: 头像 URL（可空）
        user_profile: 个人简介（可空）
        user_role: 角色，默认 teacher
        create_time / update_time: 创建与更新时间（上海时区）
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_account = Column(String(64), unique=True, index=True, nullable=False)
    user_password = Column(String(256), nullable=False)
    user_name = Column(String(64), nullable=False, default="")
    user_avatar = Column(String(512), nullable=True)
    user_profile = Column(Text, nullable=True)
    user_role = Column(String(16), nullable=False, default="teacher")
    create_time = Column(DateTime, default=_now, nullable=False)
    update_time = Column(DateTime, default=_now, onupdate=_now, nullable=False)


class UserSession(Base):
    """一次登录会话（Cookie 携带 token，落库保证重启 / 多 worker 共享）。

    Attributes:
        token: 随机会话令牌（登录时下发到 Cookie，HttpOnly）
        user_id: 对应用户 id
        expire_time: 过期时间（默认 7 天）
    """
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, index=True, nullable=False)
    expire_time = Column(DateTime, nullable=False)
    create_time = Column(DateTime, default=_now, nullable=False)
