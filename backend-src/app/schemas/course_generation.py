"""课程生成引擎的 Pydantic 模型。

两层用途：
  - 内部：job/review/event/file 的读写 DTO（配合 crud 使用）；
  - 对外：教师端 teacher-portal 接口的请求/响应 DTO（与前端 course-generation-api.ts
    及 useContentGeneration.ts 的字段逐一对应）。
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------- 内部 DTO ----------------------------

class CourseGenerationJobCreate(BaseModel):
    """创建课程生成任务的输入。"""
    job_uid: str
    user_id: str
    request_payload: Dict[str, Any] = Field(default_factory=dict)
    token_budget: int = 0  # 0 表示无上限


class CourseGenerationJobOut(BaseModel):
    """job 的对外形状。"""
    id: int
    job_uid: str
    user_id: str
    status: str
    plan: Optional[List[Dict[str, Any]]] = None
    request_payload: Dict[str, Any] = Field(default_factory=dict)
    token_budget: int = 0
    tokens_spent: int = 0
    published_course_id: Optional[int] = None
    error_message: Optional[str] = None
    create_time: Any = None
    update_time: Any = None


class CourseGenerationReviewOut(BaseModel):
    """一次评审的对外形状。"""
    id: int
    job_id: int
    scope: str
    summary: str
    artifact_paths: List[str] = Field(default_factory=list)
    status: str
    feedback: Optional[str] = None
    create_time: Any = None
    decide_time: Optional[Any] = None


class CourseGenerationEventOut(BaseModel):
    """一条事件流记录的对外形状。"""
    id: int
    job_id: int
    stage: str
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    message: Optional[str] = None
    create_time: Any = None


class CourseGenerationWorkspaceFileOut(BaseModel):
    """工作区草稿的对外形状。"""
    id: int
    job_id: int
    path: str
    content: str
    version: int
    update_time: Any = None


# ------------------------- 教师端接口 DTO -------------------------
# 与 d:\PBL\teacher-frontend\teacher-frontend\src\api\system\course-generation-api.ts
# 及 src\composables\stream\useContentGeneration.ts 的字段约定保持一致。

class DetectTemplateRequest(BaseModel):
    """模板检测请求：学习路径 JSON（章节与知识点结构）。"""
    learning_path: Dict[str, Any]


class SuggestedTemplate(BaseModel):
    """建议模板。"""
    id: str
    name: str
    description: str


class DetectTemplateResponse(BaseModel):
    """模板检测响应。"""
    matched: bool = False
    template_id: Optional[str] = None
    template_name: Optional[str] = None
    reason: Optional[str] = None
    confidence: Optional[str] = None
    message: Optional[str] = None
    suggested_templates: Optional[List[SuggestedTemplate]] = None


class ThemeInfo(BaseModel):
    """示例主题。"""
    id: str
    name: str
    description: str


class TemplateMetaResponse(BaseModel):
    """模板元数据（用于汇总编辑区分 Web/代码题及判题语言）。"""
    template_id: str
    template_name: str
    checkpoint_paradigm: str  # "web" | "code"
    language: str


class StageInfo(BaseModel):
    """模板的一个生成阶段。"""
    stage: str
    name: str
    enabled: bool


class GetStagesResponse(BaseModel):
    """模板的生成阶段列表。"""
    template_id: str
    template_name: str
    stages: List[StageInfo]


class CreateJobRequest(BaseModel):
    """创建课程生成任务：学习路径 + 生成配置。"""
    learning_path: Dict[str, Any]
    config: Dict[str, Any] = Field(default_factory=dict)


class CreateJobResponse(BaseModel):
    """创建任务后立即返回 jobId 与状态，前端随即订阅 SSE。"""
    jobId: str
    status: str


class OutlineChapter(BaseModel):
    """大纲中的一章（LLM 生成，前端可编辑）。"""
    key: str
    title: str
    description: str = ""


class OutlineRequest(BaseModel):
    """一句话主题 → 课程大纲 的请求（OpenMAIC 式输入方式）。"""
    topic: str = Field(..., min_length=1, max_length=200)


class OutlineResponse(BaseModel):
    """大纲生成响应：课程标题/简介 + 章节列表（4~6 章）。"""
    title: str
    description: str = ""
    chapters: List[OutlineChapter] = Field(default_factory=list)


class GenerationDraft(BaseModel):
    """任务草稿（前端编辑后暂存 / 刷新恢复用）。"""
    task_id: str
    status: str
    progress: float = 0.0
    message: Optional[str] = None
    learning_path: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    draft_result: Optional[Dict[str, Any]] = None
    confirmed_data: Optional[Dict[str, Any]] = None
    updated_at: Optional[int] = None


class GenerationProgressMessage(BaseModel):
    """SSE 推流消息，type 取值见 useContentGeneration.ts 的 GenerationProgressMessage。"""
    type: str
    task_id: str
    stage: Optional[str] = None
    node_id: Optional[str] = None
    node_type: Optional[str] = None
    progress: float = 0.0
    message: str = ""
    index: Optional[int] = None
    total: Optional[int] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
