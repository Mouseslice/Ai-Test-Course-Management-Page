from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.response import StandardResponse
from app.schemas.content import LearningContent, TestTask
from app.services.content_loader import load_json_content
from app.db.database import get_db
from app.crud.crud_course import course as course_repo
from app.crud.crud_course import course_content as content_repo

# 使用前缀统一版本管理,可修改
router = APIRouter()


@router.get("/learning-content/{topic_id}", response_model=StandardResponse[LearningContent])
def get_learning_content(topic_id: str):
    """
    获取指定主题的学习材料。
    """
    try:
        content_data = load_json_content("learning_content", topic_id)
        return StandardResponse(data=content_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/test-tasks/{topic_id}", response_model=StandardResponse[TestTask])
def get_test_task(topic_id: str):
    """
    获取指定主题的测试任务。
    """
    try:
        content_data = load_json_content("test_tasks", topic_id)
        return StandardResponse(data=content_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/scene-course/{course_id}")
def get_scene_course(course_id: int, db: Session = Depends(get_db)):
    """获取 OpenMAIC 式场景课件（学生端场景播放器数据源）。

    与教师端 content-summary 不同：本接口面向学生端公开读取（学生端无登录态），
    仅返回课程标题/简介与场景序列；无场景数据时返回空 scenes（前端容错为空课）。
    """
    row = course_repo.get_by_id(db, course_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"课程不存在: {course_id}")
    content = content_repo.get_by_course_id(db, row.id)
    scenes = content.scenes if content is not None and isinstance(content.scenes, dict) else {}
    # code=0 与教师端 request.ts 约定一致（区别于学生端旧接口 code=200）
    return StandardResponse(code=0, data={
        "courseId": row.id,
        "title": row.title,
        "description": row.description or "",
        "scenes": scenes.get("scenes") or [],
    })