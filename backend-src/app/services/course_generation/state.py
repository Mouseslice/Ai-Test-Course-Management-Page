"""课程生成 job 的确定性状态机。

对应 Go 侧 coursegen/job.go：七个状态、一张 allowedTransitions 表、一处 transition 校验。
状态机是 harness 唯一的真相来源——所有状态变更都经过 transition() 校验，同状态自转移一律拒绝。
"""
from enum import Enum
from typing import Dict, List, Optional


class Status(str, Enum):
    """job 状态，取值与库上列一一对应。"""
    CREATED = "created"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReviewStatus(str, Enum):
    """一次评审的裁决状态。rejected 不是终点：feedback 会作为观察喂回 agent。"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


def is_terminal(status: Status) -> bool:
    """终态判断：published 之后再无状态转移（SSE 推流靠它决定何时收尾）。

    cancelled 不是终态——取消是「停下来」不是「结束」，教师想继续时走 Start 恢复。
    """
    return status == Status.PUBLISHED


# 状态机的唯一真相来源。running ⇄ awaiting_review：agent 请求评审进去，教师裁决后回来；
# approve 与 reject 都回 running——驳回不是失败，是信息。
ALLOWED_TRANSITIONS: Dict[Status, List[Status]] = {
    Status.CREATED: [Status.RUNNING, Status.CANCELLED],
    Status.RUNNING: [Status.AWAITING_REVIEW, Status.PUBLISHING, Status.FAILED, Status.CANCELLED],
    Status.AWAITING_REVIEW: [Status.RUNNING, Status.FAILED, Status.CANCELLED],
    Status.PUBLISHING: [Status.RUNNING, Status.PUBLISHED, Status.FAILED, Status.CANCELLED],
    # publishing → running 是发布失败回滚（契约不符时回生成态让 agent 修改，见 publish.py）
    # failed → running 是重试；cancelled → running 是恢复，工作区持久，不需要重放。
    Status.FAILED: [Status.RUNNING, Status.CANCELLED],
    Status.CANCELLED: [Status.RUNNING],
    Status.PUBLISHED: [],
}


class InvalidTransitionError(ValueError):
    """非法状态转移，例如 running → running。"""

    def __init__(self, from_status: Status, to_status: Status) -> None:
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"coursegen: illegal transition {from_status.value} → {to_status.value}")


def validate_transition(from_status: Status, to_status: Status) -> None:
    """校验一次状态转移，非法时抛出 InvalidTransitionError。"""
    if to_status not in ALLOWED_TRANSITIONS.get(from_status, []):
        raise InvalidTransitionError(from_status, to_status)


# 两个 harness 认识的评审 scope；其余取值是 agent 自定的标签。
SCOPE_DESIGN = "design"
SCOPE_FINAL = "final"

# harness 自己发的事件类型（agent 的工具调用另有 tool_call，共用同一张表）。
EVENT_JOB_CREATED = "job_created"
EVENT_STATUS_CHANGED = "status_changed"
EVENT_PLAN_UPDATED = "plan_updated"
EVENT_EPISODE_STARTED = "episode_started"
EVENT_EPISODE_FINISHED = "episode_finished"
EVENT_REVIEW_REQUESTED = "review_requested"
EVENT_REVIEW_DECIDED = "review_decided"
EVENT_TEACHER_COMMENT = "teacher_comment"
EVENT_BUDGET_WARNING = "budget_warning"
EVENT_BUDGET_ADJUSTED = "budget_adjusted"
EVENT_PUBLISH_WARNING = "publish_warning"
EVENT_TOOL_CALL = "tool_call"

# harness 发的事件用的 stage 标签；其余 stage 是 agent 计划里的自由 phase 文本。
STAGE_HARNESS = "harness"
STAGE_EPISODE = "episode"


def parse_status(raw: Optional[str]) -> Status:
    """把库里的字符串解析回 Status 枚举。"""
    return Status(raw) if raw is not None else Status.CREATED
