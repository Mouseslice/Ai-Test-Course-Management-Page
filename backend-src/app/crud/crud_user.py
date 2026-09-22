"""教师端用户与会话的仓储实现。

数据访问一律走 SQLAlchemy ORM；会话带过期时间，读取时校验并顺手清理过期记录。
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core import security
from app.models.user import User, UserSession

# 会话默认有效期（天）
_SESSION_EXPIRE_DAYS = 7


class CRUDUser:
    """User 表操作。"""

    def get_by_id(self, db: Session, user_id: int) -> Optional[User]:
        """按主键取用户。"""
        return db.query(User).filter(User.id == user_id).first()

    def get_by_account(self, db: Session, user_account: str) -> Optional[User]:
        """按登录账号取用户（账号唯一）。"""
        return db.query(User).filter(User.user_account == user_account).first()

    def create_user(self, db: Session, *, user_account: str, user_password: str,
                    user_name: str = "", user_role: str = "teacher") -> User:
        """创建用户（口令先哈希再落库）。"""
        db_obj = User(
            user_account=user_account,
            user_password=security.hash_password(user_password),
            user_name=user_name or user_account,
            user_role=user_role,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


class CRUDUserSession:
    """UserSession 表操作。"""

    def create_session(self, db: Session, user_id: int) -> UserSession:
        """为某用户创建会话并返回（token 随机生成）。"""
        db_obj = UserSession(
            token=security.generate_session_token(),
            user_id=user_id,
            expire_time=datetime.now() + timedelta(days=_SESSION_EXPIRE_DAYS),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_valid_session(self, db: Session, token: str) -> Optional[UserSession]:
        """取未过期的会话；顺带清理已过期记录（登录失败路径的兜底清理）。"""
        session = db.query(UserSession).filter(UserSession.token == token).first()
        if session is None:
            return None
        if session.expire_time <= datetime.now():
            db.delete(session)
            db.commit()
            return None
        return session

    def delete_session(self, db: Session, token: str) -> None:
        """删除会话（登出）。"""
        db.query(UserSession).filter(UserSession.token == token).delete()
        db.commit()


user = CRUDUser()
user_session = CRUDUserSession()
