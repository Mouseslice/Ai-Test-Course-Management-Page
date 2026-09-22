"""发布器：把工作区产物按发布契约写成平台课程。

对应 Go 侧 coursegen/publish.go。三道顺序不可变：
  1. BeginPublish：终审不变量检查（终审之后工作区又动过 → 终审作废）；
  2. PublishGeneratedCourse：校验 course.json 契约 → 写入平台课程；
  3. CompletePublish：publishing → published。

契约不符（PublishContractError）不是失败——它是喂回 agent 的观察，让它自己改产物。
平台写入落 courses / course_content 两张表（与教师端课程管理接口同库，
backend_data 卷挂载，后端容器立即可见）：courses 让生成课程进入课程列表，
course_content 存章节结构 + 总览 HTML（markdown 经 mistune 转 HTML）。
"""
import html as html_escape
import json
import logging
from typing import Any, Dict, Optional

import mistune

from app.core.config import settings
from app.crud.crud_course import course as course_repo
from app.crud.crud_course import course_content as content_repo
from app.db.database import SessionLocal
from app.models.course_generation import CourseGenerationJob
from app.services.course_generation import state
from app.services.course_generation.errors import FinalReviewStaleError, PublishContractError
from app.services.course_generation.harness import Harness
from app.services.course_generation.prompts import PUBLISH_CONTRACT

logger = logging.getLogger(__name__)

REQUIRED_UNIT_KEYS = {"key", "title", "sortOrder", "blocks"}
REQUIRED_BLOCK_KEYS = {"kind", "title", "bodyPath", "format", "sortOrder"}

# 生成课程编码前缀（字母/数字/连字符，符合课程编码规则）
_COURSE_CODE_PREFIX = "GEN-"


