"""教师端认证接口。

契约（与 teacher-frontend/src/api/auth-api.ts 对应）：
  - POST /api/v1/user/login    登录：校验口令，下发会话 Cookie，返回 SyncPBLUserVO
  - GET  /api/v1/user/current  当前用户：从 Cookie/Bearer 解析会话，返回 SyncPBLUserVO
  - POST /api/v1/user/logout   登出：销毁会话并清除 Cookie
  - POST /api/v1/user/register 注册：创建教师账号，返回新用户 id

约定：
  - 成功响应统一 StandardResponse(code=0)（教师端 request.ts 只认 code=0）；
  - 未登录的 current 返回 HTTP 200 + code=40100（教师端拦截器拒收并跳登录页）；
  - 登录态以 Cookie 为主，同时兼容 Authorization: Bearer <token>。
  - 会话解析 / Cookie 下发统一复用 app/api/deps.py。
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import SESSION_COOKIE, extract_token, get_current_user, set_session_cookie
from app.core import security
from app.crud.crud_user import user, user_session
from app.db.database import get_db
from app.models.user import User
from app.schemas.response import StandardResponse
from app.schemas.user import SyncPBLUserVO, UserLoginRequest, UserRegisterRequest

logger = logging.getLogger(__name__)

router = APIRouter()


def _ok(data, message: str = "success") -> StandardResponse:
    """统一成功包装：code=0 与教师端约定一致（区别于原有后端 code=200）。"""
    return StandardResponse(code=0, message=message, data=data)


def _vo_from_user(u: User) -> SyncPBLUserVO:
    """把 ORM 用户转成对外视图（时间序列化为 ISO 字符串，绝不含口令）。"""
    return SyncPBLUserVO(
        id=u.id,
        userAccount=u.user_account,
        userName=u.user_name,
        userAvatar=u.user_avatar,
        userProfile=u.user_profile,
        userRole=u.user_role,
        createTime=u.create_time.isoformat() if u.create_time else None,
        updateTime=u.update_time.isoformat() if u.update_time else None,
    )


@router.post("/register", response_model=StandardResponse[int])
def register(req: UserRegisterRequest, db: Session = Depends(get_db)) -> StandardResponse[int]:
    """教师注册：校验两次口令一致与账号唯一，创建用户后返回新用户 id。"""
    if req.userPassword != req.checkPassword:
        raise HTTPException(status_code=400, detail="两次输入的密码不一致")
    if user.get_by_account(db, req.userAccount) is not None:
        raise HTTPException(status_code=400, detail="账号已存在")
    new_user = user.create_user(
        db,
        user_account=req.userAccount,
        user_password=req.userPassword,
        user_role=req.userRole or "teacher",
    )
    logger.info("教师端注册新账号: %s", req.userAccount)
    return _ok(new_user.id, message="注册成功")


@router.post("/login", response_model=StandardResponse[SyncPBLUserVO])
def login(req: UserLoginRequest, response: Response,
          db: Session = Depends(get_db)) -> StandardResponse[SyncPBLUserVO]:
    """登录：校验账号口令，创建会话并下发 Cookie。"""
    account = req.userAccount.strip()
    if not account or not req.userPassword:
        raise HTTPException(status_code=400, detail="账号和密码不能为空")
    db_user = user.get_by_account(db, account)
    if db_user is None or not security.verify_password(req.userPassword, db_user.user_password):
        # 统一提示，不区分「账号不存在」与「密码错误」，避免账号枚举
        raise HTTPException(status_code=400, detail="账号或密码错误")
    session = user_session.create_session(db, db_user.id)
    set_session_cookie(response, session.token)
    logger.info("教师端登录成功: %s", account)
    return _ok(_vo_from_user(db_user), message="登录成功")


@router.get("/current", response_model=StandardResponse[SyncPBLUserVO])
def current(request: Request, db: Session = Depends(get_db)) -> StandardResponse[SyncPBLUserVO]:
    """获取当前登录用户；未登录返回 code=40100（HTTP 200）。"""
    db_user = get_current_user(request, db)
    if db_user is None:
        return StandardResponse(code=40100, message="未登录")
    return _ok(_vo_from_user(db_user))


@router.post("/logout", response_model=StandardResponse[None])
def logout(request: Request, response: Response,
           db: Session = Depends(get_db)) -> StandardResponse[None]:
    """登出：销毁会话并清除 Cookie（幂等，未登录也返回成功）。"""
    token = extract_token(request)
    if token:
        user_session.delete_session(db, token)
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return _ok(None, message="已退出登录")
