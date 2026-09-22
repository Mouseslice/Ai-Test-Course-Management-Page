import logging
import re
import time
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from types import SimpleNamespace
from typing import Any, Dict
from app.schemas.submission import TestSubmissionRequest, TestSubmissionResponse, TestSubmissionAsyncResponse
from app.schemas.judge_preview import (
    PreviewErrorInfo,
    PreviewJudgeRequest,
    PreviewJudgeResponse,
    PreviewMetrics,
    PreviewTestCaseResultItem,
)
from app.tasks.submission_tasks import process_submission_task
from app.celery_app import celery_app
from celery.result import AsyncResult
from app.services.sandbox_service import sandbox_service
from app.services.user_state_service import UserStateService
from app.services.content_loader import load_json_content
from app.config.dependency_injection import get_user_state_service, get_db, get_redis_client
from app.crud.crud_progress import progress as crud_progress
from app.schemas.user_progress import UserProgressCreate
from app.schemas.response import StandardResponse
from app.tasks.db_tasks import save_progress_task, save_code_submission_task

router = APIRouter()

@router.post("/submit-test2", response_model=StandardResponse[TestSubmissionAsyncResponse], status_code=202)
def submit_test2(
    *,
    submission_in: TestSubmissionRequest,
) -> Any:
    """
    接收用户代码提交，异步进行评测，并返回任务ID。
    """
    # 使用Celery队列异步保存用户提交的代码到数据库
    submission_data = {
        "participant_id": submission_in.participant_id,
        "topic_id": submission_in.topic_id,
        "html_code": submission_in.code.html,
        "css_code": submission_in.code.css,
        "js_code": submission_in.code.js
    }
    save_code_submission_task.apply_async(
        args=[submission_data],
        queue='db_writer_queue'
    )
    
    task = process_submission_task.apply_async(
        args=[submission_in.model_dump()],
        queue='submit_queue'
    )
    return StandardResponse(data={"task_id": task.id})

@router.get("/submit-test2/result/{task_id}", response_model=StandardResponse[TestSubmissionResponse])
def get_submission_result(task_id: str) -> Any:
    """
    获取异步代码评测任务的结果。
    """
    task_result = AsyncResult(task_id, app=celery_app)
    if not task_result.ready():
        raise HTTPException(status_code=202, detail={"status": task_result.status})
    
    result = task_result.get()
    if task_result.failed():
        raise HTTPException(status_code=500, detail=result)
        
    return StandardResponse(data=result)

@router.post("/submit-test", response_model=StandardResponse[TestSubmissionResponse])
def submit_test(
        *,
        db: Session = Depends(get_db),
        submission_in: TestSubmissionRequest,
        user_state_service: UserStateService = Depends(lambda: get_user_state_service(get_redis_client()))
) -> Any:
    """
    接收用户代码提交，进行评测，更新BKT模型，并返回结果。
    """
    # 记录提交的代码内容用于调试
    print(f"Received submission for participant {submission_in.participant_id}, topic {submission_in.topic_id}")
    print(f"Submitted code: {submission_in.code}")

    # 使用Celery队列异步保存用户提交的代码到数据库
    submission_data = {
        "participant_id": submission_in.participant_id,
        "topic_id": submission_in.topic_id,
        "html_code": submission_in.code.html,
        "css_code": submission_in.code.css,
        "js_code": submission_in.code.js
    }
    save_code_submission_task.apply_async(
        args=[submission_data],
        queue='db_writer_queue'
    )

    # 1. 加载测试内容
    try:
        test_task_data = load_json_content("test_tasks", submission_in.topic_id)
        checkpoints = test_task_data.checkpoints
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Topic '{submission_in.topic_id}' not found.")
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    # 2. 执行代码评测
    # 注意：这里的sandbox_service是直接导入的单例，如果未来需要更复杂的依赖管理，
    # 也可以像user_state_service一样通过Depends注入。
    evaluation_result = sandbox_service.run_evaluation(
        user_code=submission_in.code.model_dump(),
        checkpoints=checkpoints,
        topic_id=submission_in.topic_id,
    )

    # 3. 更新学生模型
    user_state_service.update_bkt_on_submission(
        participant_id=submission_in.participant_id,
        topic_id=submission_in.topic_id,
        is_correct=evaluation_result["passed"]
    )

    # 4. 触发一次快照检查（可选但推荐）
    # 这确保了BKT模型更新后，状态能及时被保存
    user_state_service.maybe_create_snapshot(submission_in.participant_id, db)

    # 5. 如果测试通过，使用Celery队列异步更新用户进度记录
    if evaluation_result["passed"]:
        progress_data = UserProgressCreate(
            participant_id=submission_in.participant_id,
            topic_id=submission_in.topic_id
        )
        save_progress_task.apply_async(
            args=[progress_data.model_dump()],
            queue='db_writer_queue'
        )

    # 6. 返回评测结果
    return StandardResponse(data=evaluation_result)


