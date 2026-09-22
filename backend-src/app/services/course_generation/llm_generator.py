"""OpenMAIC 式场景生成器：一句话主题 → LLM 生成场景序列课件。

对齐 OpenMAIC 的两阶段流水线（大纲 → 场景）：
  - 大纲：优先取教师确认后的 learning_path 章节；没有时由 LLM 根据主题生成 4~6 章；
  - 场景：每章由 LLM 一次生成三类场景（并发，整体 1~3 分钟）：
      slides       逐页讲解（每页 title + markdown 正文，构成一屏）；
      quiz         章节测验（单选题，本地即时判题，含解析）；
      interactive  交互练习（自包含 HTML：内联 CSS/JS 的小工具演示）；
      code         编程练习（仅当章节与编程相关时由 LLM 生成，含语言/题目/初始代码）。
  - 组装：scenes 写入 course.json 顶层；同时从 slides 派生 units/blocks（满足既有
    发布契约），让 knowledgeGraph / chapterDict / knowledgeDict 等传统部件继续可用。

生成产物同时具备两套视图：
  - 传统视图（章节 + 知识点 + 测试题）：学生端既有 learning_page 可读；
  - 场景视图（slides/quiz/interactive 序列）：学生端新增场景播放器读取 scenes。

与 LocalGenerator 复用同一发布契约；单章失败回退空场景（跳过 quiz/交互，
保留 slides 兜底标题），整体失败由 driver 回退 LocalGenerator。
"""
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.course_generation import CourseGenerationJob
from app.services.course_generation import state
from app.services.course_generation.harness import Harness

logger = logging.getLogger(__name__)

# 工作区里每个 block 正文的路径前缀（course.json 的 bodyPath 指向它们）
_BODY_PATH_PREFIX = "content"

# 章节并发调用上限（LLM 调用慢，串行会超 3 分钟）
_SCENE_MAX_WORKERS = 6
# 每章 slides 页数上下限 / quiz 题数上下限
_MIN_SLIDES_PER_CHAPTER = 2
_MAX_SLIDES_PER_CHAPTER = 4
_MIN_QUIZ_PER_CHAPTER = 1
_MAX_QUIZ_PER_CHAPTER = 3
# 大纲章节数量范围（无 learning_path 时由 LLM 生成）
_MIN_CHAPTERS = 4
_MAX_CHAPTERS = 6
# 组装 course.json 前的停顿（秒），给前端一点收尾过程感
_BUILD_GAP_SECONDS = 2.0
# 章节间最小停顿（秒），保留逐章推进的过程感
_STEP_GAP_SECONDS = 0.5


