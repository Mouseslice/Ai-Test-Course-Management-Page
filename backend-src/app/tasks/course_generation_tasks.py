"""课程生成的 Celery 主循环。

driver.Drive 是整个生成的唯一推进入口；教师裁决（confirm）后重新入队本任务。
任务幂等：Driver 内部有进程内租约，重复入队直接跳过。
"""
import logging

from app.celery_app import celery_app
from app.services.course_generation.driver import Driver
from app.services.course_generation.repository import SQLRepository

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.course_generation_tasks.drive_generation_job",
                 bind=True, max_retries=0, acks_late=False)
def drive_generation_job(self, job_uid: str) -> dict:
    """驱动一个课程生成任务到暂停点或终态（同步运行，回合间带间隔）。"""
    repo = SQLRepository()
    driver = Driver(repo)
    try:
        driver.drive(job_uid)
    except Exception as exc:
        # 任务级兜底：job 级失败由 Driver 内部转 failed 状态，这里只记日志不重试
        logger.exception("coursegen: drive job %s crashed: %s", job_uid, exc)
        return {"job_uid": job_uid, "status": "error", "detail": str(exc)}
    return {"job_uid": job_uid, "status": "ok"}
