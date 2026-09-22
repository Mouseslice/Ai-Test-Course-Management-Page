"""生成驱动：唯一决定「这个 job 什么时候停下来」的地方。

本地生成模式下流程大幅简化——不再有多智能体回合循环：

  running:
    - 调 LocalGenerator 一次性组装 course.json（模板内容库，秒级完成）
    - 成功后发布（BeginPublish → 契约校验 → CompletePublish）
    - 生成/发布异常 → harness.fail（教师可 failed → running 重试）
  awaiting_review: break（教师裁决接口会重新入队驱动）
  publishing/published/failed/cancelled: break

进程内租约防重入：Celery 并发或重试时同一个 job 不会同时被两条驱动推进。
（SQLite 单写者 + 乐观状态写提供了最终防线；跨进程租约后续可用 Redis 实现。）
"""
import logging
import threading
from typing import Dict, Optional

from app.core.config import settings
from app.models.course_generation import CourseGenerationJob
from app.services.course_generation.errors import (
    AlreadyRunningError,
    PublishContractError,
)
from app.services.course_generation.harness import Harness
from app.services.course_generation.llm_generator import LlmGenerator
from app.services.course_generation.local_generator import LocalGenerator
from app.services.course_generation.publish import Publisher
from app.services.course_generation.repository import SQLRepository

logger = logging.getLogger(__name__)

# 进程内租约：job_id -> 运行中的驱动线程。Celery 的 at-least-once 语义下，
# 同一 job 的重复入队靠它幂等掉（重复入队直接 AlreadyRunningError 跳过）。
_leases: Dict[int, threading.Thread] = {}
_leases_lock = threading.Lock()


class Driver:
    """驱动一个 job 到终态或暂停点。"""

    def __init__(self, repo: SQLRepository) -> None:
        self.repo = repo
        self.harness = Harness(repo)
        self.generator = LocalGenerator(self.harness)
        self.publisher = Publisher(self.harness)

    # ------------------------------ 对外入口 ------------------------------

    def drive(self, job_uid: str) -> None:
        """驱动一个 job；已经有人在驱动时幂等跳过。"""
        job = self.repo.get_job_by_uid(job_uid)
        if not self._acquire(job.id):
            logger.info("coursegen: job %s already being driven, skip", job_uid)
            raise AlreadyRunningError(f"coursegen: job {job_uid} already running")
        try:
            self._drive_once(job)
        finally:
            self._release(job.id)

    def drive_by_id(self, job_id: int) -> None:
        """按内部 id 驱动（教师裁决接口用）。"""
        job = self.repo.get_job(job_id)
        self.drive(job.job_uid)

    # ------------------------------ 内部 ------------------------------

    def _drive_once(self, job: CourseGenerationJob) -> None:
        """单次驱动：生成（本地或 LLM 引导）→ 发布；任一环节失败转 failed 收尾。"""
        job = self.repo.get_job(job.id)

        if job.status == "awaiting_review":
            return  # 教师裁决接口会重新入队驱动
        if job.status != "running":
            return  # 已被取消/失败/发布中/发布完成

        try:
            self._generate(job)
        except Exception as exc:
            logger.exception("coursegen: generation failed for job %s", job.job_uid)
            self.harness.fail(job, f"生成失败：{exc}")
            return

        self._publish(job)

    def _generate(self, job: CourseGenerationJob) -> None:
        """按 config.generation_mode 选生成器；LLM 引导整体失败时回退本地模板。"""
        payload = job.request_payload if isinstance(job.request_payload, dict) else {}
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        mode = str(config.get("generation_mode") or config.get("generationMode") or "local")

        generator = self.generator  # LocalGenerator（默认）
        if mode == "llm":
            generator = LlmGenerator(self.harness)
        # LLM 引导整体失败时不再回退本地模板：回退产物是旧式无场景课程，
        # 与新场景课件的预览/播放要求不符，直接失败并由上层标记任务失败、给出重试提示。
        generator.generate(job)

    def _publish(self, job: CourseGenerationJob) -> bool:
        """本地生成完成后的发布路径。返回 True 表示已发布。

        本地生成的 course.json 由模板内容库保证满足契约，PublishContractError
        理论上不应出现；出现时仍按原语义回滚到 running 并终止，避免死循环。
        """
        try:
            self.publisher.publish(job)
            return True
        except PublishContractError as exc:
            logger.warning("coursegen: publish contract pending for job %s: %s", job.job_uid, exc)
            return False
        except Exception as exc:
            logger.exception("coursegen: publish failed for job %s", job.job_uid)
            self.harness.fail(job, f"发布失败：{exc}")
            return False

    def _acquire(self, job_id: int) -> bool:
        """进程内租约；持有者先存在说明已有驱动在跑。"""
        with _leases_lock:
            holder = _leases.get(job_id)
            if holder is not None and holder.is_alive():
                return False
            thread = threading.current_thread()
            _leases[job_id] = thread
            return True

    def _release(self, job_id: int) -> None:
        with _leases_lock:
            _leases.pop(job_id, None)
