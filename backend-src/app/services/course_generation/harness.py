"""课程生成的确定性 harness：状态机、工作区、预算、评审门。

对应 Go 侧 coursegen/harness.go。harness 不含生成逻辑——它只回答四个问题：
  - 状态该不该变（validate_transition + 乐观并发写）；
  - 事件该不该记（append_event，SSE 的数据源）；
  - 预算还剩多少（check_budget：总额门 + 设计评审检查点）；
  - 评审门该不该拦（发布终审不变量在 publisher 里，这里负责裁决流转）。

所有方法拿 repo 持久化；本地生成在 local_generator.py 里组装产物，driver.py 只决定何时停。
"""
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.course_generation import CourseGenerationJob
from app.services.course_generation import state
from app.services.course_generation.errors import (
    BudgetExhaustedError,
    DesignReviewRequiredError,
    FinalReviewStaleError,
    JobNotFoundError,
    StaleStatusError,
    WorkspaceFileNotFoundError,
)
from app.services.course_generation.repository import SQLRepository


class EpisodeResult:
    """一轮 episode 的产物，供 driver 决定下一步。"""

    def __init__(self, *, outcome: str, tokens_used: int = 0,
                 requested_review_id: Optional[int] = None, done: bool = False,
                 message: str = "") -> None:
        self.outcome = outcome          # DONE / REVIEW / COMPLETED / ERROR
        self.tokens_used = tokens_used
        self.requested_review_id = requested_review_id
        self.done = done
        self.message = message


