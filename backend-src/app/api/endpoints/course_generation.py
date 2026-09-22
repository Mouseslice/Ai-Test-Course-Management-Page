r"""教师端课程生成门户接口（/api/v1/teacher-portal/course-generation/*）。

对接前端 d:\PBL\teacher-frontend\teacher-frontend\src\api\system\course-generation-api.ts
与 src\composables\stream\useContentGeneration.ts：
  - 模板/主题/阶段：模板元数据静态目录（catalog.py），detect-template 未启用
    LLM 检测（生成链路已本地化），返回建议模板列表由教师手动选择；
  - jobs 生命周期：创建即启动（入队 Celery 驱动）、取消、确认（裁决评审并续跑）；
  - draft：刷新恢复 + 前端编辑暂存；
  - stream：SSE 推流，事件源是 course_generation_events 表（支持 Last-Event-ID 续传）。

响应包装统一为 {code: 0, data, message}（code=0 成功），与前端请求拦截器约定一致。
"""
import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.course_generation import (
    CreateJobRequest,
    CreateJobResponse,
    DetectTemplateRequest,
    DetectTemplateResponse,
    GenerationDraft,
    GenerationProgressMessage,
    GetStagesResponse,
    OutlineRequest,
    OutlineResponse,
    SuggestedTemplate,
    TemplateMetaResponse,
    ThemeInfo,
)
from app.schemas.response import StandardResponse
from app.services.course_generation import catalog, state
from app.services.course_generation.errors import JobNotFoundError
from app.services.course_generation.harness import Harness
from app.services.course_generation.repository import SQLRepository
from app.tasks.course_generation_tasks import drive_generation_job

logger = logging.getLogger(__name__)

router = APIRouter()

# 仓储单例：每次操作自开会话，可安全用于后台驱动与请求上下文
_repo = SQLRepository()

# 当前教师标识：教师端认证（/api/user/*）接入后替换为真实解析；骨架阶段统一占位
_CURRENT_USER_ID = "teacher"

# SSE 心跳间隔（秒）
_SSE_PING_INTERVAL = 15


def _ok(data: Any, message: str = "success") -> StandardResponse:
    """统一成功包装：code=0 与教师端约定一致（区别于原有后端 code=200）。"""
    return StandardResponse(code=0, message=message, data=data)


def _get_job_or_404(job_uid: str):
    """按对外 job_uid 取 job；不存在抛 404。"""
    try:
        return _repo.get_job_by_uid(job_uid)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=f"课程生成任务不存在: {job_uid}")


def _progress(job) -> float:
    """进度：发布完成 = 100；有预算则按 token 消耗比例，封顶 99 等待终态事件。"""
    if job.status == state.Status.PUBLISHED.value:
        return 100.0
    budget = job.token_budget or 0
    if budget > 0:
        return min(round((job.tokens_spent or 0) / budget * 100, 1), 99.0)
    return 0.0


# ------------------------------ 模板 / 主题 / 阶段 ------------------------------


@router.post("/detect-template", response_model=StandardResponse[DetectTemplateResponse])
def detect_template(req: DetectTemplateRequest) -> StandardResponse[DetectTemplateResponse]:
    """检测学习路径匹配的课程模板。

    未启用 LLM 模板检测：直接返回建议模板列表（matched=False），由教师
    手动选择模板后继续生成，前端流程不中断。
    """
    suggested = [
        SuggestedTemplate(id=t["template_id"], name=t["template_name"],
                          description=f"checkpoint_paradigm={t['checkpoint_paradigm']}")
        for t in catalog.TEMPLATES
    ]

    logger.info("coursegen: detect-template skipped (LLM detection disabled), return suggestions")
    return _ok(DetectTemplateResponse(
        matched=False,
        template_id=None,
        template_name=None,
        reason="未启用 LLM 模板检测，请手动选择",
        confidence="low",
        message="请从建议模板中选择",
        suggested_templates=suggested))


# ------------------------------ 一句话主题 → 大纲 ------------------------------
# OpenMAIC 式输入方式：教师输入一句话主题，LLM 扩成结构化大纲（标题+章节），
# 前端确认/编辑后走现有「选模板 → 本地生成」流程。LLM 仅在这一步调用一次。

# LLM 大纲限定输出键：防止模型自由发挥产生前端无法渲染的字段
_OUTLINE_MAX_CHAPTERS = 6