class Publisher:
    """课程发布器。"""

    def __init__(self, harness: Harness) -> None:
        self.harness = harness
        self.repo = harness.repo

    def publish(self, job: CourseGenerationJob) -> int:
        """执行完整发布流程，返回平台课程 ID。

        任何一步失败都先回滚到 running 再抛错，让驱动循环能把契约问题喂回 agent。
        """
        self._begin_publish(job)
        try:
            course_id = self._publish_course(job)
        except Exception as exc:
            self._rollback_to_running(job, exc)
            raise
        self._complete_publish(job, course_id)
        return course_id

    # ------------------------------ 三个顺序步骤 ------------------------------

    def _begin_publish(self, job: CourseGenerationJob) -> None:
        """BeginPublish：终审不变量。有 approved 的 final 评审，且其时间早于
        工作区最后一次写入 → 那次终审已作废，拒绝发布。"""
        approved_final = self.repo.count_approved_reviews(job.id, scope=state.SCOPE_FINAL)
        if approved_final > 0:
            final_time = self.repo.latest_approved_review_time(job.id, scope=state.SCOPE_FINAL)
            last_write = self.repo.latest_workspace_write_time(job.id)
            if final_time is not None and last_write is not None and last_write > final_time:
                self.harness.emit(job, state.STAGE_HARNESS, state.EVENT_PUBLISH_WARNING,
                                  {}, "终审之后工作区又被修改，终审作废")
                raise FinalReviewStaleError(
                    "coursegen: final review stale — workspace modified after final review")

    def _publish_course(self, job: CourseGenerationJob) -> int:
        """校验 course.json 契约 → 写入平台课程（courses + course_content 两行）。

        编码取 GEN-{job_uid} 保证唯一；同一 job 重试发布时按编码复用已有课程行
        （幂等），内容整体覆盖保存。返回真实课程主键。
        """
        self.harness.change_status(job, state.Status.PUBLISHING, "正在发布课程")

        raw = self._read_course_json(job)
        course = self._validate_contract(job, raw)

        # ---- 平台写入：落库而非落文件，后端容器通过共享库立即可见 ----
        course_code = f"{_COURSE_CODE_PREFIX}{job.job_uid}"
        bodies = self._read_block_bodies(job, course)
        meta = self._build_meta(job, course)

        with SessionLocal() as db:
            row = course_repo.get_by_code(db, course_code)
            if row is None:
                row = course_repo.create(
                    db, course_code=course_code, title=course["title"],
                    description=course.get("description"), cover_url=None,
                    status="draft", meta=meta,
                )
            else:
                # 发布重试幂等：复用已有课程行，仅覆盖标题/说明/meta（保留状态）
                row = course_repo.update(
                    db, row, course_code=course_code, title=course["title"],
                    description=course.get("description"), cover_url=None,
                    status=row.status, meta=meta,
                )
            content_repo.upsert(
                db, course=row, title=course["title"],
                html=self._build_overview_html(course, bodies),
                knowledge_dict=self._build_knowledge_dict(course),
                chapter_dict=self._build_chapter_dict(course),
                learning_path=self._build_learning_path(job),
                knowledge_graph_dict=self._build_knowledge_graph_dict(course),
                scenes=self._build_scenes(course),
            )
            course_id = row.id  # 会话内取值，避免脱离会话后惰性加载报错

        logger.info("coursegen: published course %s -> courses id=%s code=%s",
                    job.job_uid, course_id, course_code)
        return course_id

    def _complete_publish(self, job: CourseGenerationJob, course_id: int) -> None:
        """publishing → published，记发布结果。"""
        self.repo.mark_published(job.id, course_id)
        job.published_course_id = course_id
        self.harness.change_status(job, state.Status.PUBLISHED, "课程发布完成")

    # ------------------------------ 辅助 ------------------------------

    def _rollback_to_running(self, job: CourseGenerationJob, exc: Exception) -> None:
        """发布失败回滚：publishing → running（允许重试），并广播原因。"""
        self.harness.emit(job, state.STAGE_HARNESS, state.EVENT_PUBLISH_WARNING,
                          {"error": str(exc)}, f"发布未完成：{exc}")
        try:
            if state.parse_status(job.status) == state.Status.PUBLISHING:
                self.harness.change_status(job, state.Status.RUNNING, "发布未完成，回到生成")
        except Exception as rollback_exc:  # 回滚失败多半是并发裁决，不再覆盖
            logger.warning("coursegen: publish rollback failed for job %s: %s",
                           job.job_uid, rollback_exc)

    def _read_course_json(self, job: CourseGenerationJob) -> Dict[str, Any]:
        """读工作区 course.json；缺失即契约不符（需要 agent 自己补）。"""
        item = self.repo.get_workspace_file(job.id, "course.json")
        if item is None:
            self.harness.emit(job, state.STAGE_HARNESS, state.EVENT_PUBLISH_WARNING,
                              {}, "工作区缺少 course.json")
            raise PublishContractError("coursegen: course.json missing in workspace")
        try:
            parsed = json.loads(item.content)
        except json.JSONDecodeError as exc:
            raise PublishContractError(f"coursegen: course.json invalid JSON: {exc}") from exc
        return parsed if isinstance(parsed, dict) else {}

    def _validate_contract(self, job: CourseGenerationJob, course: Dict[str, Any]) -> Dict[str, Any]:
        """对照发布契约校验 course.json，契约不符抛 PublishContractError（喂回 agent）。"""
        problems: list[str] = []
        if not course.get("title"):
            problems.append("title 缺失")
        if not course.get("courseType"):
            problems.append("courseType 缺失")
        units = course.get("units")
        if not isinstance(units, list) or len(units) == 0:
            problems.append("units 不能为空")
        else:
            for i, unit in enumerate(units):
                if not isinstance(unit, dict):
                    problems.append(f"units[{i}] 不是对象")
                    continue
                if not REQUIRED_UNIT_KEYS.issubset(set(unit.keys())):
                    problems.append(f"units[{i}] 缺少键 {sorted(REQUIRED_UNIT_KEYS - set(unit.keys()))}")
                blocks = unit.get("blocks")
                if not isinstance(blocks, list) or len(blocks) == 0:
                    problems.append(f"units[{i}] blocks 不能为空")
                else:
                    for j, block in enumerate(blocks):
                        if not isinstance(block, dict):
                            problems.append(f"units[{i}].blocks[{j}] 不是对象")
                            continue
                        # 报出具体缺失的键，让 agent 拿到可执行的修复指引
                        missing = sorted(REQUIRED_BLOCK_KEYS - set(block.keys()))
                        if missing:
                            problems.append(f"units[{i}].blocks[{j}] 缺少键 {missing}")

        if problems:
            self.harness.emit(job, state.STAGE_HARNESS, state.EVENT_PUBLISH_WARNING,
                              {"problems": problems}, f"course.json 不满足发布契约：{'；'.join(problems)}")
            raise PublishContractError("coursegen: publish contract violation: " + "; ".join(problems))
        return course

    def _read_block_bodies(self, job: CourseGenerationJob,
                           course: Dict[str, Any]) -> Dict[str, str]:
        """按 block.bodyPath 从工作区读各块正文（markdown），读不到给空串。"""
        bodies: Dict[str, str] = {}
        for unit in course.get("units") or []:
            for block in unit.get("blocks") or []:
                path = block.get("bodyPath")
                if not path:
                    continue
                item = self.repo.get_workspace_file(job.id, path)
                bodies[path] = item.content if item is not None else ""
        return bodies

    def _build_scenes(self, course: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """course.json 顶层 scenes → course_content.scenes。

        scenes 是 OpenMAIC 式场景序列（slides/quiz/interactive），场景式生成器
        （LlmGenerator）产出；本地生成器不产出，返回 None（保持传统视图）。
        学生端场景播放器按 {scenes: [...]} 读取。
        """
        scenes = course.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            return None
        return {"scenes": scenes}

    def _build_knowledge_dict(self, course: Dict[str, Any]) -> Dict[str, Any]:
        """units → knowledge_dict（知识点字典，含测试任务 test_content）。

        每个章节作为一个知识点：key 与 chapter_dict 对齐（前端 content-summary
        用同一 key 关联知识点与图谱）；章节级 tests 挂到 test_content，让学生端
        可以呈现知识点测试。
        """
        out: Dict[str, Any] = {}
        for i, unit in enumerate(course.get("units") or []):
            key = str(unit.get("key") or f"chapter-{i + 1}")
            tests = unit.get("tests") or []
            test_content = tests[0] if isinstance(tests, list) and tests else None
            out[key] = {
                "topic_id": key,
                "title": str(unit.get("title") or key),
                "levels": [],
                "test_content": test_content,
            }
        return out

    def _build_knowledge_graph_dict(self, course: Dict[str, Any]) -> Dict[str, Any]:
        """course.json 顶层 knowledgeGraph → knowledge_graph_dict。

        前端/学生端按 {sectionId: {nodes, edges}} 读图；生成器产出的是整门课程
        一张全局图（节点覆盖全部章节），统一挂到 root 键，sectionId=root、
        sectionTitle 取课程标题。LLM 未产出图谱时返回空 dict（前端兜底）。
        """
        kg = course.get("knowledgeGraph")
        if not isinstance(kg, dict):
            return {}
        nodes = kg.get("nodes") or []
        edges = kg.get("edges") or []
        if not nodes and not edges:
            return {}
        return {"root": {"title": str(course.get("title") or "课程知识图谱"),
                         "nodes": nodes, "edges": edges}}

    def _build_learning_path(self, job) -> Optional[Dict[str, Any]]:
        """把创建任务时上传的学习路径原样落库，供学生端/前端回读。"""
        payload = job.request_payload if isinstance(job.request_payload, dict) else {}
        lp = payload.get("learning_path")
        return lp if isinstance(lp, dict) else None

    def _build_chapter_dict(self, course: Dict[str, Any]) -> Dict[str, Any]:
        """units → chapter_dict（教师端 content-summary 据此重建章节树）。"""
        out: Dict[str, Any] = {}
        for i, unit in enumerate(course.get("units") or []):
            key = str(unit.get("key") or f"chapter-{i + 1}")
            sections = []
            for j, block in enumerate(unit.get("blocks") or []):
                sid = str(block.get("bodyPath") or f"section-{j + 1}")
                sections.append({"id": sid, "title": str(block.get("title") or sid)})
            out[key] = {
                "chapter_id": key,
                "title": str(unit.get("title") or key),
                "sections": sections,
            }
        return out

    def _build_overview_html(self, course: Dict[str, Any],
                             bodies: Dict[str, str]) -> str:
        """course.json + 各 block 正文 → 总览 HTML（markdown 用 mistune 转 HTML）。"""
        md = mistune.create_markdown(escape=False)
        parts = [f"<h1>{html_escape.escape(course['title'])}</h1>"]
        if course.get("description"):
            parts.append(f"<p>{html_escape.escape(str(course['description']))}</p>")
        for i, unit in enumerate(course.get("units") or []):
            unit_title = str(unit.get("title") or f"第{i + 1}章")
            parts.append(f"<h2>{html_escape.escape(unit_title)}</h2>")
            if unit.get("description"):
                parts.append(f"<p>{html_escape.escape(str(unit['description']))}</p>")
            for block in unit.get("blocks") or []:
                block_title = str(block.get("title") or "")
                if block_title:
                    parts.append(f"<h3>{html_escape.escape(block_title)}</h3>")
                body = bodies.get(block.get("bodyPath") or "", "")
                if body:
                    parts.append(md(body))
        return "\n".join(parts)

    def _build_meta(self, job: CourseGenerationJob,
                    course: Dict[str, Any]) -> Dict[str, Any]:
        """发布时写入 courses.meta：模板/范例模式 + 溯源信息。"""
        payload = job.request_payload if isinstance(job.request_payload, dict) else {}
        cfg = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        course_type = str(course.get("courseType") or "")
        return {
            "source": "coursegen",
            "jobUid": job.job_uid,
            "templateId": str(cfg.get("templateId") or cfg.get("template_id") or ""),
            "checkpointParadigm": "code" if "code" in course_type.lower() else "web",
            "courseType": course_type,
            "allowedRuntimes": course.get("allowedRuntimes") or [],
        }
