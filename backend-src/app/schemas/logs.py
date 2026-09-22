"""教师端首页访问统计 DTO（对接 teacher-frontend/src/api/system/log-api.ts）。

与教师端其他接口约定一致：字段名 camelCase，成功响应 StandardResponse(code=0)。

后端没有独立的访问日志表，统计借用行为事件表 event_logs 聚合"活跃量"：
  - PV（浏览量） → 事件数（event_logs 行数）；
  - UV（访客数） → 去重参与人数（distinct participant_id）。
"""
from typing import List

from pydantic import BaseModel


class VisitStatsVO(BaseModel):
    """访问统计（对齐 VisitStatsVO）：
    今日/累计 PV、UV，以及相对昨日同一时间段的增长率（百分比）。
    """
    todayUvCount: int = 0
    totalUvCount: int = 0
    uvGrowthRate: float = 0.0
    todayPvCount: int = 0
    totalPvCount: int = 0
    pvGrowthRate: float = 0.0


class VisitTrendVO(BaseModel):
    """访问趋势（对齐 VisitTrendVO）：按天对齐的 PV / UV / IP 序列。"""
    dates: List[str] = []
    pvList: List[int] = []
    uvList: List[int] = []
    ipList: List[int] = []