def _build_outline_prompt(topic: str) -> str:
    """构造大纲生成提示词：把一句话主题扩成结构化章节大纲，限定 JSON 契约。"""
    return (
        "你是课程大纲设计专家。请把用户的一句话主题扩成一份结构化课程大纲。\n\n"
        f"用户主题：{topic}\n\n"
        "严格只输出一个 JSON 对象，不要输出任何其他文字。字段说明：\n"
        '- "title"：字符串，课程标题（不超过 50 字）；\n'
        '- "description"：字符串，课程简介（不超过 200 字）；\n'
        '- "chapters"：数组，4 到 6 个章节，每项包含：\n'
        '    - "key"：字符串，唯一标识，如 "ch1"（小写字母/数字/连字符）；\n'
        '    - "title"：字符串，章节标题（不超过 30 字）；\n'
        '    - "description"：字符串，章节简介（不超过 60 字）。\n'
        "章节从易到难循序渐进，完整覆盖该主题的核心知识点。"
    )


def _expand_topic_outline(topic: str) -> Dict[str, Any]:
    """调用 LLM 把一句话主题扩成结构化大纲；解析失败抛异常由上层转 HTTP 错误。"""
    from app.services.llm_gateway import llm_gateway  # 延迟导入，避免启动期依赖

    content = llm_gateway.get_completion_sync(
        system_prompt="你只输出合法 JSON，不输出任何多余文字。",
        messages=[{"role": "user", "content": _build_outline_prompt(topic)}],
    )
    text = (content or "").strip()
    # 模型可能把 JSON 包在 ```json 代码块里，剥离后解析
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"大纲 JSON 解析失败：{exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("大纲不是 JSON 对象")

    title = str(parsed.get("title") or topic).strip()[:50] or topic
    description = str(parsed.get("description") or "").strip()[:200]
    chapters: List[Dict[str, str]] = []
    raw_chapters = parsed.get("chapters")
    if not isinstance(raw_chapters, list):
        raise ValueError("大纲缺少 chapters 数组")
    for i, ch in enumerate(raw_chapters[: _OUTLINE_MAX_CHAPTERS]):
        if not isinstance(ch, dict):
            continue
        ch_title = str(ch.get("title") or "").strip()
        if not ch_title:
            continue
        chapters.append({
            "key": str(ch.get("key") or f"ch{i + 1}").strip() or f"ch{i + 1}",
            "title": ch_title[:30],
            "description": str(ch.get("description") or "").strip()[:60],
        })
    if not chapters:
        raise ValueError("大纲章节标题为空")
    return {"title": title, "description": description, "chapters": chapters}


@router.post("/outline", response_model=StandardResponse[OutlineResponse])
async def generate_outline(req: OutlineRequest) -> StandardResponse[OutlineResponse]:
    """把一句话主题扩成结构化课程大纲（LLM，带超时保护）。

    超时/调用失败返回可读错误，前端提示教师重试或改用上传学习路径。
    """
    try:
        outline = await asyncio.wait_for(
            asyncio.to_thread(_expand_topic_outline, req.topic),
            timeout=settings.COURSEGEN_OUTLINE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("coursegen: outline timeout for topic=%s", req.topic)
        raise HTTPException(status_code=504, detail="大纲生成超时，请稍后重试")
    except Exception as exc:
        logger.exception("coursegen: outline failed for topic=%s", req.topic)
        raise HTTPException(status_code=502, detail=f"大纲生成失败：{exc}")
    logger.info("coursegen: outline generated for topic=%s (chapters=%d)",
                req.topic, len(outline["chapters"]))
    return _ok(OutlineResponse(**outline))


@router.get("/themes", response_model=StandardResponse[List[ThemeInfo]])
def list_themes() -> StandardResponse[List[ThemeInfo]]:
    """示例主题列表。"""
    return _ok([ThemeInfo(**t) for t in catalog.THEMES])


@router.get("/themes/{theme_id}", response_model=StandardResponse[ThemeInfo])
def get_theme(theme_id: str) -> StandardResponse[ThemeInfo]:
    """单个主题详情。"""
    item = catalog.get_theme(theme_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"主题不存在: {theme_id}")
    return _ok(ThemeInfo(**item))


@router.get("/templates/{template_id}", response_model=StandardResponse[TemplateMetaResponse])
def get_template(template_id: str) -> StandardResponse[TemplateMetaResponse]:
    """模板元数据（判题范式与语言，供汇总编辑区渲染）。"""
    item = catalog.get_template(template_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_id}")
    return _ok(TemplateMetaResponse(
        template_id=item["template_id"], template_name=item["template_name"],
        checkpoint_paradigm=item["checkpoint_paradigm"], language=item["language"]))


@router.get("/stages/{template_id}", response_model=StandardResponse[GetStagesResponse])
def get_stages(template_id: str) -> StandardResponse[GetStagesResponse]:
    """模板的生成阶段（前端进度编排面板）。"""
    item = catalog.get_template(template_id)
    if not item:
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_id}")
    return _ok(GetStagesResponse(template_id=template_id, template_name=item["template_name"],
                                 stages=catalog.STAGES.get(template_id, [])))


# ------------------------------ 任务生命周期 ------------------------------

