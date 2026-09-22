"""教师端学情分析接口（/api/v1/teacher-portal/analysis/*）。

按课程维度聚合学生端学习数据，供教师端「学情分析」页面展示：
  - BKT 掌握度：Redis JSON `user_profile:{participant_id}` 的 `.bkt_model.{topic_id}`
    （学生端判题通过/失败后由 update_bkt_on_submission 更新），仅统计属于该课程知识点的 topic。
  - 学习进度：`UserProgress`（测试通过才记录 completed_at），按参与人统计完成知识点数。
  - 行为活跃度：`EventLog` 近 7 天按天计数（平台学习活跃度）。
  - 代码提交：`Submission` 中属于该课程知识点的提交次数 / 参与学生数。

课程知识点 id 集合来源（coursegen 发布时仅落 chapter_dict，未落 knowledge_dict/learning_path）：
  chapter_dict 各章节 sections.id（即 bodyPath）∪ knowledge_dict 的 keys。

约定与教师端其它接口一致：
  - 成功 StandardResponse(code=0)；未登录 HTTP 200 + code=40100；
  - 课程不存在返回 HTTPException 404 detail="课程不存在: {id}"。
"""
import logging
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.config.dependency_injection import get_redis_client
from app.crud.crud_course import course, course_content
from app.db.database import get_db
from app.models.course import CourseContent
from app.models.event import EventLog
from app.models.submission import Submission
from app.models.user_progress import UserProgress
from app.schemas.analysis import (
    ActivityPointVO,
    CourseAnalysisSummaryVO,
    CourseBriefVO,
    MasteryBucketVO,
    StudentProgressVO,
    SubmissionStatsVO,
    WeakTopicVO,
)
from app.schemas.response import StandardResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# 掌握度分布区间（5 档），index = min(mastery // 0.2, 4)
_MASTERY_BUCKETS: List[str] = ["0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
_ACTIVITY_DAYS = 7


def _ok(data: Any, message: str = "success") -> StandardResponse:
    """统一成功包装：code=0 与教师端约定一致。"""
    return StandardResponse(code=0, message=message, data=data)


def _unauthorized() -> StandardResponse:
    """未登录响应：HTTP 200 + code=40100，教师端拦截器据此跳登录页。"""
    return StandardResponse(code=40100, message="未登录")


def _course_topics(content: CourseContent) -> List[str]:
    """提取课程知识点 id 集合（章节 sections.id ∪ knowledge_dict keys），去重保序。"""
    topics: List[str] = []
    kd = content.knowledge_dict or {}
    if isinstance(kd, dict):
        topics.extend(str(k) for k in kd.keys())
    cd = content.chapter_dict or {}
    if isinstance(cd, dict):
        for ch in cd.values():
            if not isinstance(ch, dict):
                continue
            for sec in ch.get("sections") or []:
                sid = sec.get("id") if isinstance(sec, dict) else None
                if sid:
                    topics.append(str(sid))
    seen: Set[str] = set()
    return [t for t in topics if not (t in seen or seen.add(t))]


def _collect_mastery(redis_client: Any, topics: Optional[List[str]] = None
                     ) -> Dict[str, Dict[str, float]]:
    """扫描 Redis 中所有学生档案，返回 {participant_id: {topic_id: mastery_prob}}。

    topics 为 None 时收集全部知识点（学生端课程模式）；否则仅保留属于该课程
    知识点的 topic。Redis 异常时降级为空（不影响其它指标）。
    """
    topic_set = set(topics) if topics is not None else None
    out: Dict[str, Dict[str, float]] = {}
    try:
        for key in redis_client.scan_iter("user_profile:*", count=500):
            # scan_iter 在 decode_responses=False 时返回 bytes，先解码避免
            # str(bytes) 产生 "b'...'" 前缀导致 json().get 查不到 key
            key_str = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            pid = key_str.split(":", 1)[-1]
            try:
                doc = redis_client.json().get(key_str)
            except Exception:
                doc = None
            if not isinstance(doc, dict):
                continue
            bkt = doc.get("bkt_model")
            if not isinstance(bkt, dict):
                continue
            mastery: Dict[str, float] = {}
            for topic_id, model in bkt.items():
                if topic_set is None or topic_id in topic_set:
                    if isinstance(model, dict):
                        mp = model.get("mastery_prob")
                        if isinstance(mp, (int, float)):
                            mastery[str(topic_id)] = float(mp)
            if mastery:
                out[pid] = mastery
    except Exception as exc:  # Redis 不可用不影响其它指标
        logger.warning("analysis: read bkt from redis failed: %s", exc)
    return out


def _aggregate(db: Session, redis_client: Any, topics: Optional[List[str]],
               course_vo: CourseBriefVO) -> CourseAnalysisSummaryVO:
    """按给定知识点集合聚合学生端学习数据为学情总览。

    topics=None 表示学生端课程（全量数据）；否则按课程知识点集合过滤。
    """
    topic_set = set(topics) if topics is not None else None
    use_filter = topic_set is not None

    # ---- 学习进度：UserProgress（课程模式按知识点过滤，学生端模式全量） ----
    completed_by_participant: Counter = Counter()
    prog_topics: Set[str] = set()
    prog_query = db.query(UserProgress)
    if use_filter:
        prog_query = prog_query.filter(UserProgress.topic_id.in_(topic_set))
    for p in prog_query.all():
        completed_by_participant[p.participant_id] += 1
        prog_topics.add(p.topic_id)

    # ---- 代码提交：Submission ----
    sub_query = db.query(Submission)
    if use_filter:
        sub_query = sub_query.filter(Submission.topic_id.in_(topic_set))
    sub_rows = sub_query.all()
    sub_count = len(sub_rows)
    sub_participants: Set[str] = {s.participant_id for s in sub_rows}

    # 学生端全量模式的知识点总数 = 学生实际涉及的知识点（进度 ∪ 提交）并集，
    # 不能用 BKT 知识点数：真实学生 bkt_model 常为空，会导致 totalCount=0、
    # progressRate 溢出成数百个百分点。
    all_topics: Set[str] = prog_topics | {s.topic_id for s in sub_rows}
    total_topics = len(topic_set) if use_filter else (len(all_topics) or 1)

    # ---- 掌握度：Redis BKT 快照 ----
    mastery_by_participant = _collect_mastery(redis_client, topics)

    mastery_vals: List[float] = []
    topic_avg: Dict[str, List[float]] = defaultdict(list)
    for _, mastery in mastery_by_participant.items():
        for topic_id, val in mastery.items():
            mastery_vals.append(val)
            topic_avg[topic_id].append(val)

    avg_mastery = round(sum(mastery_vals) / len(mastery_vals), 4) if mastery_vals else None
    bucket_counts = [0] * len(_MASTERY_BUCKETS)
    for val in mastery_vals:
        bucket_counts[min(int(val // 0.2), len(_MASTERY_BUCKETS) - 1)] += 1
    mastery_distribution = [
        MasteryBucketVO(bucket=b, count=c)
        for b, c in zip(_MASTERY_BUCKETS, bucket_counts)
    ]

    weak_topics = sorted(
        (
            WeakTopicVO(topicId=t, avgMastery=round(sum(vs) / len(vs), 4), studentCount=len(vs))
            for t, vs in topic_avg.items()
        ),
        key=lambda x: x.avgMastery,
    )[:5]

    # ---- 学生进度排行（按完成数降序，Top 20） ----
    student_progress = sorted(
        (
            StudentProgressVO(
                participantId=pid,
                completedCount=c,
                totalCount=len(topic_set) if use_filter else len(all_topics),
                # 同一学生同一知识点可能多次通过判题（多次记录），封顶 1.0 避免进度条溢出
                progressRate=round(min(c / total_topics, 1.0), 4),
            )
            for pid, c in completed_by_participant.items()
        ),
        key=lambda x: x.completedCount,
        reverse=True,
    )[:20]

    # ---- 活跃度趋势：近 7 天按天计数（平台学习活跃度） ----
    today = date.today()
    start = today - timedelta(days=_ACTIVITY_DAYS - 1)
    day_rows = (
        db.query(func.date(EventLog.timestamp).label("d"), func.count(EventLog.id))
        .filter(EventLog.timestamp >= start)
        .group_by("d")
        .all()
    )
    day_map = {str(d): c for d, c in day_rows if d}
    activity_trend = [
        ActivityPointVO(
            date=(start + timedelta(days=i)).isoformat(),
            count=day_map.get((start + timedelta(days=i)).isoformat(), 0),
        )
        for i in range(_ACTIVITY_DAYS)
    ]

    students = (
        set(completed_by_participant)
        | sub_participants
        | set(mastery_by_participant)
    )

    return CourseAnalysisSummaryVO(
        course=CourseBriefVO(
            courseId=course_vo.courseId,
            courseCode=course_vo.courseCode,
            title=course_vo.title,
            studentCount=len(students),
            knowledgeCount=len(topic_set) if use_filter else len(all_topics),
        ),
        masteryDistribution=mastery_distribution,
        avgMastery=avg_mastery,
        weakTopics=weak_topics,
        studentProgress=student_progress,
        activityTrend=activity_trend,
        submissionStats=SubmissionStatsVO(
            submissionCount=sub_count,
            studentCount=len(sub_participants),
        ),
    )


@router.get("/course/{course_id}/summary",
            response_model=StandardResponse[CourseAnalysisSummaryVO])
def course_analysis_summary(request: Request, course_id: int,
                            db: Session = Depends(get_db)) -> StandardResponse[CourseAnalysisSummaryVO]:
    """课程学情分析总览：掌握度分布/薄弱点/学生进度/活跃度/提交统计。

    course_id <= 0 时表示"学生端课程"（聚合学生端全量学习数据，即学生端
    唯一那门 Web 前端课的学习情况），不做按课程知识点过滤。
    """
    if get_current_user(request, db) is None:
        return _unauthorized()

    if course_id <= 0:
        # 学生端课程模式：直接聚合全量学生学习数据
        vo = _aggregate(
            db, get_redis_client(), None,
            CourseBriefVO(courseId=0, courseCode="STUDENT",
                          title="学生端 Web 前端课程"),
        )
        return _ok(vo)

    row = course.get(db, course_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")

    content = course_content.get_by_course_id(db, course_id)
    topics = _course_topics(content) if content else []
    vo = _aggregate(
        db, get_redis_client(), topics,
        CourseBriefVO(courseId=row.id, courseCode=row.course_code, title=row.title),
    )
    return _ok(vo)
