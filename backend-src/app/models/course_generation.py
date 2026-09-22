"""课程生成引擎的持久化模型。

对应 Go 侧 coursegen/job.go 的四个结构：Job / Review / WorkspaceFile / Event。
设计要点（来自 ADR-0014）：
  - 一切状态都在库里：恢复、取消、进度全部由数据库状态驱动，不依赖进程内存；
  - job 状态机取值见 app/services/course_generation/state.py 的 Status 枚举；
  - 内部 id 是自增整数，对外暴露的 job_uid 是 UUID 字符串（教师端 URL 用后者）。
"""
from datetime import datetime
import pytz
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from app.db.base_class import Base


def _now() -> datetime:
    """当前时间（上海时区），用于各表的时间列默认值。"""
    return datetime.now(pytz.timezone('Asia/Shanghai'))


class CourseGenerationJob(Base):
    """课程生成任务。

    Attributes:
        id: 内部自增主键（事件/评审/工作区文件都引用它）
        job_uid: 对外暴露的任务标识（UUID 字符串），教师端 URL 使用
        user_id: 发起生成的教师标识
        status: 状态机取值（created/running/awaiting_review/publishing/published/failed/cancelled）
        plan: agent 的最新计划快照（todo-list 形态的 JSON）
        request_payload: 创建时教师提交的意图描述 + 约束 + 资料选择（自由的 JSON）
        token_budget: token 预算，0 表示无上限
        tokens_spent: 已消耗 token 数
        published_course_id: 发布成功后的课程 ID（未发布时为 None）
        error_message: 失败原因（status=failed 时非空）
    """
    __tablename__ = "course_generation_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_uid = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(String(255), index=True, nullable=False)
    status = Column(String(32), index=True, nullable=False, default="created")
    plan = Column(JSON, default=list)
    request_payload = Column(JSON, default=dict)
    token_budget = Column(Integer, nullable=False, default=0)
    tokens_spent = Column(Integer, nullable=False, default=0)
    published_course_id = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    create_time = Column(DateTime, default=_now, nullable=False)
    update_time = Column(DateTime, default=_now, onupdate=_now, nullable=False)


class CourseGenerationReview(Base):
    """一次教师评审。

    Attributes:
        scope: design=方向确认，final=发布终审；也可以是 agent 自定的标签
        summary: 请教师看什么、希望裁决什么
        artifact_paths: 请教师看的草稿路径列表
        status: pending/approved/rejected（rejected 的 feedback 会喂回 agent）
        feedback: 教师驳回/批准时的意见
        decide_time: 裁决时间
    """
    __tablename__ = "course_generation_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, index=True, nullable=False)
    scope = Column(String(32), nullable=False)
    summary = Column(Text, nullable=False)
    artifact_paths = Column(JSON, default=list)
    status = Column(String(16), index=True, nullable=False, default="pending")
    feedback = Column(Text, nullable=True)
    create_time = Column(DateTime, default=_now, nullable=False)
    decide_time = Column(DateTime, nullable=True)


class CourseGenerationWorkspaceFile(Base):
    """工作区里的一份草稿产物。

    Attributes:
        path: 草稿路径（模型给的字符串，唯一键；发布契约要求 course.json 在这个目录下）
        content: 正文全文
        version: 版本号，每次整份写入递增
    """
    __tablename__ = "course_generation_workspace_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, index=True, nullable=False)
    path = Column(String(512), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    update_time = Column(DateTime, default=_now, onupdate=_now, nullable=False)


class CourseGenerationEvent(Base):
    """job 事件流里的一条，SSE 推流与留痕的数据源。

    Attributes:
        stage: harness 或 episode，也可以是 agent 计划里的自由 phase 标签
        event_type: 事件类型（见 state.py 的 EVENT_* 常量；agent 工具调用恒为 tool_call）
        payload: 结构化载荷（JSON）
        message: 给人看的中文说明
    """
    __tablename__ = "course_generation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, index=True, nullable=False)
    stage = Column(String(64), nullable=False)
    event_type = Column(String(64), nullable=False)
    payload = Column(JSON, default=dict)
    message = Column(Text, nullable=True)
    create_time = Column(DateTime, default=_now, nullable=False)
