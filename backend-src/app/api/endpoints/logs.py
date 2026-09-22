"""教师端首页访问统计接口（/api/v1/logs/*）。

对接 teacher-frontend/src/api/system/log-api.ts 的 getVisitStats / getVisitTrend
（首页 dashboard 在 USE_MOCK=false 时调用）。

后端没有独立访问日志表，借用行为事件表 event_logs 聚合"活跃量"：
  - PV（浏览量） → 事件数（event_logs 行数）；
  - UV（访客数） → 去重参与人数（distinct participant_id）；
  - 同比口径 = 今日 vs 昨日。

约定（与教师端其他接口一致）：
  - 成功响应统一 StandardResponse(code=0)；
  - 未登录返回 HTTP 200 + code=40100（教师端拦截器跳登录页）。
"""
import logging
from datetime import date, datetime, time as dtime, timedelta
from typing import Any, List, Tuple

import pytz
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.database import get_db
from app.models.event import EventLog
from app.schemas.logs import VisitStatsVO, VisitTrendVO
from app.schemas.response import StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# 事件日志时间统一按 Asia/Shanghai 落库（见 models/event.py 默认值），
# 统计口径也以该时区的自然日为准，避免容器本地时区（UTC）导致的日期偏差
_TZ = pytz.timezone("Asia/Shanghai")


def _china_today() -> date:
    """返回上海时区的今天。"""
    return datetime.now(_TZ).date()


def _day_boundaries(d: date) -> Tuple[datetime, datetime]:
    """返回某自然日 [00:00:00, 23:59:59] 的起止时间（无时区信息，与库内时间对齐）。"""
    return datetime.combine(d, dtime.min), datetime.combine(d, dtime.max)


def _counts_for(db: Session, d: date) -> Tuple[int, int]:
    """统计某天的 (PV, UV)：PV=事件数，UV=去重参与人数。"""
    start, end = _day_boundaries(d)
    base = db.query(EventLog).filter(EventLog.timestamp >= start, EventLog.timestamp <= end)
    pv = base.count()
    uv = base.with_entities(func.count(func.distinct(EventLog.participant_id))).scalar() or 0
    return pv, uv


def _growth_rate(current: int, previous: int) -> float:
    """相对增长率（百分比，保留 1 位小数）：昨日为 0 时，今日有量记 100.0，否则 0.0。"""
    if previous > 0:
        return round((current - previous) / previous * 100, 1)
    return 100.0 if current > 0 else 0.0


@router.get("/visit-stats", response_model=StandardResponse[VisitStatsVO])
def visit_stats(request: Request, db: Session = Depends(get_db)) -> StandardResponse[VisitStatsVO]:
    """访问统计：今日/累计 PV、UV 及相对昨日增长率。"""
    if get_current_user(request, db) is None:
        return StandardResponse(code=40100, message="未登录")

    today = _china_today()
    yesterday = today - timedelta(days=1)
    today_pv, today_uv = _counts_for(db, today)
    yesterday_pv, yesterday_uv = _counts_for(db, yesterday)

    total_pv = db.query(EventLog).count()
    total_uv = db.query(func.count(func.distinct(EventLog.participant_id))).scalar() or 0

    return StandardResponse(code=0, data=VisitStatsVO(
        todayUvCount=today_uv,
        totalUvCount=total_uv,
        uvGrowthRate=_growth_rate(today_uv, yesterday_uv),
        todayPvCount=today_pv,
        totalPvCount=total_pv,
        pvGrowthRate=_growth_rate(today_pv, yesterday_pv),
    ))


@router.get("/visit-trend", response_model=StandardResponse[VisitTrendVO])
def visit_trend(request: Request, startDate: str, endDate: str,
                db: Session = Depends(get_db)) -> StandardResponse[VisitTrendVO]:
    """访问趋势：按天对齐的 PV / UV 序列（起止日期均含，含多天时自动补齐 0 值天）。"""
    if get_current_user(request, db) is None:
        return StandardResponse(code=40100, message="未登录")

    try:
        start = datetime.strptime(startDate, "%Y-%m-%d").date()
        end = datetime.strptime(endDate, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="日期格式应为 YYYY-MM-DD")

    if start > end:
        start, end = end, start

    dates: List[str] = []
    pv_list: List[int] = []
    uv_list: List[int] = []
    cursor = start
    while cursor <= end:
        pv, uv = _counts_for(db, cursor)
        dates.append(cursor.strftime("%Y-%m-%d"))
        pv_list.append(pv)
        uv_list.append(uv)
        cursor += timedelta(days=1)

    return StandardResponse(code=0, data=VisitTrendVO(
        dates=dates,
        pvList=pv_list,
        uvList=uv_list,
        # 无访问 IP 数据，置 0 保证契约完整（前端趋势图只绘制 PV/UV）
        ipList=[0] * len(dates),
    ))
