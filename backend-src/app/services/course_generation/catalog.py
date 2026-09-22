"""教师端模板与主题目录。

骨架阶段用静态样例数据提供模板元数据、生成阶段与主题列表，让前端完整流程可测。
LLM 模板检测（detect-template 的真实匹配）与主题库扩充在后续步骤接入。
"""
from typing import Dict, List

# 模板元数据：checkpoint_paradigm 决定汇总编辑区按 Web 题还是代码题渲染
TEMPLATES: List[Dict[str, str]] = [
    {"template_id": "web-frontend", "template_name": "Web 前端开发",
     "checkpoint_paradigm": "web", "language": "html"},
    {"template_id": "python-basic", "template_name": "Python 编程基础",
     "checkpoint_paradigm": "code", "language": "python"},
    {"template_id": "cpp-basic", "template_name": "C++ 编程基础",
     "checkpoint_paradigm": "code", "language": "cpp"},
    # 一句话生成（OpenMAIC 式）：不选模板，LLM 按主题直接生成场景式课件。
    # 仅作为元数据占位，供教师端 getStages 拉取生成阶段；真实生成走 LlmGenerator。
    {"template_id": "llm", "template_name": "AI 智能生成（OpenMAIC 式）",
     "checkpoint_paradigm": "code", "language": "general"},
]

# 每个模板的生成阶段（前端进度条与编排面板按此渲染）
STAGES: Dict[str, List[Dict[str, object]]] = {
    "web-frontend": [
        {"stage": "design", "name": "方向确认", "enabled": True},
        {"stage": "chapters", "name": "章节生成", "enabled": True},
        {"stage": "tasks", "name": "测试任务", "enabled": True},
        {"stage": "judge", "name": "判题配置", "enabled": False},
        {"stage": "review", "name": "教师终审", "enabled": True},
    ],
    "python-basic": [
        {"stage": "design", "name": "方向确认", "enabled": True},
        {"stage": "chapters", "name": "章节生成", "enabled": True},
        {"stage": "tasks", "name": "测试任务", "enabled": True},
        {"stage": "judge", "name": "判题配置", "enabled": True},
        {"stage": "review", "name": "教师终审", "enabled": True},
    ],
    "cpp-basic": [
        {"stage": "design", "name": "方向确认", "enabled": True},
        {"stage": "chapters", "name": "章节生成", "enabled": True},
        {"stage": "tasks", "name": "测试任务", "enabled": True},
        {"stage": "judge", "name": "判题配置", "enabled": True},
        {"stage": "review", "name": "教师终审", "enabled": True},
    ],
    # 一句话生成（LLM 引导）的生成阶段：大纲 → 场景 → 发布
    "llm": [
        {"stage": "outline", "name": "大纲规划", "enabled": True},
        {"stage": "scenes", "name": "场景生成", "enabled": True},
        {"stage": "publish", "name": "内容发布", "enabled": True},
    ],
}

# 示例主题
THEMES: List[Dict[str, str]] = [
    {"id": "minimal", "name": "极简风", "description": "白底黑字，专注内容"},
    {"id": "default-dark", "name": "深色专业", "description": "深蓝底色，适合技术课程"},
    {"id": "colorful", "name": "活泼多彩", "description": "高饱和配色，适合青少年课程"},
    {"id": "flat", "name": "扁平化", "description": "简约扁平，现代感强"},
]


def get_template(template_id: str) -> Dict[str, str]:
    """按 id 取模板元数据；不存在返回空 dict。"""
    for item in TEMPLATES:
        if item["template_id"] == template_id:
            return item
    return {}


def get_theme(theme_id: str) -> Dict[str, str]:
    """按 id 取主题；不存在返回空 dict。"""
    for item in THEMES:
        if item["id"] == theme_id:
            return item
    return {}