def _to_checkpoint_obj(cp) -> SimpleNamespace:
    """教师端扁平检查点 → 后端属性式检查点对象。

    沙箱（sandbox_service._evaluate_checkpoint）按属性访问检查点字段
    （cp.type / cp.assertion / cp.action_type 等），而教师端 CheckpointParam
    是扁平 dict 结构（见 schemas/judge_preview.py），因此这里用
    SimpleNamespace 适配为属性式对象，并将扁平字段同时当作嵌套断言的来源。
    """
    ns = SimpleNamespace(
        type=cp.type or "",
        name=cp.name or "",
        feedback=cp.feedback,
        selector=cp.selector or "",
        assertion_type=cp.assertion_type,
        value=cp.value,
        css_property=cp.css_property,
        attribute=cp.attribute,
        script=cp.script,
        action_selector=cp.action_selector,
        action_type=cp.action_type,
        action_value=cp.action_value,
    )
    if ns.type == "interaction_and_assert":
        if cp.assertion is not None:
            # 客户端显式提供嵌套断言（如真实内容里的 interaction_and_assert）：
            # 递归适配为属性式对象，保证"点击后再断言文本/样式/属性"等完整语义
            ns.assertion = _to_checkpoint_obj(cp.assertion)
        else:
            # 兼容扁平结构：无法单独表达嵌套断言的种类，只能按携带字段推断
            # （script→自定义脚本 / css_property→样式 / attribute→属性，
            # 其余默认元素断言，其 exists/contains/equals 分支与文本断言语义兼容）
            nested_kind = (
                "custom_script" if ns.script
                else "assert_style" if ns.css_property
                else "assert_attribute" if ns.attribute
                else "assert_element"
            )
            ns.assertion = SimpleNamespace(
                type=nested_kind,
                selector=ns.selector,
                assertion_type=cp.assertion_type,
                value=ns.value,
                css_property=ns.css_property,
                attribute=ns.attribute,
                script=ns.script,
            )
    else:
        ns.assertion = None
    return ns


@router.post("/previews", response_model=StandardResponse[PreviewJudgeResponse])
def preview_judge(submission_in: PreviewJudgeRequest) -> Any:
    """
    判题预览（不创建提交记录）。

    教师端内容生成器的测试题编辑组件（TestQuestionForm.vue）在"保存前本地
    判题预览"时调用本接口：
      - Web 模式（codeBundle + checkpoints）：复用学生端 playwright 沙箱
        逐项评测，映射为 JudgeResponseVO；
      - 代码题模式（languageMode + code + testCases）：后端暂未接入代码运行
        沙箱，返回明确的 unsupported 提示（success=false），避免前端拿到
        异常响应直接 break。
    """
    web_mode = submission_in.codeBundle is not None and submission_in.checkpoints is not None
    code_mode = submission_in.languageMode is not None and submission_in.code is not None
    if not web_mode and not code_mode:
        raise HTTPException(
            status_code=422,
            detail="参数不完整：Web 模式需提供 codeBundle 与 checkpoints，代码题模式需提供 languageMode 与 code",
        )

    if code_mode:
        total = len(submission_in.testCases or [])
        skipped = [
            PreviewTestCaseResultItem(
                index=i,
                status="SKIPPED",
                expected=tc.expected,
                actual="暂未评测",
            )
            for i, tc in enumerate(submission_in.testCases or [])
        ]
        return StandardResponse(code=0, data=PreviewJudgeResponse(
            status="unsupported",
            success=False,
            score=0,
            passedCount=0,
            totalCount=total,
            message=f"代码题判题预览暂未开放：后端暂未接入 {submission_in.languageMode} 运行沙箱，发布后由学生端评测。",
            testCaseResults=skipped,
        ))

    # Web 模式：适配检查点后复用学生端沙箱评测
    checkpoints = [_to_checkpoint_obj(cp) for cp in submission_in.checkpoints]
    started = time.monotonic()
    try:
        evaluation = sandbox_service.run_evaluation(
            user_code=submission_in.codeBundle.model_dump(),
            checkpoints=checkpoints,
            topic_id=None,
        )
    except Exception as e:
        logging.getLogger(__name__).exception("判题预览执行失败")
        return StandardResponse(code=0, data=PreviewJudgeResponse(
            status="error",
            success=False,
            score=0,
            passedCount=0,
            totalCount=len(checkpoints),
            errorInfo=PreviewErrorInfo(errorType="INTERNAL", message=str(e)),
            message="判题预览执行失败，请检查代码与检查点定义。",
        ))
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # 解析沙箱返回：失败 detail 形如 "检查点 {N} 失败: {feedback}"（1-based），
    # 定位失败检查点索引，并剥离前缀拿到用户可读的失败原因
    failed_indexes: Dict[int, str] = {}
    for detail in evaluation.get("details", []):
        matched = re.match(r"^检查点\s+(\d+)\s+失败:\s*(.*)$", detail)
        if matched:
            failed_indexes[int(matched.group(1)) - 1] = matched.group(2)

    total = len(checkpoints)
    passed = sum(1 for i in range(total) if i not in failed_indexes)
    results = [
        PreviewTestCaseResultItem(
            index=i,
            status="ACCEPTED" if i not in failed_indexes else "FAILED",
            expected=checkpoints[i].name or None,
            actual=None if i not in failed_indexes else failed_indexes[i],
        )
        for i in range(total)
    ]
    return StandardResponse(code=0, data=PreviewJudgeResponse(
        status="SUCCESS" if evaluation["passed"] else "FAILED",
        success=evaluation["passed"],
        score=round(passed / total * 100) if total else 0,
        passedCount=passed,
        totalCount=total,
        metrics=PreviewMetrics(executionTime=elapsed_ms, totalTime=elapsed_ms),
        testCaseResults=results,
        message=evaluation.get("message"),
    ))
