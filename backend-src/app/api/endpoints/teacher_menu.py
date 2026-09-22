r"""教师端菜单路由接口（/api/v1/teacher-portal/menus/*）。

对接前端 d:\PBL\teacher-frontend\teacher-frontend\src\api\system\menu-api.ts：
  - GET /api/v1/teacher-portal/menus/routes  返回当前登录人的动态路由，用于生成菜单。

说明：教师端前端把全部页面（首页/课程生成/课程管理等）都写死在
src\router\index.ts 的 constantRoutes 里，侧边栏渲染 permissionStore.routes
= [...constantRoutes, ...dynamicRoutes]；若后端再返回同样的菜单树会造成
重复菜单，因此这里返回空动态路由（前端已含全部页面，无需后端下发）。
"""
from typing import Any, List

from fastapi import APIRouter

from app.schemas.response import StandardResponse

router = APIRouter()


def _ok(data: Any, message: str = "success") -> StandardResponse:
    """统一成功包装：code=0 与教师端约定一致（区别于原有后端 code=200）。"""
    return StandardResponse(code=0, message=message, data=data)


@router.get("/menus/routes", response_model=StandardResponse[List[Any]])
def get_menu_routes() -> StandardResponse[List[Any]]:
    """获取教师端动态路由。

    返回空数组：教师端页面已全部内置于前端 constantRoutes，
    无需后端下发额外动态路由（返回重复菜单树会造成侧边栏重复项）。
    """
    return _ok([], message="success")