@router.post("/jobs", response_model=StandardResponse[CreateJobResponse], status_code=202)
def create_job(req: CreateJobRequest) -> StandardResponse[CreateJobResponse]:
    """创建课程生成任务并立即启动（入队 Celery 驱动），返回 jobId 供订阅 SSE。"""
    harness = Harness(_repo)
    job = harness.create_job(
        job_uid=uuid.uuid4().hex,
        user_id=_CURRENT_USER_ID,
        request_payload={"learning_path": req.learning_path, "config": req.config},
        token_budget=settings.COURSEGEN_DEFAULT_TOKEN_BUDGET,
    )
    harness.start(job)
    drive_generation_job.apply_async(args=[job.job_uid], queue=settings.COURSEGEN_QUEUE)
    logger.info("coursegen: job %s created and started by %s", job.job_uid, _CURRENT_USER_ID)
    return _ok(CreateJobResponse(jobId=job.job_uid, status=job.status), "任务已创建并启动")


@router.get("/jobs", response_model=StandardResponse[List[dict]])
def list_jobs() -> StandardResponse[List[dict]]:
    """当前教师的任务列表（轻量摘要）。"""
    jobs = _repo.list_jobs_by_user(_CURRENT_USER_ID, limit=50)
    return _ok([
        {"jobId": j.job_uid, "status": j.status, "progress": _progress(j),
         "updated_at": int(j.update_time.timestamp() * 1000) if j.update_time else None}
        for j in jobs
    ])


@router.get("/jobs/{job_id}/draft", response_model=StandardResponse[GenerationDraft])
def get_draft(job_id: str) -> StandardResponse[GenerationDraft]:
    """读取任务草稿（页面刷新恢复用）：状态、进度、意图、产物与教师已确认内容。"""
    job = _get_job_or_404(job_id)
    return _ok(_build_draft(job))


@router.post("/jobs/{job_id}/draft", response_model=StandardResponse[GenerationDraft])
def save_draft(job_id: str, payload: Dict[str, Any] = Body(default_factory=dict)) -> StandardResponse[GenerationDraft]:
    """暂存前端编辑的草稿内容（不改状态机，仅进 request_payload）。"""
    job = _get_job_or_404(job_id)
    _repo.patch_request_payload(job.id, {"draft": payload})
    job = _repo.get_job(job.id)
    return _ok(_build_draft(job))


@router.post("/jobs/{job_id}/cancel", response_model=StandardResponse[dict])
def cancel_job(job_id: str) -> StandardResponse[dict]:
    """取消任务；驱动循环会在下一轮看到 cancelled 并收尾。

    已发布（published）等终态任务不可取消，返回业务错误而非 500。
    """
    job = _get_job_or_404(job_id)
    if state.is_terminal(job.status):
        raise HTTPException(status_code=400, detail=f"任务已处于终态（{job.status}），无法取消")
    harness = Harness(_repo)
    harness.cancel(job)
    return _ok({"jobId": job_id, "status": job.status}, "任务已取消")


@router.post("/jobs/{job_id}/confirm", response_model=StandardResponse[dict], status_code=202)
def confirm_job(job_id: str, data: Dict[str, Any] = Body(default_factory=dict)) -> StandardResponse[dict]:
    """教师确认：批准最近的待裁决评审并续跑；同时把确认内容暂存进草稿。"""
    job = _get_job_or_404(job_id)
    harness = Harness(_repo)

    review = _repo.latest_pending_review(job.id)
    if review is not None:
        feedback = json.dumps(data, ensure_ascii=False) if data else None
        harness.decide_review(job, review.id, approved=True, feedback=feedback)
    _repo.patch_request_payload(job.id, {"confirmed_data": data})

    drive_generation_job.apply_async(args=[job.job_uid], queue=settings.COURSEGEN_QUEUE)
    return _ok({"jobId": job_id, "status": job.status}, "已确认，继续生成")


# ------------------------------ SSE 推流 ------------------------------

@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str, request: Request) -> StreamingResponse:
    """SSE 推流：事件源是 course_generation_events 表。

    - 支持 Last-Event-ID 续传（EventSource 断线重连自动带上）；
    - job 到终态（published/failed/cancelled）后推完剩余事件即关闭；
    - 等待教师确认期间保持连接，定期 ping 保活。
    """
    job = _get_job_or_404(job_id)
    raw = request.headers.get("last-event-id")
    after_id = int(raw) if raw and raw.isdigit() else 0
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",  # 关闭反向代理缓冲，保证事件即时到达
    }
    return StreamingResponse(_stream_events(job.job_uid, after_id),
                             media_type="text/event-stream", headers=headers)