class LlmGenerator:
    """OpenMAIC 式场景生成器：LLM 按主题生成 slides/quiz/interactive 场景序列。"""

    def __init__(self, harness: Harness) -> None:
        self.harness = harness
        self.repo = harness.repo

    # ------------------------------ 对外入口 ------------------------------

    def generate(self, job: CourseGenerationJob) -> None:
        """执行一次场景式生成：大纲 → 并发生成场景 → 组装 course.json。

        完成后由 driver 调 Publisher 落库；单章失败已在内部降级，仅整体异常向上抛。
        """
        payload = job.request_payload if isinstance(job.request_payload, dict) else {}
        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        topic = str(config.get("topic") or "").strip()
        title = str(config.get("title") or "AI 生成课程").strip()
        description = str(config.get("description") or "").strip()
        lang = self._guess_language(topic, config)

        # 1. 大纲章节：优先用确认后的大纲，没有则由 LLM 生成
        chapter_titles = self._outline_chapter_titles(payload.get("learning_path"))
        if not chapter_titles:
            chapter_titles = self._generate_outline(topic, lang)
        if not chapter_titles:  # 大纲也失败：退到通用占位标题
            chapter_titles = [f"第{i + 1}章 {topic or '课程主题'}" for i in range(_MIN_CHAPTERS)]

        # 2. 计划快照（前端编排面板 / draft 回退展示用）
        plan = [{"item": t, "type": "chapter", "detail": "生成讲解/测验/交互/编程场景"}
                for t in chapter_titles] + [{"item": "组装场景课件", "type": "build",
                                             "detail": "校验契约并落库"}]
        self.harness.update_plan(job, plan)

        # 3. 阶段开始（stage=harness → SSE stage_start）
        self.harness.emit(job, state.STAGE_HARNESS, state.EVENT_EPISODE_STARTED,
                          {}, "开始生成场景式课程")

        # 4. 并发让 LLM 生成每章场景内容
        chapter_drafts = self._expand_chapters(job, chapter_titles, topic, lang)

        # 5. 逐章组装场景序列（保留逐章推进的过程感）
        scenes: List[Dict[str, Any]] = []
        units: List[Dict[str, Any]] = []
        for index, (chapter_title, draft) in enumerate(zip(chapter_titles, chapter_drafts)):
            self._step_gap()
            unit_scenes, unit = self._build_chapter(
                job, chapter_title, index, draft, topic)
            scenes.extend(unit_scenes)
            units.append(unit)

        # 5.5 兜底：所有章节场景均为空（LLM 全部失败）时直接失败，
        # 而不是发布一门空场景课程（发布契约允许，但会得到不可预览的课程）
        if not scenes:
            raise RuntimeError("场景内容全部生成失败（LLM 调用异常），请重试")

        # 6. 组装 course.json 并写入工作区（scenes 顶层 + 兼容 units + 知识图谱）
        self._step_gap(_BUILD_GAP_SECONDS)
        course_json = {
            "title": title or f"{topic}学习课程",
            "description": description,
            "courseType": "python" if "python" in lang.lower() else
                          ("cpp" if "c++" in lang.lower() else "general"),
            "allowedRuntimes": ["web"],
            "scenes": scenes,
            "units": units,
            "knowledgeGraph": self._build_knowledge_graph(units),
        }
        self.harness.write_workspace_file(
            job, "course.json", json.dumps(course_json, ensure_ascii=False, indent=2))

        # 7. 阶段完成（stage=harness → SSE stage_complete）
        self.harness.emit(job, state.STAGE_HARNESS, state.EVENT_EPISODE_FINISHED,
                          {}, "场景式课程生成完成，等待发布")
        logger.info("coursegen: scene generation done for job %s (chapters=%d, scenes=%d)",
                    job.job_uid, len(chapter_titles), len(scenes))

    # ------------------------------ 大纲 ------------------------------

    def _guess_language(self, topic: str, config: Dict[str, Any]) -> str:
        """推断课程语言方向：config 显式指定 > 主题关键词 > 默认 Python。"""
        cfg_lang = str(config.get("language") or config.get("lang") or "").strip()
        if cfg_lang:
            return cfg_lang
        t = topic.lower()
        if any(k in t for k in ("c++", "cpp", "算法", "数据结构")):
            return "C++"
        if any(k in t for k in ("html", "css", "javascript", "前端", "网页")):
            return "Web前端"
        return "Python"

    def _outline_chapter_titles(self, learning_path: Any) -> List[str]:
        """从 learning_path 的 chapter 节点提取大纲章节标题（按节点顺序）。"""
        if not isinstance(learning_path, dict):
            return []
        nodes = learning_path.get("nodes")
        if not isinstance(nodes, list):
            return []
        titles: List[str] = []
        for node in nodes:
            data = node.get("data") if isinstance(node, dict) else None
            if isinstance(data, dict) and data.get("type") == "chapter":
                label = str(data.get("label") or "").strip()
                if label:
                    titles.append(label)
        return titles

    def _generate_outline(self, topic: str, lang: str) -> List[str]:
        """无大纲时由 LLM 生成章节标题序列；失败返回空列表（调用方兜底）。"""
        from app.services.llm_gateway import llm_gateway  # 延迟导入，避免启动期依赖
        if not topic:
            return []
        prompt = (
            "你是课程大纲设计专家。请为一个学习主题设计课程章节大纲。\n"
            f"主题：{topic}\n语言方向：{lang}\n\n"
            "请严格只输出一个 JSON 数组，不要输出任何其他文字。数组元素为字符串，"
            f"共 {_MIN_CHAPTERS}~{_MAX_CHAPTERS} 个章节标题，每项不超过 20 字，"
            "按学习顺序从易到难，紧扣主题。"
        )
        try:
            content = llm_gateway.get_completion_sync(
                system_prompt="你只输出合法 JSON，不输出任何多余文字。",
                messages=[{"role": "user", "content": prompt}],
            )
            text = (content or "").strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            parsed = json.loads(text)
            if isinstance(parsed, list):
                titles = [str(t).strip()[:20] for t in parsed if str(t).strip()]
                return titles[:_MAX_CHAPTERS]
        except Exception as exc:
            logger.warning("coursegen: outline generation failed: %s", exc)
        return []

    # ------------------------------ 场景生成 ------------------------------

    def _build_scene_prompt(self, chapter_title: str, index: int,
                            topic: str, lang: str) -> str:
        """构造单章场景 prompt：让 LLM 一次生成 slides + quiz + interactive + 可选 code。

        输出 JSON 结构：
          {"slides": [{"title","content"}], "quiz": [{"question","options",
           "answer","explanation"}], "interactive": {"title","description","html"},
           "code": {"language","description","initialCode","expectedOutput","testCases"}}
        code 为可选字段：仅当本章涉及编程/代码实践时由 LLM 输出，否则省略。
        """
        lang_hint = f"课程语言方向为「{lang}」，示例代码必须使用该语言。" if lang else ""
        topic_hint = f"课程主题：{topic}。" if topic else ""
        return (
            "你是资深课程设计专家，负责把一章讲透彻并配好练习。\n"
            f"{topic_hint}{lang_hint}\n"
            f"本章标题：{chapter_title}（课程第 {index + 1} 章）\n\n"
            "请严格只输出一个 JSON 对象，不要输出任何其他文字。字段说明：\n"
            f'- "slides"：数组，{_MIN_SLIDES_PER_CHAPTER}~{_MAX_SLIDES_PER_CHAPTER} 个讲解页，每页：\n'
            '    - "title"：字符串，页标题（不超过 20 字）；\n'
            '    - "content"：字符串，该页正文，用 Markdown 编写（300~600 字，'
            "含必要代码示例，代码用 ```语言 代码块 包裹）；\n"
            f'- "quiz"：数组，{_MIN_QUIZ_PER_CHAPTER}~{_MAX_QUIZ_PER_CHAPTER} 道单选题，每道：\n'
            '    - "question"：题干（30~100 字）；\n'
            '    - "options"：4 个选项字符串数组；\n'
            '    - "answer"：正确选项下标（0~3 的整数）；\n'
            '    - "explanation"：答案解析（30~100 字，讲清为什么）；\n'
            '- "interactive"：对象，一章一个交互小练习（自包含 HTML，内联 CSS/JS，'
            "用于演示本章概念，如可点击运行的小工具/可视化），字段：\n"
            '    - "title"：交互练习标题（不超过 20 字）；\n'
            '    - "description"：一句话说明练习内容（20~60 字）；\n'
            '    - "html"：完整自包含 HTML 源码字符串（含 <!DOCTYPE html>，内联 '
            "<style> 与 <script>，不引用任何外部资源）。\n"
            '- "code"：可选对象，仅当本章内容涉及编程/代码实践时才输出，'
            "与编程无关的章节必须省略该字段（不要生成空对象），字段：\n"
            '    - "language"：编程语言名（如 Python / C++ / JavaScript）；\n'
            '    - "description"：编程题目描述（30~120 字，说明任务与要求）；\n'
            '    - "initialCode"：初始代码字符串（含必要的函数骨架/注释占位，'
            "供学习者在其上补充实现，注意转义换行为 \\n）；\n"
            '    - "expectedOutput"：期望输出或验收要点（30~80 字）；\n'
            '    - "testCases"：2~3 个机器测试点数组，每项 {"input","expected"}，'
            "input 为程序 stdin 输入（多行用 \\n 表示），expected 为程序 stdout 期望输出"
            "（精确到行、比对前会去除首尾空白）。\n\n"
            "要求：slides 从概念到应用循序渐进；quiz 覆盖本章核心点且答案唯一；"
            "interactive 必须能直接在浏览器中运行；code 的初始代码与语言必须匹配"
            "本章编程主题。"
        )

    def _expand_chapters(self, job: CourseGenerationJob, chapter_titles: List[str],
                         topic: str, lang: str) -> List[Dict[str, Any]]:
        """并发调用 LLM 生成每章场景内容；单章失败回退空草稿。"""
        from app.services.llm_gateway import llm_gateway  # 延迟导入，避免启动期依赖

        drafts: List[Optional[Dict[str, Any]]] = [None] * len(chapter_titles)

        def _run(index: int, chapter_title: str) -> Dict[str, Any]:
            try:
                content = llm_gateway.get_completion_sync(
                    system_prompt="你只输出合法 JSON，不输出任何多余文字。",
                    messages=[{"role": "user",
                               "content": self._build_scene_prompt(
                                   chapter_title, index, topic, lang)}],
                )
                return self._parse_scene_draft(content)
            except Exception as exc:
                logger.warning("coursegen: chapter %d (%s) scene llm failed: %s",
                               index + 1, chapter_title, exc)
                return {}

        workers = min(_SCENE_MAX_WORKERS, len(chapter_titles))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(_run, i, t): i
                for i, t in enumerate(chapter_titles)
            }
            for future in futures:
                index = futures[future]
                try:
                    drafts[index] = future.result(timeout=settings.COURSEGEN_SCENE_TIMEOUT_SECONDS)
                except Exception as exc:
                    logger.warning("coursegen: chapter %d scene timeout/failed: %s",
                                   index + 1, exc)
                    drafts[index] = {}
        return [d or {} for d in drafts]

    def _parse_scene_draft(self, content: str) -> Dict[str, Any]:
        """解析单章 LLM 输出：剥离代码块 → JSON → 裁剪数量与字段。"""
        text = (content or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("场景草稿不是 JSON 对象")

        # slides：裁剪页数与标题长度
        slides: List[Dict[str, str]] = []
        raw_slides = parsed.get("slides")
        if isinstance(raw_slides, list):
            for item in raw_slides[:_MAX_SLIDES_PER_CHAPTER]:
                if not isinstance(item, dict):
                    continue
                slide_title = str(item.get("title") or "").strip()
                slide_content = str(item.get("content") or "").strip()
                if not slide_title or not slide_content:
                    continue
                slides.append({"title": slide_title[:20], "content": slide_content})
        # 不足下限时由调用方兜底，这里只做裁剪

        # quiz：裁剪题数
        quiz: List[Dict[str, Any]] = []
        raw_quiz = parsed.get("quiz")
        if isinstance(raw_quiz, list):
            for item in raw_quiz[:_MAX_QUIZ_PER_CHAPTER]:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question") or "").strip()
                options = [str(o).strip() for o in (item.get("options") or []) if str(o).strip()]
                if not question or len(options) < 2:
                    continue
                answer = item.get("answer")
                try:
                    answer = int(answer)
                except (TypeError, ValueError):
                    answer = 0
                if not (0 <= answer < len(options)):
                    answer = 0
                quiz.append({
                    "question": question[:200],
                    "options": options[:4],
                    "answer": answer,
                    "explanation": str(item.get("explanation") or "").strip()[:200],
                })

        # interactive：自包含 HTML（可选，解析失败/为空则跳过该场景）
        interactive: Dict[str, Any] = {}
        raw_ia = parsed.get("interactive")
        if isinstance(raw_ia, dict):
            html = str(raw_ia.get("html") or "").strip()
            if html:
                interactive = {
                    "title": str(raw_ia.get("title") or "交互练习").strip()[:20],
                    "description": str(raw_ia.get("description") or "").strip()[:100],
                    "html": html,
                }

        # code：编程练习（可选，仅编程相关章节出现；无初始代码则跳过）
        code: Dict[str, Any] = {}
        raw_code = parsed.get("code")
        if isinstance(raw_code, dict):
            initial_code = str(raw_code.get("initialCode") or "").strip()
            if initial_code:
                # testCases：机器测试点（input/expected 字符串对），非法项丢弃，最多保留 5 个
                test_cases: List[Dict[str, str]] = []
                raw_cases = raw_code.get("testCases")
                if isinstance(raw_cases, list):
                    for tc in raw_cases:
                        if not isinstance(tc, dict):
                            continue
                        tc_input = str(tc.get("input") or "")
                        tc_expected = str(tc.get("expected") or "")
                        if tc_expected.strip() and len(test_cases) < 5:
                            test_cases.append({"input": tc_input, "expected": tc_expected})
                code = {
                    "language": str(raw_code.get("language") or "Python").strip()[:20],
                    "description": str(raw_code.get("description") or "").strip()[:200],
                    "initialCode": initial_code,
                    "expectedOutput": str(raw_code.get("expectedOutput") or "").strip()[:200],
                    "testCases": test_cases,
                }
        return {"slides": slides, "quiz": quiz, "interactive": interactive, "code": code}

    # ------------------------------ 组装 ------------------------------

    def _build_chapter(self, job: CourseGenerationJob, chapter_title: str, index: int,
                       draft: Dict[str, Any], topic: str) -> tuple[List[Dict[str, Any]],
                                                                   Dict[str, Any]]:
        """组装一个章节：返回 (场景序列, 兼容 unit)。"""
        key = f"ch{index + 1}"
        item_title = f"第{index + 1}章：{chapter_title}"
        self.harness.emit(job, state.STAGE_EPISODE, state.EVENT_EPISODE_STARTED,
                          {"item": item_title}, item_title)

        slides = draft.get("slides") or []
        quiz = draft.get("quiz") or []
        interactive = draft.get("interactive") or {}
        code = draft.get("code") or {}

        # 场景序列：slides → quiz → interactive
        unit_scenes: List[Dict[str, Any]] = []
        if slides:
            unit_scenes.append({
                "key": f"{key}-slides",
                "type": "slides",
                "title": f"{chapter_title} · 讲解",
                "slides": slides,
            })
        if quiz:
            unit_scenes.append({
                "key": f"{key}-quiz",
                "type": "quiz",
                "title": f"{chapter_title} · 测验",
                "questions": quiz,
            })
        if interactive:
            unit_scenes.append({
                "key": f"{key}-interactive",
                "type": "interactive",
                "title": interactive.get("title") or f"{chapter_title} · 交互练习",
                "description": interactive.get("description") or "",
                "html": interactive.get("html") or "",
            })
        if code:
            unit_scenes.append({
                "key": f"{key}-code",
                "type": "code",
                "title": f"{chapter_title} · 编程练习",
                "language": code.get("language") or "Python",
                "description": code.get("description") or "",
                "initialCode": code.get("initialCode") or "",
                "expectedOutput": code.get("expectedOutput") or "",
                "testCases": code.get("testCases") or [],
            })

        # 兼容 unit：slides 内容落成 blocks（无 slides 时用占位知识点），保证发布契约
        blocks: List[Dict[str, Any]] = []
        if slides:
            for j, slide in enumerate(slides):
                body_path = f"{_BODY_PATH_PREFIX}/{key}/s{j + 1}.md"
                self.harness.write_workspace_file(job, body_path, slide["content"])
                blocks.append({
                    "kind": "corpus",
                    "title": slide["title"],
                    "bodyPath": body_path,
                    "format": "markdown",
                    "sortOrder": j + 1,
                })
        else:
            # 单章 LLM 失败：落一个占位知识点，保证章节不空、契约可过
            body_path = f"{_BODY_PATH_PREFIX}/{key}/s1.md"
            self.harness.write_workspace_file(
                job, body_path, f"# {chapter_title}\n\n（本章内容生成失败，请稍后重试。）")
            blocks.append({
                "kind": "corpus",
                "title": chapter_title,
                "bodyPath": body_path,
                "format": "markdown",
                "sortOrder": 1,
            })

        self.harness.emit(job, state.STAGE_EPISODE, state.EVENT_EPISODE_FINISHED,
                          {"item": item_title}, f"已完成：{item_title}")
        return unit_scenes, {"key": key, "title": chapter_title, "sortOrder": index + 1,
                             "blocks": blocks, "tests": []}

    def _build_knowledge_graph(self, units: List[Dict[str, Any]]) -> Dict[str, Any]:
        """由生成的 units 推导知识图谱：章节→知识点，章节按顺序串链。"""
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        for i, unit in enumerate(units):
            nodes.append({"data": {"id": unit["key"], "label": unit["title"],
                                   "type": "chapter"}})
            for j, block in enumerate(unit.get("blocks") or []):
                sid = f"{unit['key']}_s{j + 1}"
                nodes.append({"data": {"id": sid, "label": block["title"],
                                       "type": "knowledge"}})
                edges.append({"data": {"source": unit["key"], "target": sid}})
            if i + 1 < len(units):
                edges.append({"data": {"source": unit["key"], "target": units[i + 1]["key"]}})
        return {"nodes": nodes, "edges": edges}

    def _step_gap(self, seconds: float = 0.0) -> None:
        """章节间停顿：保留逐章推进的过程感（LLM 耗时本身已提供主体时长）。"""
        time.sleep(seconds if seconds > 0 else _STEP_GAP_SECONDS)