class RunOutcome:
    """episode 结局：DONE=该发布了；REVIEW=在等教师；COMPLETED=这轮做完了还要继续。"""
    DONE = "DONE"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class Harness:
    """状态机 + 预算 + 评审门 + 事件流的所有者。"""

    def __init__(self, repo: SQLRepository, *, turn_gap: Optional[float] = None) -> None:
        self.repo = repo
        # 两个预算门都挂在 harness：总额门 + 设计评审检查点
        self.max_turns = settings.COURSEGEN_MAX_TURNS
        self.design_review_fraction = settings.COURSEGEN_DESIGN_REVIEW_FRACTION
        self.turn_gap = turn_gap if turn_gap is not None else settings.COURSEGEN_TURN_GAP

    # ------------------------------ 状态与事件 ------------------------------

    def change_status(self, job: CourseGenerationJob, to_status: state.Status,
                      message: Optional[str] = None) -> CourseGenerationJob:
        """带乐观并发的状态转移，并追加 status_changed 事件。

        骨架约定：并发写冲突（StaleStatusError）向上抛，由调用方决定重读还是放弃——
        绝不静默吞掉，因为两个执行者同时推进同一个 job 本身就是需要诊断的信号。
        """
        from_status = state.parse_status(job.status)
        state.validate_transition(from_status, to_status)
        error_message = message if to_status == state.Status.FAILED else None
        self.repo.update_status(job.id, from_status, to_status, error_message)
        job.status = to_status.value
        self.emit(job, state.STAGE_HARNESS, state.EVENT_STATUS_CHANGED,
                  {"from": from_status.value, "to": to_status.value}, message)
        return job

    def emit(self, job: CourseGenerationJob, stage: str, event_type: str,
             payload: Dict[str, Any], message: Optional[str] = None) -> None:
        """追加一条事件（SSE 推流与留痕的唯一入口）。"""
        self.repo.append_event(job_id=job.id, stage=stage, event_type=event_type,
                               payload=payload, message=message)

    # ------------------------------ 生命周期 ------------------------------

    def create_job(self, *, job_uid: str, user_id: str, request_payload: Dict[str, Any],
                   token_budget: int) -> CourseGenerationJob:
        """创建 job 记录并广播 job_created。"""
        job = self.repo.create_job(job_uid=job_uid, user_id=user_id,
                                   request_payload=request_payload, token_budget=token_budget)
        self.emit(job, state.STAGE_HARNESS, state.EVENT_JOB_CREATED,
                  {"job_uid": job_uid}, "课程生成任务已创建")
        return job

    def start(self, job: CourseGenerationJob) -> None:
        """created → running。"""
        self.change_status(job, state.Status.RUNNING, "生成任务启动")

    def cancel(self, job: CourseGenerationJob) -> None:
        """取消：允许从非终态进入。状态机里 cancelled → running 是恢复通道。"""
        self.change_status(job, state.Status.CANCELLED, "生成任务已取消")

    def fail(self, job: CourseGenerationJob, error_message: str) -> None:
        """failed：把失败原因落库（教师可 AdjustBudget 后走 failed → running 重试）。"""
        try:
            self.change_status(job, state.Status.FAILED, error_message)
        except StaleStatusError:
            # 并发下别人已经把这个 job 带走了（比如刚被取消），不再覆盖它的结局
            pass

    def add_comment(self, job: CourseGenerationJob, scope: str, content: str) -> None:
        """教师留言：记事件，不改状态（评审内容在下一轮观察里喂回 agent）。"""
        self.emit(job, state.STAGE_HARNESS, state.EVENT_TEACHER_COMMENT,
                  {"scope": scope, "content": content}, content)

    def adjust_budget(self, job: CourseGenerationJob, new_budget: int) -> None:
        """调预算（含改为 0 = 无上限），广播 budget_adjusted。"""
        from_status = state.parse_status(job.status)
        self.repo.update_budget(job.id, from_status, new_budget)
        job.token_budget = new_budget
        self.emit(job, state.STAGE_HARNESS, state.EVENT_BUDGET_ADJUSTED,
                  {"new_budget": new_budget}, f"预算调整为 {new_budget}")

    def decide_review(self, job: CourseGenerationJob, review_id: int, approved: bool,
                      feedback: Optional[str] = None) -> None:
        """裁决一条待评审；pending → approved/rejected，然后 awaiting_review → running。

        驳回不是失败：feedback 会进入下一轮观察，agent 修完再来一次评审。
        """
        review = self.repo.get_review(review_id)
        verdict = state.ReviewStatus.APPROVED if approved else state.ReviewStatus.REJECTED
        self.repo.decide_review(review_id, verdict, feedback)
        self.emit(job, state.STAGE_HARNESS, state.EVENT_REVIEW_DECIDED,
                  {"review_id": review_id, "scope": review.scope,
                   "verdict": verdict.value, "feedback": feedback},
                  f"评审#{review_id} 已{'批准' if approved else '驳回'}")
        if state.parse_status(job.status) == state.Status.AWAITING_REVIEW:
            self.change_status(job, state.Status.RUNNING, "教师已裁决，继续生成")

    # ------------------------------ 工作区与计划 ------------------------------

    def update_plan(self, job: CourseGenerationJob, plan: List[Dict[str, Any]]) -> None:
        """替换计划快照并广播 plan_updated。"""
        self.repo.update_plan(job.id, plan)
        job.plan = plan
        self.emit(job, state.STAGE_HARNESS, state.EVENT_PLAN_UPDATED,
                  {"plan": plan}, "计划已更新")

    def write_workspace_file(self, job: CourseGenerationJob, path: str, content: str) -> int:
        """整份写入草稿，返回版本号。"""
        version = self.repo.write_workspace_file(job.id, path, content)
        self.emit(job, state.STAGE_EPISODE, state.EVENT_TOOL_CALL,
                  {"tool": "write_draft", "path": path, "version": version},
                  f"写入草稿 {path} (v{version})")
        return version

    def read_workspace_file(self, job: CourseGenerationJob, path: str) -> str:
        """读取草稿内容；不存在抛 WorkspaceFileNotFoundError（工具层会转成观察）。"""
        item = self.repo.get_workspace_file(job.id, path)
        if item is None:
            raise WorkspaceFileNotFoundError(f"coursegen: workspace file {path} not found")
        return item.content

    # ------------------------------ 预算与评审门 ------------------------------

    def check_budget(self, job: CourseGenerationJob) -> None:
        """两道预算门，episode 之间调用：

        1. 总额门：tokens_spent > token_budget → BudgetExhaustedError（job 由 driver 转 failed）；
        2. 设计评审检查点：越过 15% 后还没有任何 approved 的 design 评审 → DesignReviewRequiredError
           （harness 拒绝继续派活，等 agent 发起评审、教师批准）。
        """
        budget = job.token_budget or 0
        if budget > 0 and (job.tokens_spent or 0) > budget:
            self.emit(job, state.STAGE_HARNESS, state.EVENT_BUDGET_WARNING,
                      {"spent": job.tokens_spent, "budget": budget}, "token 预算已用尽")
            raise BudgetExhaustedError(
                f"coursegen: token budget exhausted ({job.tokens_spent}/{budget})")

        checkpoint = int(budget * self.design_review_fraction)
        approved = self.repo.count_approved_reviews(job.id, scope=state.SCOPE_DESIGN)
        if checkpoint > 0 and (job.tokens_spent or 0) > checkpoint and approved == 0:
            self.emit(job, state.STAGE_HARNESS, state.EVENT_BUDGET_WARNING,
                      {"checkpoint": checkpoint}, "已越过设计评审检查点，等待方向确认")
            raise DesignReviewRequiredError(
                f"coursegen: design review required after {checkpoint} tokens")
