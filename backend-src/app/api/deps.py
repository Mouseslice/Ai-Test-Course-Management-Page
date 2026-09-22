"""教师端接口共享依赖。

把会话解析 / Cookie 下发统一收口到这里，供 /api/v1/user/* 与 /api/v1/course/*
等教师端接口复用：

  - 登录态以 Cookie 为主，同时兼容 Authorization: Bearer <token>；
  - get_current_user 返回 Optional[User]，未登录返回 None，由各端点决定
    返回 code=40100（HTTP 200，教师端拦截器据此跳登录页）还是其他处理。
"""
from typing import Optional

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.crud.crud_user import user, user_session
from app.models.user import User

# 会话 Cookie 名称与有效期（秒），与 crud 中 7 天一致
SESSION_COOKIE = "pbl_session"
SESSION_MAX_AGE = 7 * 24 * 3600


def extract_token(request: Request) -> Optional[str]:
    """从 Cookie 或 Authorization: Bearer 头提取会话 token，都没有返回 None。"""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        return token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer "):].strip()
    return None


def get_current_user(request: Request, db: Session) -> Optional[User]:
    """解析当前登录用户；未登录返回 None。"""
    token = extract_token(request)
    if not token:
        return None
    session = user_session.get_valid_session(db, token)
    if session is None:
        return None
    return user.get_by_id(db, session.user_id)


def set_session_cookie(response: Response, token: str) -> None:
    """下发会话 Cookie（HttpOnly，JS 不可读；SameSite=Lax 兼顾跨端口同站请求）。"""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        path="/",
    )
