from fastapi import APIRouter
from app.api.endpoints import session, chat, submission, content, config, progress, knowledge_graph, behavior,websocket
from app.api.endpoints import course_generation
from app.api.endpoints import teacher_menu
from app.api.endpoints import user
from app.api.endpoints import course
from app.api.endpoints import logs
from app.api.endpoints import analysis

api_router = APIRouter()
api_router.include_router(session.router, prefix="/session", tags=["session"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(submission.router, prefix="/submission", tags=["submission"])
api_router.include_router(content.router, tags=["learning-content", "test-tasks"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(knowledge_graph.router, prefix="/knowledge-graph", tags=["knowledge-graph"])
api_router.include_router(behavior.router, prefix="/behavior", tags=["behavior"])
api_router.include_router(course_generation.router, prefix="/teacher-portal/course-generation",
                          tags=["teacher-portal", "course-generation"])
api_router.include_router(teacher_menu.router, prefix="/teacher-portal", tags=["teacher-portal", "menu"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(course.router, prefix="/course", tags=["course"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(analysis.router, prefix="/teacher-portal/analysis",
                          tags=["teacher-portal", "analysis"])


api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])