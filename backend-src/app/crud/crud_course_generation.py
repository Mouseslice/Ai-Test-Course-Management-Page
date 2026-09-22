"""课程生成引擎的仓储实现。

对应 Go 侧 coursegen/repository.go 的 Repository 接口 + SQLRepository 实现。
所有数据访问都走 SQLAlchemy ORM；关键写操作带 from-status 乐观并发（防止两个执行者
同时推进同一个 job），token 用累加而非覆盖（episode 并发跑，读-改-写会丢更新）。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.crud.base_improved import CRUDBaseImproved
from app.models.course_generation import (
    CourseGenerationEvent,
    CourseGenerationJob,
    CourseGenerationReview,
    CourseGenerationWorkspaceFile,
)
from app.schemas.course_generation import CourseGenerationJobCreate
from app.services.course_generation import state
from app.services.course_generation.errors import (
    JobNotFoundError,
    ReviewNotFoundError,
    StaleStatusError,
    WorkspaceFileNotFoundError,
)


class CRUDCourseGeneration(CRUDBaseImproved[CourseGenerationJob, CourseGenerationJobCreate, Dict[str, Any]]):
    """课程生成域的全部持久化操作，统一收敛在一个 CRUD 对象里。"""

    # ------------------------------ jobs ------------------------------

    def create_job(self, db: Session, *, job_uid: str, user_id: str,
                   request_payload: Dict[str, Any], token_budget: int) -> CourseGenerationJob:
        """创建一条 job 记录。"""
        db_obj = CourseGenerationJob(
            job_uid=job_uid,
            user_id=user_id,
            request_payload=request_payload or {},
            token_budget=token_budget,
            status=state.Status.CREATED.value,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_job(self, db: Session, job_id: int) -> Optional[CourseGenerationJob]:
        """按内部 id 取 job。"""
        return db.query(CourseGenerationJob).filter(CourseGenerationJob.id == job_id).first()

    def get_job_by_uid(self, db: Session, job_uid: str) -> Optional[CourseGenerationJob]:
        """按对外 job_uid 取 job。"""
        return db.query(CourseGenerationJob).filter(CourseGenerationJob.job_uid == job_uid).first()

    def list_jobs_by_user(self, db: Session, user_id: str, limit: int = 50) -> List[CourseGenerationJob]:
        """列出某教师最近的任务，按创建时间倒序。"""
        return (
            db.query(CourseGenerationJob)
            .filter(CourseGenerationJob.user_id == user_id)
            .order_by(CourseGenerationJob.create_time.desc())
            .limit(limit)
            .all()
        )

    def update_status(self, db: Session, job_id: int, from_status: state.Status,
                      to_status: state.Status, error_message: Optional[str] = None) -> None:
        """带 from-status 乐观并发的状态更新：状态已经不是 from 时抛 StaleStatusError。"""
        updated = (
            db.query(CourseGenerationJob)
            .filter(CourseGenerationJob.id == job_id, CourseGenerationJob.status == from_status.value)
            .update({"status": to_status.value, "error_message": error_message,
                     "update_time": datetime.now()})
        )
        db.commit()
        if updated == 0:
            raise StaleStatusError(
                f"coursegen: job {job_id} status changed concurrently (expected {from_status.value})")

    def update_plan(self, db: Session, job_id: int, plan: List[Dict[str, Any]]) -> None:
        """写入 agent 的最新计划快照。"""
        db.query(CourseGenerationJob).filter(CourseGenerationJob.id == job_id).update(
            {"plan": plan, "update_time": datetime.now()})
        db.commit()

    def update_budget(self, db: Session, job_id: int, from_status: state.Status, new_budget: int) -> None:
        """调预算（含改为 0 = 无上限）。带 from-status 乐观并发。"""
        updated = (
            db.query(CourseGenerationJob)
            .filter(CourseGenerationJob.id == job_id, CourseGenerationJob.status == from_status.value)
            .update({"token_budget": new_budget, "update_time": datetime.now()})
        )
        db.commit()
        if updated == 0:
            raise StaleStatusError(
                f"coursegen: job {job_id} budget adjusted concurrently (expected {from_status.value})")

    def add_tokens(self, db: Session, job_id: int, delta: int) -> int:
        """累加 token 并返回累加后的值。累加而非覆盖：并发 episode 的更新不能丢。"""
        job = db.query(CourseGenerationJob).filter(CourseGenerationJob.id == job_id).first()
        if job is None:
            raise JobNotFoundError(f"coursegen: job {job_id} not found")
        job.tokens_spent = (job.tokens_spent or 0) + delta
        job.update_time = datetime.now()
        db.commit()
        db.refresh(job)
        return job.tokens_spent

    def mark_published(self, db: Session, job_id: int, course_id: int) -> None:
        """记录发布结果。"""
        updated = (
            db.query(CourseGenerationJob)
            .filter(CourseGenerationJob.id == job_id)
            .update({"published_course_id": course_id, "update_time": datetime.now()})
        )
        db.commit()
        if updated == 0:
            raise JobNotFoundError(f"coursegen: job {job_id} not found")

    def patch_request_payload(self, db: Session, job_id: int, patch: Dict[str, Any]) -> CourseGenerationJob:
        """把前端暂存的草稿字段合并进 request_payload（不改状态）。"""
        job = self.get_job(db, job_id)
        if job is None:
            raise JobNotFoundError(f"coursegen: job {job_id} not found")
        payload = dict(job.request_payload or {})
        payload.update(patch)
        job.request_payload = payload
        job.update_time = datetime.now()
        db.commit()
        db.refresh(job)
        return job

    # ------------------------------ reviews ------------------------------

    def create_review(self, db: Session, *, job_id: int, scope: str, summary: str,
                      artifact_paths: List[str]) -> int:
        """创建一条待裁决评审，返回评审 id。"""
        db_obj = CourseGenerationReview(
            job_id=job_id, scope=scope, summary=summary,
            artifact_paths=artifact_paths or [], status=state.ReviewStatus.PENDING.value,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj.id

    def get_review(self, db: Session, review_id: int) -> Optional[CourseGenerationReview]:
        """按 id 取评审。"""
        return db.query(CourseGenerationReview).filter(CourseGenerationReview.id == review_id).first()

    def list_reviews(self, db: Session, job_id: int) -> List[CourseGenerationReview]:
        """列出某个 job 的全部评审，按创建时间升序。"""
        return (
            db.query(CourseGenerationReview)
            .filter(CourseGenerationReview.job_id == job_id)
            .order_by(CourseGenerationReview.create_time.asc())
            .all()
        )

    def latest_pending_review(self, db: Session, job_id: int) -> Optional[CourseGenerationReview]:
        """取最近一条待裁决评审（供教师 confirm 使用）。"""
        return (
            db.query(CourseGenerationReview)
            .filter(CourseGenerationReview.job_id == job_id,
                    CourseGenerationReview.status == state.ReviewStatus.PENDING.value)
            .order_by(CourseGenerationReview.create_time.desc())
            .first()
        )

    def decide_review(self, db: Session, review_id: int, status_: state.ReviewStatus,
                      feedback: Optional[str] = None) -> None:
        """记下裁决。一条评审不能被改主意（否则终审不变量基准会被挪动）。"""
        updated = (
            db.query(CourseGenerationReview)
            .filter(CourseGenerationReview.id == review_id,
                    CourseGenerationReview.status == state.ReviewStatus.PENDING.value)
            .update({"status": status_.value, "feedback": feedback, "decide_time": datetime.now()})
        )
        db.commit()
        if updated == 0:
            raise StaleStatusError(f"coursegen: review {review_id} already decided")

    def count_approved_reviews(self, db: Session, job_id: int, scope: Optional[str] = None) -> int:
        """统计某 job（可按 scope 过滤）已批准的评审数。"""
        query = db.query(CourseGenerationReview).filter(
            CourseGenerationReview.job_id == job_id,
            CourseGenerationReview.status == state.ReviewStatus.APPROVED.value)
        if scope is not None:
            query = query.filter(CourseGenerationReview.scope == scope)
        return query.count()

    def latest_approved_review_time(self, db: Session, job_id: int, scope: str) -> Optional[datetime]:
        """某 scope 最近一次批准的时间；一次都没批过返回 None。"""
        row = (
            db.query(CourseGenerationReview)
            .filter(CourseGenerationReview.job_id == job_id,
                    CourseGenerationReview.scope == scope,
                    CourseGenerationReview.status == state.ReviewStatus.APPROVED.value)
            .order_by(CourseGenerationReview.decide_time.desc())
            .first()
        )
        return row.decide_time if row is not None else None

    # ------------------------------ workspace files ------------------------------

    def write_workspace_file(self, db: Session, job_id: int, path: str, content: str) -> int:
        """整份写入（upsert），返回最新版本号。"""
        existing = (
            db.query(CourseGenerationWorkspaceFile)
            .filter(CourseGenerationWorkspaceFile.job_id == job_id,
                    CourseGenerationWorkspaceFile.path == path)
            .first()
        )
        if existing is None:
            db_obj = CourseGenerationWorkspaceFile(job_id=job_id, path=path, content=content, version=1)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj.version
        existing.content = content
        existing.version = (existing.version or 1) + 1
        existing.update_time = datetime.now()
        db.commit()
        return existing.version

    def get_workspace_file(self, db: Session, job_id: int, path: str) -> Optional[CourseGenerationWorkspaceFile]:
        """按路径取一份草稿。"""
        return (
            db.query(CourseGenerationWorkspaceFile)
            .filter(CourseGenerationWorkspaceFile.job_id == job_id,
                    CourseGenerationWorkspaceFile.path == path)
            .first()
        )

    def list_workspace_files(self, db: Session, job_id: int) -> List[CourseGenerationWorkspaceFile]:
        """列出某 job 工作区里的全部草稿。"""
        return (
            db.query(CourseGenerationWorkspaceFile)
            .filter(CourseGenerationWorkspaceFile.job_id == job_id)
            .order_by(CourseGenerationWorkspaceFile.path.asc())
            .all()
        )

    def latest_workspace_write_time(self, db: Session, job_id: int) -> Optional[datetime]:
        """工作区最后一次写入时间；工作区为空返回 None。"""
        row = (
            db.query(CourseGenerationWorkspaceFile)
            .filter(CourseGenerationWorkspaceFile.job_id == job_id)
            .order_by(CourseGenerationWorkspaceFile.update_time.desc())
            .first()
        )
        return row.update_time if row is not None else None

    # ------------------------------ events ------------------------------

    def append_event(self, db: Session, *, job_id: int, stage: str, event_type: str,
                     payload: Dict[str, Any], message: Optional[str] = None) -> int:
        """追加一条事件，返回事件 id。"""
        db_obj = CourseGenerationEvent(
            job_id=job_id, stage=stage, event_type=event_type,
            payload=payload or {}, message=message,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj.id

    def list_events_after(self, db: Session, job_id: int, after_id: int, limit: int = 100) -> List[CourseGenerationEvent]:
        """取某 job 在 after_id 之后的事件（SSE 推流与回放的数据源）。"""
        return (
            db.query(CourseGenerationEvent)
            .filter(CourseGenerationEvent.job_id == job_id, CourseGenerationEvent.id > after_id)
            .order_by(CourseGenerationEvent.id.asc())
            .limit(limit)
            .all()
        )

    def latest_event(self, db: Session, job_id: int) -> Optional[CourseGenerationEvent]:
        """取某 job 最近一条事件。"""
        return (
            db.query(CourseGenerationEvent)
            .filter(CourseGenerationEvent.job_id == job_id)
            .order_by(CourseGenerationEvent.id.desc())
            .first()
        )


# 模块级单例，与现有 crud_*.py 的写法一致
course_generation = CRUDCourseGeneration(CourseGenerationJob)
