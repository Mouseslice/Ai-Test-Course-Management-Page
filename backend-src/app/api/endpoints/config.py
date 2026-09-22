from fastapi import APIRouter
from app.core.config import settings
from app.schemas.config import FrontendConfig
from app.schemas.response import StandardResponse # 使用标准响应格式

router = APIRouter()

@router.get("/", response_model=StandardResponse[FrontendConfig])
def get_frontend_config():
    """
    为前端应用程序提供安全、非敏感的配置变量集合。
    """
    config_data = FrontendConfig(
        api_base_url=settings.API_V1_STR,
        backend_port=settings.BACKEND_PORT
    )
    return StandardResponse(data=config_data)