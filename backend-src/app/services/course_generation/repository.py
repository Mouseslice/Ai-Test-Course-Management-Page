"""harness/driver 使用的仓储门面：每次操作自开会话。

与 Go 的 SQLRepository 语义一致——harness 在 Celery 后台任务里运行，不依赖
HTTP 请求上下文，所以仓储自己管理会话生命周期。测试时可注入 db_factory 换内存库。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.crud.crud_course_generation import course_generation
from app.db.database import SessionLocal
from app.models.course_generation import (
    CourseGenerationEvent,
    CourseGenerationJob,
    CourseGenerationReview,
    CourseGenerationWorkspaceFile,
)
from app.services.course_generation import state
from app.services.course_generation.errors import (
    JobNotFoundError,
    ReviewNotFoundError,
)


class SQLRepository:
    """仓储门面：每次操作自开会话。"""

    def __init__(self, db_factory=SessionLocal) -> None:
        self._db_factory = db_factory
        self._crud = course_generation

    # ----- jobs -----
    def create_job(self, *, job_uid: str, user_id: str, request_payload: Dict[str, Any],
                   token_budget: int) -> CourseGenerationJob:
        with self._db_factory() as db:
            return self._crud.create_job(db, job_uid=job_uid, user_id=user_id,
                                         request_payload=request_payload, token_budget=token_budget)

    def get_job(self, job_id: int) -> CourseGenerationJob:
        with self._db_factory() as db:
            job = self._crud.get_job(db, job_id)
            if job is None:
                raise JobNotFoundError(f"coursegen: job {job_id} not found")
            return job

    def get_job_by_uid(self, job_uid: str) -> CourseGenerationJob:
        with self._db_factory() as db:
            job = self._crud.get_job_by_uid(db, job_uid)
            if job is None:
                raise JobNotFoundError(f"coursegen: job {job_uid} not found")
            return job

    def list_jobs_by_user(self, user_id: str, limit: int = 50) -> List[CourseGenerationJob]:
        with self._db_factory() as db:
            return self._crud.list_jobs_by_user(db, user_id, limit)

    def update_status(self, job_id: int, from_status: state.Status, to_status: state.Status,
                      error_message: Optional[str] = None) -> None:
        with self._db_factory() as db:
            self._crud.update_status(db, job_id, from_status, to_status, error_message)

    def update_plan(self, job_id: int, plan: List[Dict[str, Any]]) -> None:
        with self._db_factory() as db:
            self._crud.update_plan(db, job_id, plan)

    def update_budget(self, job_id: int, from_status: state.Status, new_budget: int) -> None:
        with self._db_factory() as db:
            self._crud.update_budget(db, job_id, from_status, new_budget)

    def add_tokens(self, job_id: int, delta: int) -> int:
        with self._db_factory() as db:
            return self._crud.add_tokens(db, job_id, delta)

    def mark_published(self, job_id: int, course_id: int) -> None:
        with self._db_factory() as db:
            self._crud.mark_published(db, job_id, course_id)

    def patch_request_payload(self, job_id: int, patch: Dict[str, Any]) -> CourseGenerationJob:
        with self._db_factory() as db:
            return self._crud.patch_request_payload(db, job_id, patch)

    # ----- reviews -----
    def create_review(self, *, job_id: int, scope: str, summary: str, artifact_paths: List[str]) -> int:
        with self._db_factory() as db:
            return self._crud.create_review(db, job_id=job_id, scope=scope,
                                            summary=summary, artifact_paths=artifact_paths)

    def get_review(self, review_id: int) -> CourseGenerationReview:
        with self._db_factory() as db:
            review = self._crud.get_review(db, review_id)
            if review is None:
                raise ReviewNotFoundError(f"coursegen: review {review_id} not found")
            return review

    def list_reviews(self, job_id: int) -> List[CourseGenerationReview]:
        with self._db_factory() as db:
            return self._crud.list_reviews(db, job_id)

    def latest_pending_review(self, job_id: int) -> Optional[CourseGenerationReview]:
        with self._db_factory() as db:
            return self._crud.latest_pending_review(db, job_id)

    def decide_review(self, review_id: int, status_: state.ReviewStatus,
                      feedback: Optional[str] = None) -> None:
        with self._db_factory() as db:
            self._crud.decide_review(db, review_id, status_, feedback)

    def count_approved_reviews(self, job_id: int, scope: Optional[str] = None) -> int:
        with self._db_factory() as db:
            return self._crud.count_approved_reviews(db, job_id, scope)

    def latest_approved_review_time(self, job_id: int, scope: str) -> Optional[datetime]:
        with self._db_factory() as db:
            return self._crud.latest_approved_review_time(db, job_id, scope)

    # ----- workspace -----
    def write_workspace_file(self, job_id: int, path: str, content: str) -> int:
        with self._db_factory() as db:
            return self._crud.write_workspace_file(db, job_id, path, content)

    def get_workspace_file(self, job_id: int, path: str) -> Optional[CourseGenerationWorkspaceFile]:
        with self._db_factory() as db:
            return self._crud.get_workspace_file(db, job_id, path)

    def list_workspace_files(self, job_id: int) -> List[CourseGenerationWorkspaceFile]:
        with self._db_factory() as db:
            return self._crud.list_workspace_files(db, job_id)

    def latest_workspace_write_time(self, job_id: int) -> Optional[datetime]:
        with self._db_factory() as db:
            return self._crud.latest_workspace_write_time(db, job_id)

    # ----- events -----
    def append_event(self, *, job_id: int, stage: str, event_type: str,
                     payload: Dict[str, Any], message: Optional[str] = None) -> int:
        with self._db_factory() as db:
            return self._crud.append_event(db, job_id=job_id, stage=stage,
                                           event_type=event_type, payload=payload, message=message)

    def list_events_after(self, job_id: int, after_id: int, limit: int = 100) -> List[CourseGenerationEvent]:
        with self._db_factory() as db:
            return self._crud.list_events_after(db, job_id, after_id, limit)

    def latest_event(self, job_id: int) -> Optional[CourseGenerationEvent]:
        with self._db_factory() as db:
            return self._crud.latest_event(db, job_id)