async def _stream_events(job_uid: str, after_id: int):
    """SSE 生成器：轮询事件表并映射为前端消息类型。"""
    pings_since_event = 0
    while True:
        job = _repo.get_job_by_uid(job_uid)
        events = _repo.list_events_after(job.id, after_id, limit=100)

        for ev in events:
            msg = _map_event(ev, job)
            if msg is not None:
                payload = json.dumps(msg.model_dump(), ensure_ascii=False)
                yield f"id: {ev.id}\nevent: {msg.type}\ndata: {payload}\n\n"
            after_id = ev.id
            pings_since_event = 0

        job = _repo.get_job_by_uid(job_uid)
        if job.status in (state.Status.PUBLISHED.value, state.Status.FAILED.value,
                          state.Status.CANCELLED.value):
            return  # 终态：推完收尾

        pings_since_event += 1
        if pings_since_event >= _SSE_PING_INTERVAL:
            pings_since_event = 0
            ping = GenerationProgressMessage(type="ping", task_id=job_uid,
                                             progress=_progress(job), message="心跳")
            yield f"id: {job.id}\nevent: ping\ndata: {json.dumps(ping.model_dump(), ensure_ascii=False)}\n\n"

        await asyncio.sleep(1)


def _map_event(ev, job) -> Optional[GenerationProgressMessage]:
    """把库里的事件映射成前端的 GenerationProgressMessage；不需要推给前端的事件返回 None。"""
    msg = GenerationProgressMessage(type="ping", task_id=job.job_uid,
                                    message=ev.message or "", progress=_progress(job))
    etype = ev.event_type

    if etype == state.EVENT_JOB_CREATED:
        msg.type = "request_received"
    elif etype == state.EVENT_STATUS_CHANGED:
        to = ev.payload.get("to")
        if to == state.Status.PUBLISHED.value:
            msg.type, msg.progress = "generation_complete", 100.0
            msg.data = {"published_course_id": job.published_course_id}
        elif to == state.Status.FAILED.value:
            msg.type, msg.error = "error", ev.message or "生成失败"
        elif to == state.Status.CANCELLED.value:
            msg.type = "cancelled"
        elif to == state.Status.AWAITING_REVIEW.value:
            msg.type = "confirmed"  # 等待教师确认方向
        elif to == state.Status.RUNNING.value:
            msg.type = "confirmed"  # 教师裁决后恢复
        else:
            msg.type = "ping"
    elif etype == state.EVENT_EPISODE_STARTED:
        if ev.stage == state.STAGE_EPISODE:
            msg.type, msg.node_id, msg.node_type = "item_start", ev.payload.get("item"), "item"
        else:
            msg.type, msg.stage = "stage_start", "planning"
    elif etype == state.EVENT_EPISODE_FINISHED:
        if ev.stage == state.STAGE_EPISODE:
            msg.type, msg.node_id = "item_complete", ev.payload.get("item")
        else:
            msg.type, msg.stage = "stage_complete", "planning"
    elif etype in (state.EVENT_REVIEW_REQUESTED, state.EVENT_REVIEW_DECIDED,
                   state.EVENT_TEACHER_COMMENT):
        msg.type = "confirmed"
    elif etype in (state.EVENT_PLAN_UPDATED, state.EVENT_BUDGET_WARNING,
                   state.EVENT_BUDGET_ADJUSTED, state.EVENT_PUBLISH_WARNING):
        msg.type = "ping"
    else:  # tool_call 等内部事件不推前端
        return None
    return msg


def _build_draft(job) -> GenerationDraft:
    """组装任务草稿（GET/POST draft 共用）。"""
    payload = job.request_payload or {}

    draft_result: Optional[Dict[str, Any]] = None
    course_item = _repo.get_workspace_file(job.id, "course.json")
    if course_item is not None:
        try:
            course = json.loads(course_item.content)
        except json.JSONDecodeError:
            course = None
        if isinstance(course, dict):
            # coursegen 产物为 course.json（units/blocks），正文存在各 block.bodyPath 工作区文件里。
            # 一并注入 _block_bodies，供前端汇总编辑器按块重建知识点内容（Level 1 = 正文）。
            block_bodies: Dict[str, str] = {}
            for unit in course.get("units") or []:
                for block in unit.get("blocks") or []:
                    path = block.get("bodyPath")
                    if not path:
                        continue
                    item = _repo.get_workspace_file(job.id, path)
                    block_bodies[path] = item.content if item is not None else ""
            course = {**course, "_block_bodies": block_bodies}
            draft_result = course
    if draft_result is None and job.plan:
        draft_result = {"plan": job.plan}

    latest = _repo.latest_event(job.id)
    return GenerationDraft(
        task_id=job.job_uid,
        status=job.status,
        progress=_progress(job),
        message=latest.message if latest is not None else None,
        learning_path=payload.get("learning_path"),
        config=payload.get("config"),
        draft_result=draft_result,
        confirmed_data=payload.get("confirmed_data"),
        updated_at=int(job.update_time.timestamp() * 1000) if job.update_time else None,
    )
